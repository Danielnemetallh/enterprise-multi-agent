"""
LLM-Konfiguration — DeepSeek via OpenAI-kompatibler API
=======================================================
Nutzt python-dotenv für API-Key aus .env
"""

import os
import re
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_llm(model: str | None = None, temperature: float = 0.1) -> ChatOpenAI:
    """Erzeugt einen ChatOpenAI-Client, der auf DeepSeek zeigt."""
    return ChatOpenAI(
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        model=model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        temperature=temperature,
    )


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
