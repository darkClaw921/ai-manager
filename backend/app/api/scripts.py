"""Scripts API: CRUD for qualification scripts, FAQ items, objection scripts, Qdrant sync, bulk import."""

import json
import re
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client_factory import create_llm_client
from app.db.repository import BaseRepository
from app.dependencies import EffectiveOwnerId, get_current_user, get_db
from app.models.script import FAQItem, ObjectionScript, QualificationScript
from app.models.user import AdminUser
from app.schemas.common import PaginatedResponse
from app.schemas.script import (
    BulkTextImport,
    FAQItemCreate,
    FAQItemResponse,
    FAQItemUpdate,
    ObjectionScriptCreate,
    ObjectionScriptResponse,
    ObjectionScriptUpdate,
    QualificationScriptCreate,
    QualificationScriptResponse,
    QualificationScriptUpdate,
    ScoreConfigUpdate,
)

logger = structlog.get_logger(__name__)


def _extract_json_array(text: str) -> str:
    """Extract a JSON array from LLM response, stripping code fences and surrounding text."""
    stripped = text.strip()
    # Remove markdown code fences
    stripped = re.sub(r"^```(?:json)?\s*\n?", "", stripped)
    stripped = re.sub(r"\n?```\s*$", "", stripped)
    stripped = stripped.strip()

    # Try to find JSON array boundaries if there's extra text around it
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start != -1 and end != -1 and end > start:
        stripped = stripped[start : end + 1]

    return stripped


def _extract_json_object(text: str) -> str:
    """Extract a JSON object from LLM response, stripping code fences and surrounding text."""
    stripped = text.strip()
    # Remove markdown code fences
    stripped = re.sub(r"^```(?:json)?\s*\n?", "", stripped)
    stripped = re.sub(r"\n?```\s*$", "", stripped)
    stripped = stripped.strip()

    # Try to find JSON object boundaries if there's extra text around it
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        stripped = stripped[start : end + 1]

    return stripped


def _check_resource_owner(resource: object, owner_id: uuid.UUID | None, detail: str = "Not found") -> None:
    """Check that a resource belongs to the effective owner. Raises 404 if not."""
    if owner_id is not None and getattr(resource, "owner_id", None) != owner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


router = APIRouter()

# --- Qualification Scripts ---


@router.get("/qualification", response_model=list[QualificationScriptResponse])
async def list_qualification_scripts(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> list[QualificationScriptResponse]:
    """List all qualification scripts."""
    repo = BaseRepository(QualificationScript, db)
    filters = []
    if owner_id is not None:
        filters.append(QualificationScript.owner_id == owner_id)
    items = await repo.get_multi(limit=100, filters=filters, order_by=QualificationScript.created_at.desc())
    return [QualificationScriptResponse.model_validate(item) for item in items]


@router.post("/qualification", response_model=QualificationScriptResponse, status_code=status.HTTP_201_CREATED)
async def create_qualification_script(
    body: QualificationScriptCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AdminUser, Depends(get_current_user)],
) -> QualificationScriptResponse:
    """Create a new qualification script."""
    repo = BaseRepository(QualificationScript, db)
    script = await repo.create(**body.model_dump(), owner_id=current_user.id)
    return QualificationScriptResponse.model_validate(script)


@router.put("/qualification/{script_id}", response_model=QualificationScriptResponse)
async def update_qualification_script(
    script_id: uuid.UUID,
    body: QualificationScriptUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> QualificationScriptResponse:
    """Update a qualification script."""
    repo = BaseRepository(QualificationScript, db)
    script = await repo.get(script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    _check_resource_owner(script, owner_id, "Script not found")
    script = await repo.update(script, **body.model_dump(exclude_unset=True))
    return QualificationScriptResponse.model_validate(script)


@router.put("/qualification/{script_id}/score-config", response_model=QualificationScriptResponse)
async def update_score_config(
    script_id: uuid.UUID,
    body: ScoreConfigUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> QualificationScriptResponse:
    """Update score weights for a qualification script.

    Validates that all keys in score_config correspond to valid stage_ids
    defined in the script's stages array. Values must be non-negative integers.
    """
    repo = BaseRepository(QualificationScript, db)
    script = await repo.get(script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    _check_resource_owner(script, owner_id, "Script not found")

    # Validate stage_ids against the script's stages
    valid_stage_ids = {s["stage_id"] for s in (script.stages or []) if isinstance(s, dict) and "stage_id" in s}
    provided_stage_ids = set(body.score_config.keys())
    invalid_ids = provided_stage_ids - valid_stage_ids
    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid stage_ids: {', '.join(sorted(invalid_ids))}. Valid: {', '.join(sorted(valid_stage_ids))}",
        )

    # Validate values are non-negative
    for stage_id, weight in body.score_config.items():
        if weight < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Weight for '{stage_id}' must be non-negative, got {weight}",
            )

    script = await repo.update(script, score_config=body.score_config)
    return QualificationScriptResponse.model_validate(script)


@router.delete("/qualification/{script_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_qualification_script(
    script_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> None:
    """Delete a qualification script."""
    repo = BaseRepository(QualificationScript, db)
    script = await repo.get(script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")
    _check_resource_owner(script, owner_id, "Script not found")
    await repo.delete(script)


@router.post("/qualification/generate", response_model=QualificationScriptResponse, status_code=status.HTTP_201_CREATED)
async def generate_qualification_script(
    body: BulkTextImport,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AdminUser, Depends(get_current_user)],
) -> QualificationScriptResponse:
    """Generate a qualification script from a business description using LLM.

    Sends the business description to the configured LLM, which returns a JSON object
    with name, description, and stages array. The script is created in the DB and returned.
    """
    try:
        llm = await create_llm_client(db)
    except Exception as exc:
        logger.error("llm_client_create_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Не удалось создать LLM-клиент: {exc}",
        ) from exc

    try:
        response = await llm.send_message(
            messages=[{"role": "user", "content": body.text}],
            system=(
                "Ты -- генератор скриптов квалификации лидов для AI-менеджера. "
                "На основе описания бизнеса/продукта создай скрипт квалификации. "
                "Верни ТОЛЬКО валидный JSON объект без какого-либо другого текста. "
                "Формат: "
                '{"name": "Название скрипта", "description": "Краткое описание", "stages": ['
                '{"stage_id": "needs_discovery", "question_prompt": "Инструкция для AI на этом этапе", '
                '"expected_info": "Какую информацию нужно собрать", '
                '"follow_ups": ["Дополнительный вопрос 1", "Дополнительный вопрос 2"], '
                '"next_stage": "budget_check", "order": 0}]}. '
                "Допустимые значения stage_id (ТОЛЬКО эти четыре): needs_discovery, budget_check, "
                "timeline_check, decision_maker. "
                "Создай 3-4 этапа из этого списка, подходящих для данного бизнеса. "
                "next_stage последнего этапа должен быть null."
            ),
            max_tokens=34096,
        )
    except Exception as exc:
        logger.error("llm_qualification_generate_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка LLM: {exc}",
        ) from exc
    finally:
        await llm.close()

    logger.info(
        "llm_qualification_generate_response",
        stop_reason=response.stop_reason,
        text_length=len(response.text),
        text_preview=response.text[:300] if response.text else "<empty>",
    )

    if not response.text.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM вернул пустой ответ. Попробуйте ещё раз.",
        )

    raw_text = _extract_json_object(response.text)

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("llm_qualification_generate_invalid_json", raw=raw_text[:500])
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="LLM вернул невалидный JSON. Попробуйте переформулировать описание.",
        ) from exc

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="LLM вернул не объект. Ожидался JSON-объект скрипта квалификации.",
        )

    name = parsed.get("name", "").strip() if isinstance(parsed.get("name"), str) else ""
    stages = parsed.get("stages") if isinstance(parsed.get("stages"), list) else []
    if not name:
        name = "Сгенерированный скрипт"

    repo = BaseRepository(QualificationScript, db)
    script = await repo.create(
        name=name,
        description=parsed.get("description") if isinstance(parsed.get("description"), str) else None,
        stages=stages,
        is_active=True,
        owner_id=current_user.id,
    )
    return QualificationScriptResponse.model_validate(script)


# --- FAQ Items ---


@router.get("/faq", response_model=PaginatedResponse[FAQItemResponse])
async def list_faq_items(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    script_id: uuid.UUID | None = Query(None, description="Filter by qualification script ID"),
) -> PaginatedResponse[FAQItemResponse]:
    """List FAQ items with pagination."""
    repo = BaseRepository(FAQItem, db)
    filters = []
    if owner_id is not None:
        filters.append(FAQItem.owner_id == owner_id)
    if script_id is not None:
        filters.append(FAQItem.qualification_script_id == script_id)
    total = await repo.count(filters)
    offset = (page - 1) * page_size
    items = await repo.get_multi(offset=offset, limit=page_size, filters=filters, order_by=FAQItem.created_at.desc())
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedResponse(
        items=[FAQItemResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        pages=pages,
    )


@router.post("/faq", response_model=FAQItemResponse, status_code=status.HTTP_201_CREATED)
async def create_faq_item(
    body: FAQItemCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AdminUser, Depends(get_current_user)],
) -> FAQItemResponse:
    """Create a new FAQ item."""
    repo = BaseRepository(FAQItem, db)
    item = await repo.create(**body.model_dump(), owner_id=current_user.id)
    return FAQItemResponse.model_validate(item)


@router.put("/faq/{faq_id}", response_model=FAQItemResponse)
async def update_faq_item(
    faq_id: uuid.UUID,
    body: FAQItemUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> FAQItemResponse:
    """Update a FAQ item."""
    repo = BaseRepository(FAQItem, db)
    item = await repo.get(faq_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ item not found")
    _check_resource_owner(item, owner_id, "FAQ item not found")
    item = await repo.update(item, **body.model_dump(exclude_unset=True))
    return FAQItemResponse.model_validate(item)


@router.delete("/faq/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_faq_item(
    faq_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> None:
    """Delete a FAQ item."""
    repo = BaseRepository(FAQItem, db)
    item = await repo.get(faq_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ item not found")
    _check_resource_owner(item, owner_id, "FAQ item not found")
    await repo.delete(item)


@router.post("/faq/sync", status_code=status.HTTP_200_OK)
async def sync_faq_to_qdrant(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
) -> dict:
    """Re-sync all FAQ items to Qdrant vector DB."""
    from app.ai.embeddings import EmbeddingsManager
    from app.ai.qdrant_init import sync_faq_to_qdrant as _sync_faq
    from app.config import get_settings
    from qdrant_client import AsyncQdrantClient

    settings = get_settings()
    qdrant = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    embeddings = EmbeddingsManager.get_instance()
    count = await _sync_faq(db, qdrant, embeddings)
    await qdrant.close()
    return {"status": "ok", "synced": count}


@router.post("/faq/parse", response_model=list[FAQItemResponse], status_code=status.HTTP_201_CREATED)
async def parse_faq_from_text(
    body: BulkTextImport,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AdminUser, Depends(get_current_user)],
) -> list[FAQItemResponse]:
    """Parse free-form text into FAQ items using LLM.

    Sends the text to the configured LLM, which returns a JSON array of
    {question, answer} objects. The records are created in the DB and returned.
    """
    try:
        llm = await create_llm_client(db)
    except Exception as exc:
        logger.error("llm_client_create_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Не удалось создать LLM-клиент: {exc}",
        ) from exc

    try:
        response = await llm.send_message(
            messages=[{"role": "user", "content": body.text}],
            system=(
                "Ты -- парсер текста. Разбей предоставленный текст на FAQ-пары (вопрос и ответ). "
                "Верни ТОЛЬКО валидный JSON массив без какого-либо другого текста. "
                'Формат: [{"question": "вопрос", "answer": "ответ"}]'
            ),
            max_tokens=16384,
        )
    except Exception as exc:
        logger.error("llm_faq_parse_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка LLM: {exc}",
        ) from exc
    finally:
        await llm.close()

    logger.info(
        "llm_faq_parse_response",
        content_blocks=len(response.content),
        stop_reason=response.stop_reason,
        text_length=len(response.text),
        text_preview=response.text[:300] if response.text else "<empty>",
    )

    if not response.text.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM вернул пустой ответ. Возможно, модель не поддерживает данный запрос. Попробуйте ещё раз.",
        )

    raw_text = _extract_json_array(response.text)

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("llm_faq_parse_invalid_json", raw=raw_text[:500])
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="LLM вернул невалидный JSON. Попробуйте переформулировать текст.",
        ) from exc

    if not isinstance(parsed, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="LLM вернул не массив. Ожидался JSON-массив FAQ-пар.",
        )

    repo = BaseRepository(FAQItem, db)
    created_items: list[FAQItemResponse] = []

    for entry in parsed:
        question = entry.get("question", "").strip() if isinstance(entry.get("question"), str) else ""
        answer = entry.get("answer", "").strip() if isinstance(entry.get("answer"), str) else ""
        if not question or not answer:
            continue

        try:
            item = await repo.create(
                question=question,
                answer=answer,
                category=entry.get("category") if isinstance(entry.get("category"), str) else None,
                is_active=True,
                owner_id=current_user.id,
                qualification_script_id=body.qualification_script_id,
            )
            created_items.append(FAQItemResponse.model_validate(item))
        except Exception as exc:
            logger.warning("faq_item_create_failed", question=question[:50], error=str(exc))
            continue

    return created_items


# --- Objection Scripts ---


@router.get("/objections", response_model=PaginatedResponse[ObjectionScriptResponse])
async def list_objection_scripts(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    script_id: uuid.UUID | None = Query(None, description="Filter by qualification script ID"),
) -> PaginatedResponse[ObjectionScriptResponse]:
    """List objection scripts with pagination."""
    repo = BaseRepository(ObjectionScript, db)
    filters = []
    if owner_id is not None:
        filters.append(ObjectionScript.owner_id == owner_id)
    if script_id is not None:
        filters.append(ObjectionScript.qualification_script_id == script_id)
    total = await repo.count(filters)
    offset = (page - 1) * page_size
    items = await repo.get_multi(offset=offset, limit=page_size, filters=filters, order_by=ObjectionScript.created_at.desc())
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedResponse(
        items=[ObjectionScriptResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        pages=pages,
    )


@router.post("/objections", response_model=ObjectionScriptResponse, status_code=status.HTTP_201_CREATED)
async def create_objection_script(
    body: ObjectionScriptCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AdminUser, Depends(get_current_user)],
) -> ObjectionScriptResponse:
    """Create a new objection script."""
    repo = BaseRepository(ObjectionScript, db)
    item = await repo.create(**body.model_dump(), owner_id=current_user.id)
    return ObjectionScriptResponse.model_validate(item)


@router.put("/objections/{objection_id}", response_model=ObjectionScriptResponse)
async def update_objection_script(
    objection_id: uuid.UUID,
    body: ObjectionScriptUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> ObjectionScriptResponse:
    """Update an objection script."""
    repo = BaseRepository(ObjectionScript, db)
    item = await repo.get(objection_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objection script not found")
    _check_resource_owner(item, owner_id, "Objection script not found")
    item = await repo.update(item, **body.model_dump(exclude_unset=True))
    return ObjectionScriptResponse.model_validate(item)


@router.delete("/objections/{objection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_objection_script(
    objection_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> None:
    """Delete an objection script."""
    repo = BaseRepository(ObjectionScript, db)
    item = await repo.get(objection_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objection script not found")
    _check_resource_owner(item, owner_id, "Objection script not found")
    await repo.delete(item)


@router.post("/objections/sync", status_code=status.HTTP_200_OK)
async def sync_objections_to_qdrant(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
) -> dict:
    """Re-sync all objection scripts to Qdrant vector DB."""
    from app.ai.embeddings import EmbeddingsManager
    from app.ai.qdrant_init import sync_objections_to_qdrant as _sync_objections
    from app.config import get_settings
    from qdrant_client import AsyncQdrantClient

    settings = get_settings()
    qdrant = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    embeddings = EmbeddingsManager.get_instance()
    count = await _sync_objections(db, qdrant, embeddings)
    await qdrant.close()
    return {"status": "ok", "synced": count}


@router.post("/objections/parse", response_model=list[ObjectionScriptResponse], status_code=status.HTTP_201_CREATED)
async def parse_objections_from_text(
    body: BulkTextImport,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AdminUser, Depends(get_current_user)],
) -> list[ObjectionScriptResponse]:
    """Parse free-form text into objection scripts using LLM.

    Sends the text to the configured LLM, which returns a JSON array of
    {objection_pattern, response_template} objects. The records are created in the DB and returned.
    """
    try:
        llm = await create_llm_client(db)
    except Exception as exc:
        logger.error("llm_client_create_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Не удалось создать LLM-клиент: {exc}",
        ) from exc

    try:
        response = await llm.send_message(
            messages=[{"role": "user", "content": body.text}],
            system=(
                "Ты -- парсер текста. Разбей предоставленный текст на возражения клиентов и шаблоны ответов. "
                "Верни ТОЛЬКО валидный JSON массив без какого-либо другого текста. "
                'Формат: [{"objection_pattern": "возражение", "response_template": "ответ"}]'
            ),
            max_tokens=16384,
        )
    except Exception as exc:
        logger.error("llm_objections_parse_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка LLM: {exc}",
        ) from exc
    finally:
        await llm.close()

    logger.info(
        "llm_objections_parse_response",
        content_blocks=len(response.content),
        stop_reason=response.stop_reason,
        text_length=len(response.text),
        text_preview=response.text[:300] if response.text else "<empty>",
    )

    if not response.text.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM вернул пустой ответ. Возможно, модель не поддерживает данный запрос. Попробуйте ещё раз.",
        )

    raw_text = _extract_json_array(response.text)

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("llm_objections_parse_invalid_json", raw=raw_text[:500])
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="LLM вернул невалидный JSON. Попробуйте переформулировать текст.",
        ) from exc

    if not isinstance(parsed, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="LLM вернул не массив. Ожидался JSON-массив возражений.",
        )

    repo = BaseRepository(ObjectionScript, db)
    created_items: list[ObjectionScriptResponse] = []

    for entry in parsed:
        objection_pattern = entry.get("objection_pattern", "").strip()
        response_template = entry.get("response_template", "").strip()
        if not objection_pattern or not response_template:
            continue

        item = await repo.create(
            objection_pattern=objection_pattern,
            response_template=response_template,
            category=entry.get("category") or None,
            priority=entry.get("priority", 0) if isinstance(entry.get("priority"), int) else 0,
            is_active=True,
            owner_id=current_user.id,
            qualification_script_id=body.qualification_script_id,
        )
        created_items.append(ObjectionScriptResponse.model_validate(item))

    return created_items
