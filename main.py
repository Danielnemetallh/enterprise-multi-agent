#!/usr/bin/env python3
"""
Enterprise Multi-Agent System — CLI-Einstiegspunkt
====================================================
Führt einen vollständigen LangGraph-Durchlauf aus:
  Triage → Data-Fetcher (optional) → Executive → HITL (optional) → Execute

Usage:
    python main.py                    # Nächstes dringendes Ticket verarbeiten
    python main.py --input 5          # Bestimmtes Ticket (ID 5) verarbeiten
    python main.py --db-rebuild       # DB neu erstellen, dann Ticket verarbeiten
    python main.py --verbose          # Mit detaillierten INFO-Logs
"""
import sys
import os

# Projekt-Root zum Pfad hinzufügen
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.tools.logger import setup_logging
from src.tools.db_tools import ensure_db
from src.graph.workflow import build_graph, AgentState

logger = setup_logging()


def main():
    args = sys.argv[1:]

    # Standard: nur WARNING+ anzeigen, mit --verbose auch INFO
    if "--verbose" not in args:
        import logging
        logging.getLogger().setLevel(logging.WARNING)

    # DB bei Bedarf neu erstellen
    if "--db-rebuild" in args:
        from src.tools.db_tools import create_database
        create_database(force=True)
        print("✅ Datenbank neu erstellt.\n")

    # Bestimmtes Ticket per ID?
    ticket_input = ""
    for i, arg in enumerate(args):
        if arg == "--input" and i + 1 < len(args):
            ticket_input = args[i + 1]
            break

    graph = build_graph()
    logger.info("🚀 Starte Graph-Durchlauf...")

    try:
        result = graph.invoke({
            "input": ticket_input,
            "ticket": None,
            "classification": "",
            "collected_data": {},
            "proposed_action": {},
            "approval": "pending",
        })
        logger.info("✅ Graph-Durchlauf abgeschlossen")

        # Abschlussbericht anzeigen
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
        logger.error(f"❌ Graph-Durchlauf fehlgeschlagen: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
