# Single-Ticket Verarbeitung + Logging-Fix

> **Für Coding-Agent:** Claude Code (CLI) empfohlen — siehe Empfehlung unten.
> Führe Tasks 1→7 sequentiell aus, nach jedem Task commit.

**Goal:** Workflow von Batch zurück auf Single-Ticket umbauen, Routing wieder via Classification, httpx-Noise aus dem Output entfernen.

**Architecture:** 1 Ticket pro Graph-Invocation. Triage klassifiziert → Router leitet zu data_fetcher ODER executive → HITL → Execute. Kein Batch mehr.

**Tech Stack:** Python 3.11, LangGraph, DeepSeek, SQLite, pytest

**Aktueller Problem-Zustand (muss rückgebaut werden):**
- `workflow.py`: Batch-State mit `tickets[]`, `collected_data: dict[str,dict]`, `proposed_actions: dict[str,dict]`, linearer Graph ohne Router
- `data_fetcher_agent.py`: Hat `run_data_fetcher_batch()` (unnötig), `_fetch_for_ticket()` (gut), `run_data_fetcher` (gut, alte API)
- `executive_agent.py`: Hat `run_executive_batch()` (unnötig), `run_executive` (gut) + `_build_action` (gut, neuer Prompt mit ticket_betreff)
- `logger.py`: Keine Filterung von httpx-Logs
- `test_graph_logic.py`: Batch-Tests, kein `router`

---

## Task 1: `workflow.py` — State + Nodes + Graph zurücksetzen

**Objective:** Single-Ticket State, Router-Conditional-Edge, keine Batch-Strukturen.

**Files:**
- Modify: `src/graph/workflow.py` (komplett, 311 Zeilen)

**Step 1: Schreibe `workflow.py` komplett neu**

Ersetze den gesamten Inhalt durch folgenden Code:

```python
"""
Enterprise Multi-Agent System — LangGraph Workflow
====================================================
Nodes:   triage → data_fetcher / executive → human_review → execute
Edges:   conditional routing via router() & needs_approval()
State:   SINGLE-TICKET — 1 Ticket pro Durchlauf
LLM:     DeepSeek (via src.tools.llm)
DB:      SQLite Mock-DB (via src.tools.db_tools)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import logging
from typing import Literal, TypedDict
from langgraph.graph import StateGraph, END

from src.agents.triage_agent import classify_ticket
from src.agents.data_fetcher_agent import run_data_fetcher
from src.agents.executive_agent import run_executive
from src.tools.llm import get_llm, extract_json
from src.tools.db_tools import query_open_tickets

logger = logging.getLogger(__name__)


# ─────────────────────────────── S T A T E ───────────────────────────────

class AgentState(TypedDict):
    """State für SINGLE-TICKET: 1 Ticket pro Graph-Durchlauf."""
    input: str                 # Ticket-ID (optional) — z.B. "28"
    ticket: dict | None        # Das aktuell verarbeitete Ticket
    classification: str        # "beschwerde" | "kuendigung" | "preisanfrage" | "sonstiges"
    collected_data: dict       # Daten aus DB für DIESES Ticket
    proposed_action: dict      # Lösungsvorschlag vom Executive
    approval: str              # "pending" | "approved" | "rejected"


# ─────────────────────────────── N O D E S ───────────────────────────────

def triage_agent(state: AgentState) -> AgentState:
    """Agent 1: Wählt EIN Ticket aus und klassifiziert es via DeepSeek."""
    try:
        tickets = query_open_tickets()
        if not tickets:
            logger.warning("Keine offenen Tickets gefunden")
            return {**state, "classification": "sonstiges", "ticket": None}

        # Ticket-Auswahl: per input(ID) oder Priorität
        if state["input"]:
            # Exakte Ticket-ID (auch wenn's erledigt ist)
            ticket = next(
                (t for t in tickets if str(t["id"]) == state["input"].strip()),
                tickets[0]
            )
        else:
            # Priorität: kuendigung > beschwerde > preisanfrage > sonstiges
            priority = {"kuendigung": 0, "beschwerde": 1, "preisanfrage": 2, "sonstiges": 3}
            ticket = min(tickets, key=lambda t: priority.get(t.get("typ", "sonstiges"), 99))

        classification = classify_ticket(ticket["betreff"], ticket["nachricht"])
        logger.info(f"Triage: [{classification}] #{ticket['id']} {ticket['betreff']}")
        return {**state, "classification": classification, "ticket": ticket}
    except Exception as e:
        logger.error(f"Triage-Agent Fehler: {e}")
        return {**state, "classification": "sonstiges", "ticket": None}


def data_fetcher(state: AgentState) -> AgentState:
    """Agent 2: Holt Daten aus DB — je nach Klassifikation (via Data-Fetcher Agent)."""
    try:
        tickets = [state["ticket"]] if state.get("ticket") else query_open_tickets()
        collected = run_data_fetcher(state["classification"], tickets)
        logger.info(f"Data-Fetcher: {len(collected)} Datenkategorien gesammelt")
        return {**state, "collected_data": collected}
    except Exception as e:
        logger.error(f"Data-Fetcher Fehler: {e}")
        return {**state, "collected_data": {}}


def executive_agent(state: AgentState) -> AgentState:
    """Agent 3: Erstellt Lösungsvorschlag (via Executive-Agent / DeepSeek)."""
    try:
        action = run_executive(state["classification"], state["collected_data"])
        return {**state, "proposed_action": action}
    except Exception as e:
        logger.error(f"Executive-Agent Fehler: {e}")
        return {**state, "proposed_action": {
            "typ": "info", "wert": 0,
            "betreff": "Ihre Anfrage",
            "nachricht": "Wir konnten Ihre Anfrage leider nicht bearbeiten. Bitte kontaktieren Sie uns erneut.",
            "kritisch": False,
        }}


def human_review(state: AgentState) -> AgentState:
    """Wartet auf menschliche Freigabe (Human-in-the-Loop) — mit 'eigen'-Option."""
    while True:
        action = state["proposed_action"]

        print(f"\n 🚷 FREIGABE ERFORDERLICH - kritische Aktion!\n")
        print(f" ─────────────────────────────────────")
        print(f"  Typ: {action.get('typ', '?')} ")
        print(f"  Rabatt: {action.get('wert', 0)}%")
        print(f"  Betreff: {action.get('betreff', '?')}")
        print(f"  Nachricht: {action.get('nachricht', '?')}")
        print(f"  ─────────────────────────────────────")

        inp = input("  Aktion freigeben? (ja/nein/eigen): ").strip().lower()

        if inp in ("ja", "yes"):
            state["approval"] = "approved"
            logger.info("Aktion freigegeben")
            return state

        elif inp in ("nein", "no"):
            state["approval"] = "rejected"
            logger.info("Aktion abgelehnt")
            return state

        elif inp == "eigen":
            print(f"\n  🤖 KI erstellt Alternativ-Vorschlag...")
            prompt = f"""The human reviewer rejected this proposed action:
{json.dumps(action, indent=2, ensure_ascii=False)}

Based on the SAME customer data, suggest a DIFFERENT approach.
Think creatively — what else could we offer the customer?

Respond with a JSON object:
{{
    "typ": "angebot|entschuldigung|info|storno",
    "wert": <number 0-30>,
    "betreff": "<short subject in German>",
    "nachricht": "<alternative response in German, max 2 Sätze>",
    "kritisch": true/false
}}"""
            try:
                llm = get_llm(temperature=0.3)
                resp = llm.invoke(prompt)
                new_action = extract_json(resp.content)
                new_action.setdefault("typ", "info")
                new_action.setdefault("wert", 0)
                new_action.setdefault("betreff", "Alternativ-Vorschlag")
                new_action.setdefault("nachricht", "Wir haben einen neuen Vorschlag für Sie.")
                new_action.setdefault("kritisch", new_action.get("wert", 0) > 15)

                state["proposed_action"] = new_action
                logger.info(f"Neuer Alternativ-Vorschlag: {new_action['typ']} | {new_action.get('betreff', '?')}")

            except Exception as e:
                logger.error(f"Alternativ-Vorschlag fehlgeschlagen: {e}")
                print(f"  ⚠️ Konnte keinen Alternativ-Vorschlag erstellen: {e}")
                print("  → Bitte nochmal eingeben (ja/nein/eigen)")
        else:
            print("  ⚠️ Bitte 'ja', 'nein' oder 'eigen' eingeben.")


def execute_action(state: AgentState) -> AgentState:
    """Führt die Aktion aus."""
    action = state["proposed_action"]
    kunde = state["collected_data"].get("kunde", {})

    if state["approval"] == "rejected":
        logger.warning(
            f"Aktion abgelehnt | Typ: {action.get('typ', '?')} | "
            f"Rabatt: {action.get('wert', 0)}% | Kunde: {kunde.get('name', '?')}"
        )
        return state

    logger.info(
        f"Aktion ausgeführt | Typ: {action.get('typ', '?')} | "
        f"Rabatt: {action.get('wert', 0)}% | "
        f"Kunde: {kunde.get('name', '?')} ({kunde.get('status', '?')})"
    )
    logger.info(f"Nachricht: {action.get('nachricht', '?')}")
    return state


# ─────────────────────── C O N D I T I O N A L   E D G E S ───────────────────────

def router(state: AgentState) -> Literal["data_fetcher", "executive_agent"]:
    """Leitet je nach Klassifikation an den richtigen Agenten."""
    if state["classification"] in ("preisanfrage", "beschwerde"):
        return "data_fetcher"        # → Agent 2: Daten holen
    return "executive_agent"         # → Agent 3: Direkt Lösung


def needs_approval(state: AgentState) -> Literal["human_review", "execute_action"]:
    """Prüft ob Human-in-the-Loop nötig ist (vom Executive gesetztes 'kritisch'-Flag)."""
    action = state["proposed_action"]
    kritisch = action.get("kritisch", action.get("wert", 0) > 15)
    if kritisch:
        return "human_review"       # Kritisch → Manager-Freigabe
    return "execute_action"         # Unkritisch → direkt ausführen


# ─────────────────────── G R A P H   B A U E N ───────────────────────

def build_graph() -> StateGraph:
    """Erstellt den LangGraph-Graphen (Single-Ticket)."""
    workflow = StateGraph(AgentState)

    # Nodes registrieren
    workflow.add_node("triage_agent", triage_agent)
    workflow.add_node("data_fetcher", data_fetcher)
    workflow.add_node("executive_agent", executive_agent)
    workflow.add_node("human_review", human_review)
    workflow.add_node("execute_action", execute_action)

    # Entry Point
    workflow.set_entry_point("triage_agent")

    # Kanten (Edges)
    workflow.add_conditional_edges(
        "triage_agent",
        router,
        {"data_fetcher": "data_fetcher", "executive_agent": "executive_agent"}
    )
    workflow.add_edge("data_fetcher", "executive_agent")
    workflow.add_conditional_edges(
        "executive_agent",
        needs_approval,
        {"human_review": "human_review", "execute_action": "execute_action"}
    )
    workflow.add_edge("human_review", "execute_action")
    workflow.add_edge("execute_action", END)

    return workflow.compile()


# ─────────────────────────────── M A I N ───────────────────────────────

if __name__ == "__main__":
    from src.tools.logger import setup_logging
    setup_logging()

    # httpx-Logs unterdrücken (sonst sieht der Nutzer jeden API-Call)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    graph = build_graph()
    logger.info("LangGraph compiled! (Single-Ticket-Modus)")

    try:
        result = graph.invoke({
            "input": "",
            "ticket": None,
            "classification": "",
            "collected_data": {},
            "proposed_action": {},
            "approval": "pending",
        })
        logger.info("Graph-Durchlauf abgeschlossen")

        ticket = result.get("ticket")
        action = result.get("proposed_action", {})
        kunde = result.get("collected_data", {}).get("kunde", {})

        print("\n" + "=" * 60)
        print(" 📋 ABSCHLUSSBERICHT")
        print("=" * 60)
        if ticket:
            print(f"  Ticket #{ticket['id']} [{result.get('classification', '?')}]")
            print(f"  Kunde: {kunde.get('name', '?')} ({kunde.get('status', '?')})")
            print(f"  Betreff: {ticket['betreff']}")
            print(f"  Status: {'✅ Genehmigt' if result.get('approval') == 'approved' else '❌ Abgelehnt'}")
            print(f"  Aktion: {action.get('typ', '?')} | Rabatt: {action.get('wert', 0)}%")
            print(f"  Antwort: {action.get('nachricht', '')}")
        else:
            print("  Kein Ticket verarbeitet.")
        print()

    except Exception as e:
        logger.error(f"Graph-Durchlauf fehlgeschlagen: {e}")
        import traceback
        traceback.print_exc()
```

**Step 2: Teste dass der Graph kompiliert**

```bash
cd /c/Users/Dania/OneDrive/Documents/Coding/Github/Enterprise-Projekt
python -c "from src.graph.workflow import build_graph; g = build_graph(); print('✅', g.nodes.keys())"
```

Expected: `✅ dict_keys(['__start__', 'triage_agent', 'data_fetcher', 'executive_agent', 'human_review', 'execute_action'])`

**Step 3: Commit**

```bash
git add src/graph/workflow.py
git commit -m "fix: workflow zurueck zu Single-Ticket + Router + httpx-Logs unterdrueckt"
```

---

## Task 2: `executive_agent.py` — `run_executive_batch` entfernen

**Objective:** Nur `run_executive` (Single-Ticket) behalten, Batch-Funktion löschen. Der Prompt mit `ticket_betreff`/`ticket_nachricht` bleibt erhalten.

**Files:**
- Modify: `src/agents/executive_agent.py` (166 Zeilen → ~130)

**Step 1: Lösche `run_executive_batch()` und passe Docstrings an**

Entferne die gesamte `run_executive_batch`-Funktion (Zeilen 134-166). Passe den Docstring von `run_executive` an:

```python
def run_executive(classification: str, collected_data: dict) -> dict:
    """
    Erstellt einen Lösungsvorschlag per DeepSeek für EIN Ticket.

    Das ist der wichtigste Agent im System – er entscheidet WAS passieren soll.
    Der Data-Fetcher liefert nur die Informationen, aber der Executive
    bestimmt die Aktion.

    Der Prompt enthält jetzt ticket_betreff und ticket_nachricht,
    damit die Antwort kundenbezogen ist (nicht generisch).

    Parameter:
    - classification: Die Ticket-Klasse vom Triage-Agent
    - collected_data: Alle Daten vom Data-Fetcher (inkl. "ticket"-Key)

    Rückgabe:
    - dict mit: typ, wert, betreff, nachricht, kritisch
    """
    ticket_info = collected_data.get("ticket", {})
    return _build_action(classification, collected_data, ticket_info)
```

**Step 2: Teste dass die Imports funktionieren**

```bash
cd /c/Users/Dania/OneDrive/Documents/Coding/Github/Enterprise-Projekt
python -c "from src.agents.executive_agent import run_executive; print('✅')"
```

Expected: `✅`

**Step 3: Commit**

```bash
git add src/agents/executive_agent.py
git commit -m "fix: run_executive_batch entfernt, Single-Ticket-Signatur bleibt"
```

---

## Task 3: `data_fetcher_agent.py` — `run_data_fetcher_batch` entfernen

**Objective:** `run_data_fetcher_batch` löschen, nur `run_data_fetcher` (alte Signatur) + `_fetch_for_ticket` behalten.

**Files:**
- Modify: `src/agents/data_fetcher_agent.py` (124 Zeilen → ~90)

**Step 1: Lösche `run_data_fetcher_batch()` und passe `run_data_fetcher` an**

Entferne die gesamte `run_data_fetcher_batch`-Funktion (Zeilen 104-124). Passe `run_data_fetcher` an — mach es zum primären Weg (kein Deprecation-Warning mehr):

```python
def run_data_fetcher(classification: str, tickets: list) -> dict:
    """
    Holt Daten aus DB für EIN Ticket — je nach Klassifikation.
    
    Nutzt die neue _fetch_for_ticket()-Logik (Klassifikation aus Ticket oder Parameter),
    inkl. ticket-Info für den Executive-Prompt.
    """
    if not tickets:
        return {"error": "Keine offenen Tickets gefunden"}
    ticket = dict(tickets[0])  # Kopie
    ticket.setdefault("classification", classification)  # aus Parameter injizieren
    return _fetch_for_ticket(ticket)
```

**Step 2: Teste alte + neue Tests**

```bash
cd /c/Users/Dania/OneDrive/Documents/Coding/Github/Enterprise-Projekt
python -c "from src.agents.data_fetcher_agent import run_data_fetcher; print('✅')"
pytest tests/test_data_fetcher_agent.py -v --tb=short
```

Expected: 5 passed

**Step 3: Commit**

```bash
git add src/agents/data_fetcher_agent.py
git commit -m "fix: run_data_fetcher_batch entfernt, _fetch_for_ticket bleibt"
```

---

## Task 4: `logger.py` — httpx-Logs automatisch unterdrücken

**Objective:** Die httpx/httpcore/openai-Logs sollen nicht nur im Main-Block, sondern auch bei `setup_logging()` standardmäßig leiser sein.

**Files:**
- Modify: `src/tools/logger.py` (52 Zeilen)

**Step 1: Füge httpx/httpcore/openai-Unterdrückung am Ende von `setup_logging()` ein**

```python
def setup_logging(level=logging.INFO, log_file: str | None = None):
    # ... bestehender Code ...

    # Noisy HTTP-Client-Logs standardmäßig unterdrücken
    # (Niemand will "POST https://api.deepseek.com 200 OK" sehen)
    for noisy in ("httpx", "httpcore", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    
    return logger
```

**Step 2: Teste dass die Unterdrückung wirkt**

```bash
cd /c/Users/Dania/OneDrive/Documents/Coding/Github/Enterprise-Projekt
python -c "
from src.tools.logger import setup_logging
import logging
setup_logging()
h = logging.getLogger('httpx')
print(f'httpx level: {h.level} (sollte {logging.WARNING} = {logging.WARNING})')
assert h.level == logging.WARNING, 'httpx nicht unterdrückt!'
print('✅')
"
```

Expected: `httpx level: 30 (sollte 30 = 30)` und `✅`

**Step 3: Commit**

```bash
git add src/tools/logger.py
git commit -m "fix: httpx/httpcore/openai-Logs standardmaessig auf WARNING"
```

---

## Task 5: `tests/test_graph_logic.py` — Router-Tests wiederherstellen

**Objective:** `router()`-Tests zurück, batch-Tests raus, an neuen Single-Ticket-State anpassen.

**Files:**
- Modify: `tests/test_graph_logic.py` (komplett, 99 Zeilen → ~80)

**Step 1: Schreibe Test-Datei komplett neu**

```python
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
```

**Step 2: Teste dass alle Tests passen**

```bash
cd /c/Users/Dania/OneDrive/Documents/Coding/Github/Enterprise-Projekt
pytest tests/test_graph_logic.py -v --tb=short
```

Expected: 11 passed

**Step 3: Vollständigen Test-Suite laufen lassen**

```bash
pytest tests/ -v --tb=short
```

Expected: alle Tests passen (aktuell 51, nach Rückbau ggf. 1-2 weniger falls batch-Tests entfernt wurden)

**Step 4: Commit**

```bash
git add tests/test_graph_logic.py
git commit -m "fix: tests an Single-Ticket-State + Router angepasst"
```

---

## Task 6: `AGENTS.md` — Architektur-Beschreibung aktualisieren

**Objective:** Aktuelle Architektur dokumentieren (Single-Ticket, Router, Batch-Rückbau).

**Files:**
- Modify: `AGENTS.md`

**Step 1: Passe den Architektur-Abschnitt an**

Ersetze den Batch-Text durch:

```markdown
## Architecture

- `src/graph/workflow.py` — compiled `StateGraph` (entrypoint, conditional edges via `router()`, 5 nodes)
- `src/agents/*.py` — 3 agents: `triage_agent` (LLM classification eines Tickets), `data_fetcher_agent` (DB queries per Ticket), `executive_agent` (LLM decision inkl. Ticket-Text im Prompt für kundenbezogene Antwort)
- `src/tools/db_tools.py` — SQLite schema + mock data generator + query functions
- `src/tools/llm.py` — `get_llm()` returns `ChatOpenAI` pointed at DeepSeek
- **Single-Ticket**: 1 Ticket pro Graph-Invocation. Priorität: kuendigung > beschwerde > preisanfrage > sonstiges
- **Conditional-Routing**: preisanfrage/beschwerde → data_fetcher; kuendigung/sonstiges → direkt executive
- **httpx-Logs**: auf WARNING unterdrückt (kein API-Noise im Output)
- **Executive-Prompt** enthält ticket_betreff + ticket_nachricht für kundenbezogene Antwort
- HITL ist console-based (`input()` in `human_review` node) — no Slack/Gmail wired yet
```

**Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: Architektur auf Single-Ticket + Router aktualisiert"
```

---

## Task 7: `src/test_hitl.py` anpassen

**Objective:** Das HITL-Testskript nutzt die neue `collected_data`-Struktur (hat jetzt `ticket`-Key). Prüfen ob alles noch funktioniert.

**Files:**
- Check: `src/test_hitl.py`
- Modify falls nötig: `src/test_hitl.py`

**Step 1: Prüfe ob test_hitl noch läuft**

```bash
cd /c/Users/Dania/OneDrive/Documents/Coding/Github/Enterprise-Projekt
python -c "
# Syntax-Check nur (kein LLM-Call)
import ast
with open('src/test_hitl.py') as f:
    ast.parse(f.read())
print('✅ Syntax OK')
"
```

Expected: ✅ Syntax OK

Skript läuft interaktiv und ruft DeepSeek auf — manuell testen: `python src/test_hitl.py`

**Step 2: Komplette Test-Suite**

```bash
cd /c/Users/Dania/OneDrive/Documents/Coding/Github/Enterprise-Projekt
pytest tests/ -v --tb=short 2>&1
```

Expected: 51 passed (oder was vor dem Batch-Rückbau der Stand war). Wenn weniger, die fehlenden identifizieren und fixen.

**Step 3: Abschluss-Commit (falls Änderungen an test_hitl.py)**

```bash
git add src/test_hitl.py  # nur falls geändert
git commit -m "fix: test_hitl an neuen State angepasst"
```

---

## ✅ Abschluss-Checkliste

- [ ] `workflow.py`: Single-Ticket State, Router, httpx-Logs unterdrückt
- [ ] `data_fetcher_agent.py`: Kein `run_data_fetcher_batch` mehr
- [ ] `executive_agent.py`: Kein `run_executive_batch` mehr
- [ ] `logger.py`: httpx/httpcore/openai automatisch auf WARNING
- [ ] `test_graph_logic.py`: Router-Tests, passende State-Tests
- [ ] `AGENTS.md`: Beschreibung aktuell
- [ ] `pytest tests/ -v`: alle Tests grün
- [ ] `python src/graph/workflow.py`: läuft durch ohne httpx-Noise

---

## 🤖 Agent-Empfehlung

| Agent | Task | Begründung |
|---|---|---|
| **Claude Code** | Implementierung (Tasks 1-7) | Bester Implementierer. Schreibt robusten Code, geht den Plan Task-für-Task durch, committed nach jedem Schritt. Nutze: `claude -p "Implementiere den Plan aus .hermes/plans/..."` |
| OpenCode | Review nach Implementation | Prüft committed Code auf fehlende Dependencies, Dead Code, Meta-Probleme. Schnellster Reviewer. |
| Cursor (Composer) | Nicht nötig | Wäre redundant nach Claude Code + OpenCode |

**Empfohlener Workflow:**
1. **Claude Code** implementiert Tasks 1-7
2. **Du testest** `python src/graph/workflow.py` auf einem echten Ticket
3. **OpenCode** reviewed den finalen Commit-Satz
