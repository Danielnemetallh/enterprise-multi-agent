"""
HITL-Testskript: Testet den Human-in-the-Loop mit einer Kündigung
===============================================================
Läuft die Agenten einzeln durch, bis zum HITL-Stopp.
Dann kannst du "ja", "nein" oder "eigen" (KI-Vorschlag) eingeben.

Ausführung: python src/test_hitl.py
"""

import os
import sys
import json

# Projekt-Verzeichnis zum Python-Pfad hinzufügen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.llm import get_llm, extract_json
from src.tools.db_tools import query_customer, query_kunden_historie, query_open_tickets
from src.agents.triage_agent import classify_ticket
from src.agents.executive_agent import run_executive

# ─── Kündigungs-Ticket aus DB holen ───
tickets = [t for t in query_open_tickets() if t["typ"] == "kuendigung"]
if not tickets:
    print("❌ Keine Kündigungs-Tickets gefunden!")
    sys.exit(1)

r_vals = (tickets[0]["id"], tickets[0]["kunden_id"], tickets[0]["typ"],
          tickets[0]["betreff"], tickets[0]["nachricht"],
          tickets[0]["kunde"], tickets[0]["email"])

print("\n" + "="*50)
print("🧪 HITL-TEST: Kündigung verarbeiten")
print("="*50)
print(f"\n📧 Ticket #{r_vals[0]}")
print(f"   Kunde:  {r_vals[5]}")
print(f"   Betreff: {r_vals[3]}")
print(f"   Nachricht: {r_vals[4][:150]}...")

# ─── 1. Triage ───
print(f"\n--- 1️⃣  Triage-Agent ---")
classification = classify_ticket(r_vals[3], r_vals[4])
print(f"   → Klassifikation: {classification.upper()}")

# ─── 2. Data-Fetcher ───
print(f"\n--- 2️⃣  Data-Fetcher ---")
kunde = query_customer(r_vals[1])
historie = query_kunden_historie(r_vals[1])
collected = {"kunde": kunde, "historie": historie}
print(f"   → Kunde: {kunde['name']} ({kunde['status']}, {kunde['vertragstyp']})")
print(f"   → Historie: {len(historie['orders'])} Bestellungen, {len(historie['tickets'])} Tickets")

# ─── 3. Executive ───
print(f"\n--- 3️⃣  Executive-Agent ---")
action = run_executive(classification, collected)
print(f"   → Vorschlag: {action['typ']} | Rabatt: {action['wert']}%")
print(f"   → Betreff: {action.get('betreff', '?')}")
print(f"   → Nachricht: {action.get('nachricht', '?')}")

# ─── 4. HITL-Prüfung ───
print(f"\n--- 4️⃣  HITL-Prüfung ---")
kritisch = action.get("kritisch", action.get("wert", 0) > 15)
print(f"   → Kritisch? {'JA 🚷' if kritisch else 'NEIN ✅'}")


def zeige_vorschlag(aktion):
    """Zeigt einen Aktionsvorschlag schön formatiert an."""
    print(f"\n  Vorschlag:")
    print(f"  Typ:      {aktion['typ']}")
    print(f"  Rabatt:   {aktion['wert']}%")
    print(f"  Betreff:  {aktion.get('betreff', '?')}")
    print(f"  Nachricht: {aktion.get('nachricht', '?')}")


if kritisch:
    while True:
        print(f"\n{'='*50}")
        print("🚷 FREIGABE ERFORDERLICH – kritische Aktion!")
        print(f"{'='*50}")
        zeige_vorschlag(action)
        print()

        # HITL: Auf Benutzereingabe warten!
        inp = input("  Aktion freigeben? (ja/nein/eigen): ").strip().lower()

        if inp in ("ja", "yes"):
            print(f"\n  ✅ FREIGEGEBEN – Aktion wird ausgeführt!")
            print(f"  📨 {action.get('nachricht', '?')}")
            break

        elif inp in ("nein", "no"):
            print(f"\n  ❌ ABGELEHNT – Aktion wurde NICHT ausgeführt.")
            break

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
            llm = get_llm(temperature=0.3)
            resp = llm.invoke(prompt)
            result = resp.content.strip()

            try:
                action = extract_json(resp.content)
                action.setdefault("typ", "info")
                action.setdefault("wert", 0)
                action.setdefault("betreff", "Alternativ-Vorschlag")
                action.setdefault("nachricht", "Wir haben einen neuen Vorschlag für Sie.")
                action.setdefault("kritisch", action.get("wert", 0) > 15)
                print(f"\n  → Neuer Vorschlag erstellt!")
                # while-Schleife zeigt den neuen Vorschlag
            except (json.JSONDecodeError, IndexError) as e:
                print(f"  ⚠️ Konnte Vorschlag nicht parsen: {e}")
                print("  → Bitte nochmal eingeben")
        else:
            print("  ⚠️ Bitte 'ja', 'nein' oder 'eigen' eingeben.")
else:
    print(f"\n  ✅ Nicht kritisch – Aktion wird automatisch ausgeführt:")
    print(f"  📨 {action.get('nachricht', '?')}")

print(f"\n{'='*50}")
print("✅ Test abgeschlossen!")
print(f"{'='*50}")
