"""Provider-neutral model access for the SupportFlow workflow."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

load_dotenv()

GENERIC_API_KEY = "LLM_API_KEY"
GENERIC_BASE_URL = "LLM_BASE_URL"
GENERIC_MODEL = "LLM_MODEL"
DEMO_MODE = "SUPPORTFLOW_DEMO_MODE"


class ProviderConfigurationError(ValueError):
    """Raised when live model configuration is incomplete."""


@dataclass(frozen=True)
class LLMConfig:
    provider: str | None
    api_key: str | None
    base_url: str | None
    model: str | None
    demo_mode: bool

    @property
    def is_configured(self) -> bool:
        return all((self.api_key, self.base_url, self.model))


def _setting(generic_name: str, legacy_name: str) -> str | None:
    return (os.getenv(generic_name) or os.getenv(legacy_name) or "").strip() or None


def _env_flag(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def get_llm_config() -> LLMConfig:
    """Resolve generic settings, with legacy provider aliases as fallback."""
    return LLMConfig(
        provider=(os.getenv("LLM_PROVIDER") or "").strip() or None,
        api_key=_setting(GENERIC_API_KEY, "DEEPSEEK_API_KEY"),
        base_url=_setting(GENERIC_BASE_URL, "DEEPSEEK_BASE_URL"),
        model=_setting(GENERIC_MODEL, "DEEPSEEK_MODEL"),
        demo_mode=_env_flag(DEMO_MODE),
    )


def _require_live_config(config: LLMConfig) -> None:
    missing = [
        name
        for name, value in (
            (GENERIC_API_KEY, config.api_key),
            (GENERIC_BASE_URL, config.base_url),
            (GENERIC_MODEL, config.model),
        )
        if not value
    ]
    if missing:
        raise ProviderConfigurationError(
            "Live model configuration is incomplete. Set: " + ", ".join(missing)
        )


def get_llm(model: str | None = None, temperature: float = 0.1) -> ChatOpenAI:
    """Create an OpenAI-compatible client from the resolved live configuration."""
    config = get_llm_config()
    if config.demo_mode:
        raise ProviderConfigurationError(
            "Live model client is unavailable while SUPPORTFLOW_DEMO_MODE is enabled"
        )
    _require_live_config(config)
    return ChatOpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        model=model or config.model,
        temperature=temperature,
    )


def _demo_category(prompt: str) -> str:
    ticket_match = re.search(
        r"Subject:\s*(.*?)\s*Message:\s*(.*?)\s*Category:",
        prompt,
        re.IGNORECASE | re.DOTALL,
    )
    ticket_text = " ".join(ticket_match.groups()).lower() if ticket_match else prompt.lower()
    keyword_groups = (
        (
            "cancellation_request",
            ("cancel", "cancellation", "kündig", "subscription", "vertrag"),
        ),
        ("refund_request", ("refund", "erstatt", "charge reversal", "rückerstatt")),
        (
            "technical_issue",
            (
                "outage",
                "technical",
                "error",
                "bug",
                "defect",
                "down",
                "verbindung",
                "störung",
                "ausfall",
                "getrennt",
            ),
        ),
        (
            "billing_inquiry",
            ("invoice", "billing", "payment", "charge", "rechnung", "zahlung", "abbuchung"),
        ),
    )
    for category, keywords in keyword_groups:
        if any(keyword in ticket_text for keyword in keywords):
            return category
    return "product_inquiry"


def _demo_resolution(prompt: str) -> str:
    match = re.search(r"Classification:\s*([a-z_]+)", prompt, re.IGNORECASE)
    classification = match.group(1).lower() if match else "product_inquiry"
    proposals = {
        "technical_issue": {
            "action_type": "send_apology",
            "discount_percent": 0,
            "subject": "Ihre technische Anfrage",
            "customer_message": "Es tut uns leid, dass Sie technische Schwierigkeiten haben. Wir prüfen den Vorgang und melden uns schnellstmöglich bei Ihnen.",
            "business_reason": "Acknowledge a technical service issue",
            "alternatives": [],
        },
        "refund_request": {
            "action_type": "offer_discount",
            "discount_percent": 10,
            "subject": "Ihre Erstattungsanfrage",
            "customer_message": "Vielen Dank für Ihre Nachricht. Wir möchten Ihnen als Kulanz einen Rabatt von 10 % anbieten.",
            "business_reason": "Offer a controlled goodwill response",
            "alternatives": [],
        },
        "cancellation_request": {
            "action_type": "process_cancellation",
            "discount_percent": 0,
            "subject": "Ihre Kündigungsanfrage",
            "customer_message": "Vielen Dank für Ihre Nachricht. Wir prüfen Ihre Kündigungsanfrage und melden uns mit den nächsten Schritten.",
            "business_reason": "Process a customer cancellation request",
            "alternatives": [],
        },
        "billing_inquiry": {
            "action_type": "provide_information",
            "discount_percent": 0,
            "subject": "Ihre Rechnungsanfrage",
            "customer_message": "Vielen Dank für Ihre Nachricht. Wir prüfen die gewünschten Rechnungsinformationen und melden uns bei Ihnen.",
            "business_reason": "Provide billing information",
            "alternatives": [],
        },
        "product_inquiry": {
            "action_type": "provide_information",
            "discount_percent": 0,
            "subject": "Ihre Produktanfrage",
            "customer_message": "Vielen Dank für Ihre Anfrage. Wir senden Ihnen die gewünschten Informationen zu unserem Produkt.",
            "business_reason": "Provide product information",
            "alternatives": [],
        },
    }
    return json.dumps(proposals.get(classification, proposals["product_inquiry"]), ensure_ascii=False)


def _demo_response(prompt: str) -> str:
    if "Classify the following customer support ticket" in prompt:
        return _demo_category(prompt)
    if "You are a resolution agent for a controlled customer support system" in prompt:
        return _demo_resolution(prompt)
    raise ProviderConfigurationError("No deterministic demo response is defined for this prompt")


def call_llm_safe(prompt: str, temperature: float = 0.0, max_retries: int = 3) -> str | None:
    """Call the configured model or the explicit deterministic demo provider."""
    if get_llm_config().demo_mode:
        try:
            return _demo_response(prompt)
        except ProviderConfigurationError as exc:
            logger.error("Demo provider configuration error: %s", exc)
            return None

    try:
        llm = get_llm(temperature=temperature)
    except ProviderConfigurationError as exc:
        logger.error("Model provider configuration error: %s", exc)
        raise

    for attempt in range(1, max_retries + 1):
        try:
            resp = llm.invoke(prompt)
            if resp is None or not hasattr(resp, "content"):
                logger.warning("LLM: Antwort war leer (Versuch %s)", attempt)
                continue
            return resp.content.strip()

        except Exception as exc:
            err_name = type(exc).__name__
            err_msg = str(exc)

            if "auth" in err_name.lower() or "authentication" in err_msg.lower() or "401" in err_msg:
                logger.error("LLM: Auth-Fehler — API-Key ungültig? %s", err_msg[:100])
                return None

            if "rate" in err_name.lower() or "429" in err_msg or "too many" in err_msg.lower():
                wait = 10
                logger.warning(
                    "LLM: Rate-Limit (Versuch %s/%s), warte %ss...",
                    attempt,
                    max_retries,
                    wait,
                )
                time.sleep(wait)
                continue

            if attempt == max_retries:
                logger.error(
                    "LLM: Aufruf fehlgeschlagen nach %s Versuchen: %s: %s",
                    max_retries,
                    err_name,
                    err_msg[:150],
                )
                return None

            wait = 2**attempt
            logger.warning(
                "LLM: %s (Versuch %s/%s), warte %ss...",
                err_name,
                attempt,
                max_retries,
                wait,
            )
            time.sleep(wait)

    return None


def extract_json(text: str) -> dict:
    """Extract JSON from a model response with optional Markdown wrapping."""
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        candidate = match.group(0).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    raise json.JSONDecodeError(
        f"Kein gültiges JSON in LLM-Antwort gefunden:\n{text[:300]}", text, 0
    )


if __name__ == "__main__":
    if get_llm_config().demo_mode:
        print(_demo_response("Classify the following customer support ticket: Product pricing"))
        raise SystemExit(0)
    llm = get_llm()
    resp = llm.invoke("Antworte nur mit 'OK' — funktioniert?")
    print(f"✅ LLM antwortet: {resp.content}")
