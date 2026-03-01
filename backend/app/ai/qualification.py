"""Qualification state machine for lead qualification stages."""

import enum
import structlog
from dataclasses import dataclass, field
from typing import Any

logger = structlog.get_logger(__name__)


class QualificationStage(str, enum.Enum):
    """All possible qualification stages."""

    INITIAL = "initial"
    NEEDS_DISCOVERY = "needs_discovery"
    BUDGET_CHECK = "budget_check"
    TIMELINE_CHECK = "timeline_check"
    DECISION_MAKER = "decision_maker"
    QUALIFIED = "qualified"
    BOOKING_OFFER = "booking_offer"
    BOOKED = "booked"
    HANDED_OFF = "handed_off"


# Valid state transitions: current_stage -> set of allowed next stages
TRANSITIONS: dict[QualificationStage, set[QualificationStage]] = {
    QualificationStage.INITIAL: {QualificationStage.NEEDS_DISCOVERY},
    QualificationStage.NEEDS_DISCOVERY: {QualificationStage.BUDGET_CHECK},
    QualificationStage.BUDGET_CHECK: {QualificationStage.TIMELINE_CHECK},
    QualificationStage.TIMELINE_CHECK: {QualificationStage.DECISION_MAKER},
    QualificationStage.DECISION_MAKER: {QualificationStage.QUALIFIED},
    QualificationStage.QUALIFIED: {QualificationStage.BOOKING_OFFER},
    QualificationStage.BOOKING_OFFER: {QualificationStage.BOOKED, QualificationStage.HANDED_OFF},
    QualificationStage.BOOKED: set(),
    QualificationStage.HANDED_OFF: set(),
}

# Score weights per stage (each contributes up to 25 points)
STAGE_WEIGHTS: dict[QualificationStage, int] = {
    QualificationStage.NEEDS_DISCOVERY: 25,
    QualificationStage.BUDGET_CHECK: 25,
    QualificationStage.TIMELINE_CHECK: 25,
    QualificationStage.DECISION_MAKER: 25,
}

# Human-readable Russian labels for each qualification stage
STAGE_LABELS: dict[str, str] = {
    "initial": "Начало",
    "needs_discovery": "Выявление потребностей",
    "budget_check": "Обсуждение бюджета",
    "timeline_check": "Выяснение сроков",
    "decision_maker": "Определение ЛПР",
    "qualified": "Квалифицирован",
    "booking_offer": "Предложение записи",
    "booked": "Записан",
    "handed_off": "Передано менеджеру",
}


def compute_score_breakdown(
    qualification_data: dict[str, Any] | None,
    score_config: dict[str, int] | None,
) -> list[dict[str, Any]]:
    """Compute per-stage score breakdown.

    Returns a list of dicts with keys:
    - stage_id: str
    - stage_label: str (from STAGE_LABELS or stage_id as fallback)
    - weight: int (from score_config or STAGE_WEIGHTS)
    - completed: bool (stage_id present in qualification_data)
    - collected_info: str | None (from _score_history if available)
    """
    data = qualification_data or {}

    # Build a lookup from _score_history: stage -> info
    score_history = data.get("_score_history", [])
    history_info: dict[str, str] = {}
    for entry in score_history:
        stage = entry.get("stage", "")
        info = entry.get("info", "")
        if stage and info:
            history_info[stage] = info

    result: list[dict[str, Any]] = []

    if score_config:
        # Use custom score_config keys and weights
        for stage_key, weight in score_config.items():
            stage_id = stage_key.lower()
            result.append({
                "stage_id": stage_id,
                "stage_label": STAGE_LABELS.get(stage_id, stage_id),
                "weight": weight,
                "completed": stage_id in data,
                "collected_info": history_info.get(stage_id),
            })
    else:
        # Use default STAGE_WEIGHTS (enum keys)
        for stage_enum, weight in STAGE_WEIGHTS.items():
            stage_id = stage_enum.value
            result.append({
                "stage_id": stage_id,
                "stage_label": STAGE_LABELS.get(stage_id, stage_id),
                "weight": weight,
                "completed": stage_id in data,
                "collected_info": history_info.get(stage_id),
            })

    return result


class InvalidTransitionError(Exception):
    """Raised when an invalid stage transition is attempted."""


@dataclass
class StageInfo:
    """Information about a single qualification script stage."""

    stage_id: str
    order: int
    question_prompt: str
    expected_info: str
    follow_ups: list[str] = field(default_factory=list)
    next_stage: str | None = None


class QualificationStateMachine:
    """Manages lead qualification through a series of stages.

    Uses a QualificationScript's stages to determine prompts and expected info.
    Tracks collected data and calculates an interest score.
    """

    def __init__(
        self,
        current_stage: QualificationStage | str | None = None,
        qualification_data: dict[str, Any] | None = None,
        script_stages: list[dict[str, Any]] | None = None,
        score_config: dict[str, int] | None = None,
    ) -> None:
        """Initialize the state machine.

        Args:
            current_stage: Current qualification stage (str or enum).
            qualification_data: Previously collected qualification data.
            script_stages: Stages from QualificationScript.stages JSONB field.
            score_config: Optional custom weights per stage_id for interest
                score calculation. When None, falls back to STAGE_WEIGHTS.
        """
        if current_stage is None:
            self._current_stage = QualificationStage.INITIAL
        elif isinstance(current_stage, str):
            self._current_stage = QualificationStage(current_stage)
        else:
            self._current_stage = current_stage

        self._qualification_data: dict[str, Any] = qualification_data or {}
        self._script_stages = self._parse_stages(script_stages or [])
        self._score_config = score_config

    @staticmethod
    def _parse_stages(raw_stages: list[dict[str, Any]]) -> dict[str, StageInfo]:
        """Parse script stages JSONB into StageInfo objects keyed by stage_id."""
        stages: dict[str, StageInfo] = {}
        for raw in raw_stages:
            info = StageInfo(
                stage_id=raw.get("stage_id", ""),
                order=raw.get("order", 0),
                question_prompt=raw.get("question_prompt", ""),
                expected_info=raw.get("expected_info", ""),
                follow_ups=raw.get("follow_ups", []),
                next_stage=raw.get("next_stage"),
            )
            stages[info.stage_id] = info
        return stages

    @property
    def current_stage(self) -> QualificationStage:
        """Return the current qualification stage."""
        return self._current_stage

    def get_current_prompt(self) -> str:
        """Return the question prompt for the current stage from the script.

        Returns an empty string if no matching stage is found in the script.
        """
        stage_info = self._script_stages.get(self._current_stage.value)
        if stage_info:
            return stage_info.question_prompt
        return ""

    def get_expected_info(self) -> str:
        """Return the expected information to collect at the current stage."""
        stage_info = self._script_stages.get(self._current_stage.value)
        if stage_info:
            return stage_info.expected_info
        return ""

    def get_follow_ups(self) -> list[str]:
        """Return follow-up prompts for the current stage."""
        stage_info = self._script_stages.get(self._current_stage.value)
        if stage_info:
            return stage_info.follow_ups
        return []

    def can_advance(self) -> bool:
        """Check if the current stage has enough collected data to advance.

        Returns True if the current stage's key exists in qualification_data.
        """
        stage_key = self._current_stage.value
        return stage_key in self._qualification_data

    def advance(self, collected_data: dict[str, Any] | None = None) -> QualificationStage:
        """Attempt to advance to the next stage.

        Args:
            collected_data: Data collected during the current stage.
                Keys should describe the information (e.g., 'needs', 'budget').

        Returns:
            The new current stage after transition.

        Raises:
            InvalidTransitionError: If no valid transition exists from the current stage.
        """
        allowed = TRANSITIONS.get(self._current_stage, set())
        if not allowed:
            raise InvalidTransitionError(
                f"No transitions available from stage {self._current_stage.value}"
            )

        # Store collected data
        if collected_data:
            self._qualification_data.update(collected_data)

        # Mark current stage as completed in data
        if self._current_stage.value not in self._qualification_data:
            self._qualification_data[self._current_stage.value] = True

        # Determine next stage
        # Check if the script defines a specific next_stage
        stage_info = self._script_stages.get(self._current_stage.value)
        if stage_info and stage_info.next_stage:
            try:
                next_stage = QualificationStage(stage_info.next_stage)
                if next_stage in allowed:
                    self._current_stage = next_stage
                    logger.info("Advanced to stage: %s", self._current_stage.value)
                    return self._current_stage
            except ValueError:
                pass

        # Default: pick the first (and usually only) allowed transition
        next_stage = sorted(allowed, key=lambda s: s.value)[0]
        self._current_stage = next_stage
        logger.info("Advanced to stage: %s", self._current_stage.value)
        return self._current_stage

    def calculate_interest_score(self) -> int:
        """Calculate interest score (0-100) based on completed stages.

        Uses custom score_config weights if provided, otherwise falls back
        to the default STAGE_WEIGHTS. Each completed qualifying stage
        contributes its configured weight to the score.

        Note: qualification_data keys are always lowercase (from enum values).
        score_config keys may be uppercase (from script stage_ids), so we
        normalize to lowercase for comparison.
        """
        if self._score_config:
            score = 0
            for stage_key, weight in self._score_config.items():
                # Normalize to lowercase — qualification_data uses lowercase enum values
                if stage_key.lower() in self._qualification_data:
                    score += weight
            logger.debug(
                "interest_score_calculated",
                source="score_config",
                score=min(score, 100),
                config_keys=list(self._score_config.keys()),
                data_keys=list(self._qualification_data.keys()),
            )
            return min(score, 100)

        # Default: use STAGE_WEIGHTS with enum keys
        score = 0
        for stage, weight in STAGE_WEIGHTS.items():
            if stage.value in self._qualification_data:
                score += weight
        logger.debug(
            "interest_score_calculated",
            source="stage_weights",
            score=min(score, 100),
            data_keys=list(self._qualification_data.keys()),
        )
        return min(score, 100)

    def get_qualification_data(self) -> dict[str, Any]:
        """Return all collected qualification data."""
        return dict(self._qualification_data)

    def is_terminal(self) -> bool:
        """Check if the current stage is a terminal state (BOOKED or HANDED_OFF)."""
        return self._current_stage in {QualificationStage.BOOKED, QualificationStage.HANDED_OFF}

    def is_qualified(self) -> bool:
        """Check if the lead has reached QUALIFIED or beyond."""
        terminal_or_qualified = {
            QualificationStage.QUALIFIED,
            QualificationStage.BOOKING_OFFER,
            QualificationStage.BOOKED,
            QualificationStage.HANDED_OFF,
        }
        return self._current_stage in terminal_or_qualified
