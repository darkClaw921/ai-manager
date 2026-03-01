"""Tests for prompt building functions."""

import pytest

from app.ai.prompts import (
    build_greeting,
    build_lead_info,
    build_rag_context,
    build_stage_instructions,
    LEAD_INFO_EMPTY,
    QUALIFICATION_STAGE_PROMPTS,
)


class TestBuildGreeting:
    """Tests for build_greeting()."""

    def test_greeting_without_name(self):
        greeting = build_greeting()
        assert "Здравствуйте!" in greeting
        assert "Ассистент" in greeting

    def test_greeting_with_name(self):
        greeting = build_greeting("Иван")
        assert "Иван" in greeting
        assert "Здравствуйте" in greeting

    def test_greeting_with_none_name(self):
        greeting = build_greeting(None)
        assert "Здравствуйте!" in greeting


class TestBuildLeadInfo:
    """Tests for build_lead_info()."""

    def test_empty_lead_info(self):
        result = build_lead_info()
        assert result == LEAD_INFO_EMPTY

    def test_lead_info_with_name(self):
        result = build_lead_info(
            lead_name="Иван",
            lead_status="qualifying",
            qualification_stage="budget_check",
            interest_score=50,
        )
        assert "Иван" in result
        assert "qualifying" in result
        assert "budget_check" in result
        assert "50/100" in result

    def test_lead_info_with_qualification_data(self):
        result = build_lead_info(
            lead_name="Иван",
            qualification_data={"needs": "Website redesign", "budget": "100k"},
        )
        assert "Website redesign" in result
        assert "100k" in result

    def test_lead_info_no_name_with_data(self):
        result = build_lead_info(
            qualification_data={"needs": "Help"},
        )
        assert "Не указано" in result
        assert "Help" in result

    def test_lead_info_boolean_data_filtered(self):
        result = build_lead_info(
            lead_name="Test",
            qualification_data={"needs_discovery": True, "budget": "50k"},
        )
        # Boolean values should be filtered
        assert "needs_discovery" not in result
        assert "50k" in result


class TestBuildStageInstructions:
    """Tests for build_stage_instructions()."""

    def test_all_stages_have_templates(self):
        stages = [
            "initial", "needs_discovery", "budget_check",
            "timeline_check", "decision_maker", "qualified",
            "booking_offer", "booked", "handed_off",
        ]
        for stage in stages:
            result = build_stage_instructions(stage)
            assert isinstance(result, str)

    def test_needs_discovery_includes_expected_info(self):
        result = build_stage_instructions(
            stage="needs_discovery",
            expected_info="Customer goals",
        )
        assert "Customer goals" in result

    def test_needs_discovery_with_script_prompt(self):
        result = build_stage_instructions(
            stage="needs_discovery",
            script_prompt="Ask about goals",
        )
        assert "Ask about goals" in result

    def test_unknown_stage_returns_empty(self):
        result = build_stage_instructions("nonexistent_stage")
        assert result == ""

    def test_initial_stage_prompt(self):
        result = build_stage_instructions("initial")
        assert "Приветствие" in result


class TestBuildRagContext:
    """Tests for build_rag_context()."""

    def test_empty_context(self):
        result = build_rag_context()
        assert result == ""

    def test_faq_only(self):
        faq_items = [
            {"question": "Сколько стоит?", "answer": "От 50 тысяч рублей."},
        ]
        result = build_rag_context(faq_items=faq_items)
        assert "Сколько стоит?" in result
        assert "50 тысяч" in result
        assert "FAQ" in result or "вопрос" in result.lower()

    def test_objections_only(self):
        objections = [
            {"pattern": "Дорого", "response": "Давайте обсудим бюджет"},
        ]
        result = build_rag_context(objections=objections)
        assert "Дорого" in result
        assert "обсудим бюджет" in result

    def test_faq_and_objections(self):
        faq_items = [{"question": "Q", "answer": "A"}]
        objections = [{"pattern": "P", "response": "R"}]
        result = build_rag_context(faq_items=faq_items, objections=objections)
        assert "Q" in result
        assert "A" in result
        assert "P" in result
        assert "R" in result

    def test_multiple_faq_items(self):
        faq_items = [
            {"question": "Q1", "answer": "A1"},
            {"question": "Q2", "answer": "A2"},
        ]
        result = build_rag_context(faq_items=faq_items)
        assert "Q1" in result
        assert "Q2" in result

    def test_empty_lists(self):
        result = build_rag_context(faq_items=[], objections=[])
        assert result == ""
