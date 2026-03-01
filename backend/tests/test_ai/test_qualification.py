"""Tests for the qualification state machine."""

import pytest

from app.ai.qualification import (
    InvalidTransitionError,
    QualificationStage,
    QualificationStateMachine,
    STAGE_WEIGHTS,
    TRANSITIONS,
)


class TestQualificationStage:
    """Test QualificationStage enum."""

    def test_all_stages_exist(self):
        stages = [s.value for s in QualificationStage]
        assert "initial" in stages
        assert "needs_discovery" in stages
        assert "budget_check" in stages
        assert "timeline_check" in stages
        assert "decision_maker" in stages
        assert "qualified" in stages
        assert "booking_offer" in stages
        assert "booked" in stages
        assert "handed_off" in stages

    def test_stage_count(self):
        assert len(QualificationStage) == 9


class TestTransitions:
    """Test state transition definitions."""

    def test_initial_transitions_to_needs_discovery(self):
        assert QualificationStage.NEEDS_DISCOVERY in TRANSITIONS[QualificationStage.INITIAL]

    def test_needs_discovery_to_budget(self):
        assert QualificationStage.BUDGET_CHECK in TRANSITIONS[QualificationStage.NEEDS_DISCOVERY]

    def test_budget_to_timeline(self):
        assert QualificationStage.TIMELINE_CHECK in TRANSITIONS[QualificationStage.BUDGET_CHECK]

    def test_timeline_to_decision_maker(self):
        assert QualificationStage.DECISION_MAKER in TRANSITIONS[QualificationStage.TIMELINE_CHECK]

    def test_decision_maker_to_qualified(self):
        assert QualificationStage.QUALIFIED in TRANSITIONS[QualificationStage.DECISION_MAKER]

    def test_qualified_to_booking_offer(self):
        assert QualificationStage.BOOKING_OFFER in TRANSITIONS[QualificationStage.QUALIFIED]

    def test_booking_offer_has_two_transitions(self):
        allowed = TRANSITIONS[QualificationStage.BOOKING_OFFER]
        assert QualificationStage.BOOKED in allowed
        assert QualificationStage.HANDED_OFF in allowed

    def test_booked_is_terminal(self):
        assert len(TRANSITIONS[QualificationStage.BOOKED]) == 0

    def test_handed_off_is_terminal(self):
        assert len(TRANSITIONS[QualificationStage.HANDED_OFF]) == 0


class TestQualificationStateMachine:
    """Test QualificationStateMachine class."""

    def test_default_initial_stage(self):
        sm = QualificationStateMachine()
        assert sm.current_stage == QualificationStage.INITIAL

    def test_init_with_string_stage(self):
        sm = QualificationStateMachine(current_stage="budget_check")
        assert sm.current_stage == QualificationStage.BUDGET_CHECK

    def test_init_with_enum_stage(self):
        sm = QualificationStateMachine(current_stage=QualificationStage.QUALIFIED)
        assert sm.current_stage == QualificationStage.QUALIFIED

    def test_init_with_none_defaults_to_initial(self):
        sm = QualificationStateMachine(current_stage=None)
        assert sm.current_stage == QualificationStage.INITIAL

    def test_advance_from_initial(self):
        sm = QualificationStateMachine()
        new_stage = sm.advance()
        assert new_stage == QualificationStage.NEEDS_DISCOVERY

    def test_advance_through_all_stages(self):
        sm = QualificationStateMachine()
        expected_sequence = [
            QualificationStage.NEEDS_DISCOVERY,
            QualificationStage.BUDGET_CHECK,
            QualificationStage.TIMELINE_CHECK,
            QualificationStage.DECISION_MAKER,
            QualificationStage.QUALIFIED,
            QualificationStage.BOOKING_OFFER,
        ]
        for expected in expected_sequence:
            result = sm.advance({"test_data": True})
            assert result == expected

    def test_advance_from_terminal_raises(self):
        sm = QualificationStateMachine(current_stage=QualificationStage.BOOKED)
        with pytest.raises(InvalidTransitionError):
            sm.advance()

    def test_advance_stores_collected_data(self):
        sm = QualificationStateMachine()
        sm.advance({"needs": "Website redesign"})
        data = sm.get_qualification_data()
        assert data["needs"] == "Website redesign"

    def test_can_advance_when_stage_data_present(self):
        sm = QualificationStateMachine(
            current_stage=QualificationStage.NEEDS_DISCOVERY,
            qualification_data={"needs_discovery": True},
        )
        assert sm.can_advance() is True

    def test_cannot_advance_when_stage_data_missing(self):
        sm = QualificationStateMachine(
            current_stage=QualificationStage.NEEDS_DISCOVERY,
            qualification_data={},
        )
        assert sm.can_advance() is False

    def test_interest_score_zero_initially(self):
        sm = QualificationStateMachine()
        assert sm.calculate_interest_score() == 0

    def test_interest_score_after_needs_discovery(self):
        sm = QualificationStateMachine(
            qualification_data={"needs_discovery": True},
        )
        assert sm.calculate_interest_score() == 25

    def test_interest_score_after_all_qualifying_stages(self):
        sm = QualificationStateMachine(
            qualification_data={
                "needs_discovery": True,
                "budget_check": True,
                "timeline_check": True,
                "decision_maker": True,
            },
        )
        assert sm.calculate_interest_score() == 100

    def test_interest_score_caps_at_100(self):
        sm = QualificationStateMachine(
            qualification_data={
                "needs_discovery": True,
                "budget_check": True,
                "timeline_check": True,
                "decision_maker": True,
                "extra_data": "should not matter",
            },
        )
        assert sm.calculate_interest_score() == 100

    def test_interest_score_partial(self):
        sm = QualificationStateMachine(
            qualification_data={
                "needs_discovery": True,
                "budget_check": True,
            },
        )
        assert sm.calculate_interest_score() == 50

    def test_is_terminal_booked(self):
        sm = QualificationStateMachine(current_stage=QualificationStage.BOOKED)
        assert sm.is_terminal() is True

    def test_is_terminal_handed_off(self):
        sm = QualificationStateMachine(current_stage=QualificationStage.HANDED_OFF)
        assert sm.is_terminal() is True

    def test_is_not_terminal_qualified(self):
        sm = QualificationStateMachine(current_stage=QualificationStage.QUALIFIED)
        assert sm.is_terminal() is False

    def test_is_qualified_for_qualified_stage(self):
        sm = QualificationStateMachine(current_stage=QualificationStage.QUALIFIED)
        assert sm.is_qualified() is True

    def test_is_qualified_for_booking_offer(self):
        sm = QualificationStateMachine(current_stage=QualificationStage.BOOKING_OFFER)
        assert sm.is_qualified() is True

    def test_is_qualified_for_booked(self):
        sm = QualificationStateMachine(current_stage=QualificationStage.BOOKED)
        assert sm.is_qualified() is True

    def test_is_not_qualified_for_initial(self):
        sm = QualificationStateMachine(current_stage=QualificationStage.INITIAL)
        assert sm.is_qualified() is False

    def test_get_qualification_data_returns_copy(self):
        data = {"needs_discovery": True}
        sm = QualificationStateMachine(qualification_data=data)
        result = sm.get_qualification_data()
        result["extra"] = "modified"
        # Original should not be affected
        assert "extra" not in sm.get_qualification_data()

    def test_script_stages_parsing(self):
        script_stages = [
            {
                "stage_id": "needs_discovery",
                "order": 1,
                "question_prompt": "What do you need?",
                "expected_info": "Customer needs",
                "follow_ups": ["Tell me more"],
                "next_stage": "budget_check",
            }
        ]
        sm = QualificationStateMachine(
            current_stage=QualificationStage.NEEDS_DISCOVERY,
            script_stages=script_stages,
        )
        assert sm.get_current_prompt() == "What do you need?"
        assert sm.get_expected_info() == "Customer needs"
        assert sm.get_follow_ups() == ["Tell me more"]

    def test_get_prompt_when_no_script(self):
        sm = QualificationStateMachine(current_stage=QualificationStage.NEEDS_DISCOVERY)
        assert sm.get_current_prompt() == ""
