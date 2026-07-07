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
from typing import Literal, TypedDict
from langgraph.graph import StateGraph, END

from src.agents.triage_agent import classify_ticket
from src.agents.data_fetcher_agent import run_data_fetcher
from src.agents.executive_agent import run_executive
from src.tools.llm import get_llm, extract_json
from src.tools.db_tools import query_open_tickets


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
    tickets = query_open_tickets()
    if not tickets:
        return {**state, "classification": "sonstiges", "ticket": None}

    # Nutze state["input"] (z.B. Ticket-ID) oder falle auf erstes Ticket zurück
    ticket = tickets[0]
    if state["input"]:
        for t in tickets:
            if str(t["id"]) == state["input"].strip():
                ticket = t
                break

    classification = classify_ticket(ticket["betreff"], ticket["nachricht"])
    print(f"  🔍 Triage: [{classification}] #{ticket['id']} {ticket['betreff']}")
    return {**state, "classification": classification, "ticket": ticket}


def data_fetcher(state: AgentState) -> AgentState:
    """Agent 2: Holt Daten aus DB — je nach Klassifikation (via Data-Fetcher Agent)."""
    tickets = [state["ticket"]] if state.get("ticket") else query_open_tickets()
    collected = run_data_fetcher(state["classification"], tickets)
    print(f"  📊 Data-Fetcher: {len(collected)} Datenkategorien gesammelt")
    return {**state, "collected_data": collected}


def executive_agent(state: AgentState) -> AgentState:
    """Agent 3: Erstellt Lösungsvorschlag (via Executive-Agent / DeepSeek)."""
    action = run_executive(state["classification"], state["collected_data"])
    return {**state, "proposed_action": action}


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
            print(f" → ✅ Freigegeben")
            return state

        elif inp in ("nein", "no"):
            state["approval"] = "rejected"
            print(f" → ❌ Abgelehnt")
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
            llm = get_llm(temperature=0.3)  # etwas Kreativität
            resp = llm.invoke(prompt)

            try:
                new_action = extract_json(resp.content)
                new_action.setdefault("typ", "info")
                new_action.setdefault("wert", 0)
                new_action.setdefault("betreff", "Alternativ-Vorschlag")
                new_action.setdefault("nachricht", "Wir haben einen neuen Vorschlag für Sie.")
                new_action.setdefault("kritisch", new_action.get("wert", 0) > 15)

                state["proposed_action"] = new_action
                print(f"  → Neuer Vorschlag: {new_action['typ']} | {new_action.get('betreff', '?')}")
                # while-Schleife wiederholt sich → Benutzer sieht neuen Vorschlag

            except (json.JSONDecodeError, IndexError) as e:
                print(f"  ⚠️ Konnte Alternativ-Vorschlag nicht parsen: {e}")
                print("  → Bitte nochmal eingeben (ja/nein/eigen)")
        else:
            print("  ⚠️ Bitte 'ja', 'nein' oder 'eigen' eingeben.")


def execute_action(state: AgentState) -> AgentState:
    """Führt die Aktion aus."""
    action = state["proposed_action"]
    kunde = state["collected_data"].get("kunde", {})

    if state["approval"] == "rejected":
        print(f"\n  ❌ Aktion abgelehnt")
        print(f" ─────────────────────────────────────")
        print(f"  Typ:     {action.get('typ', '?')}")
        print(f"  Rabatt:  {action.get('wert', 0)}%")
        print(f"  Kunde:   {kunde.get('name', '?')}")
        print(f"  ─────────────────────────────────────")
        return state

    print(f"\n  ✅ AKTION AUSGEFÜHRT")
    print(f"  ─────────────────────────────────────")
    print(f"  Typ:     {action.get('typ', '?')}")
    print(f"  Rabatt:  {action.get('wert', 0)}%")
    print(f"  Kunde:   {kunde.get('name', '?')}")
    print(f"  Status:  {kunde.get('status', '?')}")
    print(f"  ─────────────────────────────────────")
    print(f"  📨 {action.get('nachricht', '?')}")
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
    graph = build_graph()
    print("✅ LangGraph compiled!\n")

    # Testlauf
    result = graph.invoke({
        "input": "",
        "ticket": None,
        "classification": "",
        "collected_data": {},
        "proposed_action": {},
        "approval": "pending",
    })
    print(f"\n📊 Final State: {result}")
