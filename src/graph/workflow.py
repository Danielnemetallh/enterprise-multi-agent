"""
Enterprise Multi-Agent System — LangGraph Workflow
====================================================
Nodes:   triage → data_fetcher / executive → human_review → execute
Edges:   conditional routing via router() & needs_approval()
State:   AgentState (TypedDict)
LLM:     DeepSeek (via src.tools.llm)
DB:      SQLite Mock-DB (via src.tools.db_tools)
"""

# Projekt-Root zum sys.path hinzufügen (für direkte Ausführung)
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
from src.tools.db_tools import query_open_tickets, mark_ticket_done

logger = logging.getLogger(__name__)


# ─────────────────────────────── S T A T E ───────────────────────────────

class AgentState(TypedDict):
    """Gemeinsamer State, der durch den gesamten Graphen fließt."""
    input: str                 # Original-Eingabe (Mail / Task)
    ticket: dict | None        # Aktuelles Ticket (vom Triage gesetzt)
    classification: str        # "beschwerde" | "kuendigung" | "preisanfrage" | "sonstiges"
    collected_data: dict       # Daten aus DB / Scraping
    proposed_action: dict      # Lösungsvorschlag vom Executive-Agent
    approval: str              # "pending" | "approved" | "rejected"


# ─────────────────────────────── N O D E S ───────────────────────────────

def triage_agent(state: AgentState) -> AgentState:
    """Agent 1: Klassifiziert den Eingang via DeepSeek."""
    try:
        tickets = query_open_tickets()
        if not tickets:
            logger.warning("Keine offenen Tickets gefunden")
            return {**state, "classification": "sonstiges", "ticket": None}

        # Nutze state["input"] (z.B. Ticket-ID) oder Priorität
        ticket = tickets[0]
        if state["input"]:
            for t in tickets:
                if str(t["id"]) == state["input"].strip():
                    ticket = t
                    break
        else:
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
        collected = run_data_fetcher(state["classification"], state.get("ticket"))
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

    # Ticket als erledigt markieren (damit nächstes Mal ein anderes dran kommt)
    ticket_id = state.get("ticket", {}).get("id")
    if ticket_id:
        mark_ticket_done(ticket_id)

    return {**state, "approval": "approved"}


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
    """Erstellt den LangGraph-Graphen."""
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

    graph = build_graph()
    logger.info("LangGraph compiled!")

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
