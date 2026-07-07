"""
LLM-Konfiguration — DeepSeek via OpenAI-kompatibler API
=======================================================
Nutzt python-dotenv für API-Key aus .env
"""

import os
import re
import json
import time
import logging
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

load_dotenv()


def get_llm(model: str | None = None, temperature: float = 0.1) -> ChatOpenAI:
    """Erzeugt einen ChatOpenAI-Client, der auf DeepSeek zeigt."""
    return ChatOpenAI(
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        model=model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        temperature=temperature,
    )


def call_llm_safe(prompt: str, temperature: float = 0.0, max_retries: int = 3) -> str | None:
    """
    Ruft DeepSeek auf mit automatischen Retry-Versuchen bei Fehlern.

    - Network-Error (Timeout, DNS) → bis zu 3 Versuche mit 2s/5s/10s Pause
    - Auth-Error (falscher Key)   → sofort abbrechen (kein Retry sinnvoll)
    - Rate-Limit (429)            → 10s warten, dann erneut
    - API-Server-Error (5xx)      → Retry, dann None zurück
    - Wenn alle Versuche fehlschlagen → None (kein Crash!)

    Gibt bei Erfolg den Antwort-String zurück, bei Fehlschlag None.
    """
    llm = get_llm(temperature=temperature)

    for attempt in range(1, max_retries + 1):
        try:
            resp = llm.invoke(prompt)
            if resp is None or not hasattr(resp, "content"):
                logger.warning(f"LLM: Antwort war leer (Versuch {attempt})")
                continue
            return resp.content.strip()

        except Exception as e:
            err_name = type(e).__name__
            err_msg = str(e)

            # Auth-Fehler → sofort abbrechen (bringt nichts zu retryen)
            if "auth" in err_name.lower() or "authentication" in err_msg.lower() or "401" in err_msg:
                logger.error(f"LLM: Auth-Fehler — API-Key ungültig? {err_msg[:100]}")
                return None

            # Rate-Limit (429) → länger warten
            if "rate" in err_name.lower() or "429" in err_msg or "too many" in err_msg.lower():
                wait = 10
                logger.warning(f"LLM: Rate-Limit (Versuch {attempt}/{max_retries}), warte {wait}s...")
                time.sleep(wait)
                continue

            # Letzter Versuch fehlgeschlagen → aufgeben
            if attempt == max_retries:
                logger.error(f"LLM: Aufruf fehlgeschlagen nach {max_retries} Versuchen: {err_name}: {err_msg[:150]}")
                return None

            # Netzwerk/Timeout-Fehler → exponentiell warten
            wait = 2 ** attempt
            logger.warning(f"LLM: {err_name} (Versuch {attempt}/{max_retries}), warte {wait}s...")
            time.sleep(wait)

    return None  # Sollte nie erreicht werden, aber sicher ist sicher


def extract_json(text: str) -> dict:
    """
    Extrahiert zuverlässig JSON aus einer LLM-Antwort.

    Handelt:
    - Markdown-Code-Blöcke (```json ... ```, ``` ... ```)
    - Plain JSON ohne Code-Block
    - Mehrere Code-Blöcke (nimmt den ersten mit JSON-Inhalt)
    - JSON mit führendem/nachgestelltem Text
    """
    # 1) Versuche JSON-Code-Block (```json ... ```)
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass  # Fall-through zu Versuch 2

    # 2) Versuche direktes JSON-Objekt (geschweifte Klammern)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        candidate = match.group(0).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # 3) Nichts gefunden → Fehler
    raise json.JSONDecodeError(
        f"Kein gültiges JSON in LLM-Antwort gefunden:\n{text[:300]}", text, 0
    )


# Kurztest
if __name__ == "__main__":
    llm = get_llm()
    resp = llm.invoke("Antworte nur mit 'OK' — funktioniert?")
    print(f"✅ LLM antwortet: {resp.content}")
