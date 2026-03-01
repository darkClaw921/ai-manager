"""Qualification script, FAQ item, and objection script schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# --- Qualification Script ---


class QualificationScriptCreate(BaseModel):
    """Create qualification script request."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    stages: list[dict[str, Any]] = Field(default_factory=list, description="List of qualification stages")
    is_active: bool = True
    score_config: dict[str, int] | None = None


class QualificationScriptUpdate(BaseModel):
    """Update qualification script request. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    stages: list[dict[str, Any]] | None = None
    is_active: bool | None = None
    score_config: dict[str, int] | None = None


class QualificationScriptResponse(BaseModel):
    """Qualification script response."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None = None
    stages: list[dict[str, Any]] | None = None
    is_active: bool
    score_config: dict[str, int] | None = None
    created_at: datetime
    updated_at: datetime | None = None


# --- FAQ Item ---


class FAQItemCreate(BaseModel):
    """Create FAQ item request."""

    question: str = Field(..., min_length=1, description="FAQ question")
    answer: str = Field(..., min_length=1, description="FAQ answer")
    category: str | None = Field(None, max_length=255, description="FAQ category")
    keywords: list[str] | None = Field(None, description="Keywords for search")
    is_active: bool = True
    qualification_script_id: uuid.UUID | None = None


class FAQItemUpdate(BaseModel):
    """Update FAQ item request. All fields optional."""

    question: str | None = Field(None, min_length=1)
    answer: str | None = Field(None, min_length=1)
    category: str | None = Field(None, max_length=255)
    keywords: list[str] | None = None
    is_active: bool | None = None
    qualification_script_id: uuid.UUID | None = None


class FAQItemResponse(BaseModel):
    """FAQ item response."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    question: str
    answer: str
    category: str | None = None
    keywords: list[str] | None = None
    is_active: bool
    qualification_script_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None


# --- Objection Script ---


class ObjectionScriptCreate(BaseModel):
    """Create objection script request."""

    objection_pattern: str = Field(..., min_length=1, description="Objection pattern text")
    response_template: str = Field(..., min_length=1, description="Response template")
    category: str | None = Field(None, max_length=255)
    priority: int = Field(0, ge=0, description="Priority (higher = more important)")
    is_active: bool = True
    qualification_script_id: uuid.UUID | None = None


class ObjectionScriptUpdate(BaseModel):
    """Update objection script request. All fields optional."""

    objection_pattern: str | None = Field(None, min_length=1)
    response_template: str | None = Field(None, min_length=1)
    category: str | None = Field(None, max_length=255)
    priority: int | None = Field(None, ge=0)
    is_active: bool | None = None
    qualification_script_id: uuid.UUID | None = None


class ObjectionScriptResponse(BaseModel):
    """Objection script response."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    objection_pattern: str
    response_template: str
    category: str | None = None
    priority: int = 0
    is_active: bool
    qualification_script_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None


# --- Bulk Text Import ---


class BulkTextImport(BaseModel):
    """Request body for bulk text import (FAQ or objections)."""

    text: str = Field(..., min_length=10, description="Текст для парсинга в записи")
    qualification_script_id: uuid.UUID | None = None


class ScoreConfigUpdate(BaseModel):
    """Request body for updating qualification script score weights."""

    score_config: dict[str, int] = Field(
        ..., description='Веса этапов, например {"needs_discovery": 40, "budget_check": 30}'
    )
