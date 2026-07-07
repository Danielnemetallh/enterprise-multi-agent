# Enterprise Multi-Agent System — Project Brief

## Übersicht
Autonomous Multi-Agent Operations & API-Routing Engine (LangGraph).
Ein System, das täglich Tausende von Kundenanfragen, Stornierungen, Preis-Reklamationen oder Wettbewerber-Updates autonom verarbeitet – durch ein Multi-Agenten-Team aus spezialisierten Mini-KIs.

## Architektur (3 Agenten + Human-in-the-Loop)

```
┌──────────┐
│  📥 Input │
└────┬─────┘
     │
┌────▼─────┐          ╔═══════════════════╗
│ ◆ Triage  │─────────→║ Agent 2: Data-    ║  ← Preisanfragen
│   Agent   │  preis?  ║ Fetcher (DB/Scrape)║
└────┬─────┘          ╚═══════╦═══════════╝
     │                       │
     │  beschwerde/           │ Daten → Lösung
     │  kündigung?            │
     │                  ╔═════▼═════════════╗
     └─────────────────→║ Agent 3: Executive ║
                        ║ (Lösung + API)    ║
                        ╚═════╦═════════════╝
                             │
                        ┌────▼─────┐
                    nein│ ◆ Kritisch?│ ja
                        └────┬─────┘
                           ╱    ╲
                          ╱      ╲
                     ┌───▼┐     ┌──▼──────────┐
                     │ ✅  │     │ 🚷 Human-in- │
                     │Execute│    │  the-Loop    │
                     └──────┘    │ (WAIT-State)  │
                                 └──────┬───────┘
                                   ✅│      ❌
                                ┌───▼──┐  ┌─▼──┐
                                │Execute│  │ENDE│
                                └───────┘  └────┘
```

## Projekt-Struktur

```
C:\Users\Dania\OneDrive\Documents\Coding\Github\Enterprise-Projekt/
├── .venv/                          ← Python 3.11.15
├── data/
│   └── mock_customers.db           ← SQLite-Mock-DB
├── src/
│   ├── agents/                     ← Triage, Data-Fetcher, Executive
│   ├── graph/
│   │   └── workflow.py             ← LangGraph: State, Nodes, Edges
│   ├── models/                     ← (vorbereitet)
│   └── tools/
│       ├── db_tools.py             ← DB-Queries für Agenten
│       └── llm.py                  ← DeepSeek-API + extract_json
├── tests/                          ← 49 Pytest-Tests
├── .gitignore
├── requirements.txt
└── CLAUDE.md                       ← dieser File
```

## Status (was ist bereits gemacht?)

### ✅ Erledigt
- [x] Virtuelle Umgebung (`.venv`) mit Python 3.11.15
- [x] Pakete installiert: langgraph, langchain, langchain-openai, beautifulsoup4, requests, pydantic, faker
- [x] Ordner-Struktur angelegt (src/agents, graph, models, tools)
- [x] LangGraph-Code-Gerüst: `src/graph/workflow.py`
  - `class AgentState` — State-Modell (TypedDict)
  - 5 Nodes: triage_agent, data_fetcher, executive_agent, human_review, execute_action
  - 2 Conditional Edges: router() (Klassifikation), needs_approval() (HITL-Prüfung)
  - `build_graph()` → kompilierter StateGraph
- [x] Excalidraw-Diagramm in `../Enterprise-Projekt-Docs/`
- [x] Mock-Datenbank: `data/mock_customers.db`
  - 50 Kunden (deutsche Fake-Daten via Faker)
  - 10 Produkte
  - 30 Konkurrenz-Preise (5 Anbieter)
  - 30 Support-Tickets (Beschwerden, Kündigungen, Preisanfragen)
  - 80 Bestellungen
- [x] Query-Funktionen in `src/tools/db_tools.py`:
  - `query_customer(id)` — Stammdaten
  - `query_competitor_prices(produkt)` — Konkurrenz-Preisvergleich
  - `query_open_tickets()` — Offene Tickets für Triage
  - `query_kunden_historie(id)` — Bestellungen + Ticket-Verlauf

### ⏳ Nächstes
- [ ] Error-Handling + Logging
- [ ] Human-in-the-Loop mit Console/Slack/Gmail
- [ ] Vollständigen Graph-Durchlauf testen

### ✅ Neu hinzugekommen
- [x] DeepSeek via API angebunden (`src/tools/llm.py`)
- [x] Triage-Agent klassifiziert live mit DeepSeek (`src/agents/triage_agent.py`)
- [x] Data-Fetcher + Executive-Agent Logik implementiert
- [x] `extract_json()` — Robustes JSON-Parsing für LLM-Responses
- [x] 49 Pytest-Tests für Kernlogik
- [x] `db_connection` Context-Manager für saubere DB-Verbindungen
- [x] Docs nach `../Enterprise-Projekt-Docs/` ausgelagert

## Technisches Setup

### LLM: DeepSeek (via API)
- Anbieter: DeepSeek (API-Key in `.env`)
- Modell: `deepseek-chat`
- Kosten: ~0.14$/1M Tokens (sehr günstig)
- Alternativ: OpenRouter mit DeepSeek oder anderen Modellen

### Wichtige Befehle
```bash
# Venv aktivieren
source .venv/Scripts/activate

# DB neu erzeugen
python src/tools/db_tools.py --force

# Graph testen
python src/graph/workflow.py

# DB-Kurztest
python -c "from src.tools.db_tools import *; create_database(True); print(query_open_tickets()[:2])"
```

### Verbundene Dienste (via Composio)
- **Notion** — Project-Docs (Composio-Bot: "Composio")
- **Gmail** — E-Mail-Versand (für HITL-Benachrichtigung)
- **Slack** — (optional, für HITL-Freigabe)

---

*Erstellt von Hermes Agent am 28.06.2026*
