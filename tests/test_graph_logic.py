"""
Tests für reine Logik-Funktionen im LangGraph-Workflow.
Kein LLM, keine DB — nur Router-Logik und Approval-Prüfung.
"""

import pytest
from src.graph.workflow import (
    AgentState,
    router,
    needs_approval,
)


@pytest.fixture
def base_state():
    """Basis-State für Tests (Single-Ticket)."""
    return AgentState(
        input="",
        ticket=None,
        classification="",
        collected_data={},
        proposed_action={},
        approval="pending",
    )


class TestRouter:
    """router() leitet je nach Klassifikation an den richtigen Node."""

    def test_preisanfrage_geht_zu_data_fetcher(self, base_state):
        base_state["classification"] = "preisanfrage"
        assert router(base_state) == "data_fetcher"

    def test_beschwerde_geht_zu_data_fetcher(self, base_state):
        base_state["classification"] = "beschwerde"
        assert router(base_state) == "data_fetcher"

    def test_kuendigung_geht_direkt_zu_executive(self, base_state):
        base_state["classification"] = "kuendigung"
        assert router(base_state) == "executive_agent"

    def test_sonstiges_geht_direkt_zu_executive(self, base_state):
        base_state["classification"] = "sonstiges"
        assert router(base_state) == "executive_agent"


class TestNeedsApproval:
    """needs_approval() prüft ob Human-in-the-Loop nötig ist."""

    def test_kritisch_true_braucht_human_review(self, base_state):
        base_state["proposed_action"] = {"typ": "angebot", "wert": 20, "kritisch": True}
        assert needs_approval(base_state) == "human_review"

    def test_hoher_rabatt_ohne_flag_auch_kritisch(self, base_state):
        base_state["proposed_action"] = {"typ": "angebot", "wert": 20}
        assert needs_approval(base_state) == "human_review"

    def test_niedriger_rabatt_unkritisch(self, base_state):
        base_state["proposed_action"] = {"typ": "info", "wert": 5, "kritisch": False}
        assert needs_approval(base_state) == "execute_action"

    def test_kritisch_false_trotz_hohem_wert(self, base_state):
        base_state["proposed_action"] = {"typ": "angebot", "wert": 20, "kritisch": False}
        assert needs_approval(base_state) == "execute_action"

    def test_leeres_action_dict(self, base_state):
        base_state["proposed_action"] = {}
        assert needs_approval(base_state) == "execute_action"

    def test_grenze_bei_15(self, base_state):
        base_state["proposed_action"] = {"typ": "angebot", "wert": 15}
        assert needs_approval(base_state) == "execute_action"

    def test_grenze_bei_16(self, base_state):
        base_state["proposed_action"] = {"typ": "angebot", "wert": 16}
        assert needs_approval(base_state) == "human_review"