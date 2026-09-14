"""Tests for provider configuration and deterministic interview mode."""

from unittest.mock import patch

import pytest

from src.models.resolution import parse_resolution_proposal
from src.tools.llm import (
    ProviderConfigurationError,
    call_llm_safe,
    get_llm,
    get_llm_config,
    set_demo_mode_override,
)

CONFIG_VARS = (
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_PROVIDER",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
    "SUPPORTFLOW_DEMO_MODE",
)


def _clear_config(monkeypatch):
    for name in CONFIG_VARS:
        monkeypatch.delenv(name, raising=False)


def test_generic_configuration_has_priority_over_legacy_aliases(monkeypatch):
    _clear_config(monkeypatch)
    monkeypatch.setenv("LLM_API_KEY", "generic-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://generic.example/v1")
    monkeypatch.setenv("LLM_MODEL", "generic-model")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://legacy.example")
    monkeypatch.setenv("DEEPSEEK_MODEL", "legacy-model")

    config = get_llm_config()

    assert config.api_key == "generic-key"
    assert config.base_url == "https://generic.example/v1"
    assert config.model == "generic-model"
    assert config.is_configured is True


def test_legacy_configuration_remains_compatible(monkeypatch):
    _clear_config(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://legacy.example")
    monkeypatch.setenv("DEEPSEEK_MODEL", "legacy-model")

    config = get_llm_config()

    assert config.api_key == "legacy-key"
    assert config.base_url == "https://legacy.example"
    assert config.model == "legacy-model"
    assert config.is_configured is True


def test_demo_mode_can_be_overridden_for_an_interactive_session(monkeypatch):
    _clear_config(monkeypatch)
    monkeypatch.setenv("SUPPORTFLOW_DEMO_MODE", "false")

    assert get_llm_config().demo_mode is False

    set_demo_mode_override(True)
    assert get_llm_config().demo_mode is True

    set_demo_mode_override(False)
    assert get_llm_config().demo_mode is False

    set_demo_mode_override(None)


def test_missing_live_configuration_is_explicit_and_secret_free(monkeypatch):
    _clear_config(monkeypatch)

    with pytest.raises(ProviderConfigurationError, match="LLM_API_KEY") as error:
        call_llm_safe("test prompt")

    assert "DEEPSEEK" not in str(error.value)


def test_demo_mode_does_not_construct_a_model_client(monkeypatch):
    _clear_config(monkeypatch)
    monkeypatch.setenv("SUPPORTFLOW_DEMO_MODE", "true")

    with patch("src.tools.llm.ChatOpenAI") as client:
        triage = call_llm_safe(
            """Classify the following customer support ticket into EXACTLY ONE category.
Subject: Vertrag kündigen
Message: Bitte kündigen Sie meinen Vertrag.
Category:"""
        )
        resolution = call_llm_safe(
            """You are a resolution agent for a controlled customer support system.
Classification: cancellation_request
Respond with a JSON object."""
        )

    client.assert_not_called()
    assert triage == "cancellation_request"
    proposal = parse_resolution_proposal(resolution)
    assert proposal["action_type"] == "process_cancellation"
    assert "Richtlinie" not in proposal["customer_message"]


@pytest.mark.parametrize(
    "classification",
    [
        "technical_issue",
        "refund_request",
        "cancellation_request",
        "billing_inquiry",
        "product_inquiry",
    ],
)
def test_demo_mode_returns_typed_proposals_for_all_categories(monkeypatch, classification):
    _clear_config(monkeypatch)
    monkeypatch.setenv("SUPPORTFLOW_DEMO_MODE", "true")

    response = call_llm_safe(
        "You are a resolution agent for a controlled customer support system.\n"
        f"Classification: {classification}\nRespond with a JSON object."
    )

    proposal = parse_resolution_proposal(response)
    assert proposal["customer_message"]
    assert proposal["subject"]


@pytest.mark.parametrize(
    ("subject", "description", "expected"),
    [
        ("Vertrag kündigen", "Bitte kündigen Sie mein Abonnement.", "cancellation_request"),
        ("Erstattung prüfen", "Ich bitte um eine Rückerstattung.", "refund_request"),
        ("Verbindung fällt aus", "Die technische Verbindung ist gestört.", "technical_issue"),
        ("Frage zur Rechnung", "Bitte prüfen Sie meine Zahlung.", "billing_inquiry"),
        ("Produktinformation", "Welche Funktionen bietet das Produkt?", "product_inquiry"),
    ],
)
def test_demo_mode_classifies_supported_ticket_text(monkeypatch, subject, description, expected):
    _clear_config(monkeypatch)
    monkeypatch.setenv("SUPPORTFLOW_DEMO_MODE", "true")

    result = call_llm_safe(
        """Classify the following customer support ticket into EXACTLY ONE category.
Subject: {subject}
Message: {description}
Category:""".format(subject=subject, description=description)
    )

    assert result == expected


def test_get_llm_uses_resolved_generic_configuration(monkeypatch):
    _clear_config(monkeypatch)
    monkeypatch.setenv("LLM_API_KEY", "generic-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://generic.example/v1")
    monkeypatch.setenv("LLM_MODEL", "generic-model")

    with patch("src.tools.llm.ChatOpenAI") as client:
        get_llm(temperature=0.0)

    client.assert_called_once_with(
        api_key="generic-key",
        base_url="https://generic.example/v1",
        model="generic-model",
        temperature=0.0,
    )
