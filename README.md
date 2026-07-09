# 🧠 Enterprise Multi-Agent System

Autonome Verarbeitung von Kundenanfragen via **3 spezialisierte KI-Agenten** (LangGraph + DeepSeek).

> **Werkstudent-Bewerbungsprojekt** — Zeigt Kenntnisse in: LangGraph, Multi-Agent-Architekturen, LLM-Integration, Human-in-the-Loop, Python 3.11, SQLite, Pytest.

---

## Architektur

```
┌──────────┐
│  📥 Input │
└────┬─────┘
     │
┌────▼─────┐          ╔═══════════════════╗
│ ◆ Triage  │─────────→║ Data-Fetcher      ║  ← Preisanfragen
│   Agent   │  preis?  ║ (DB / Scraping)   ║     & Beschwerden
└────┬─────┘          ╚═══════╦═══════════╝
     │                       │
     │  kündigung/            │
     │  sonstiges?            │
     │                  ╔═════▼═════════════╗
     └─────────────────→║ Executive Agent    ║
                        ║ (Lösung + API)    ║
                        ╚═════╦═════════════╝
                             │
                        ┌────▼─────┐
                    nein│ ◆ Kritisch?│ ja
                        └────┬─────┘
                           ╱    ╲
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

### Agenten

| Agent | Aufgabe | Technik |
|-------|---------|---------|
| **Triage** (1) | Klassifiziert Tickets in: `preisanfrage`, `beschwerde`, `kuendigung`, `sonstiges` | DeepSeek-Chat via LangChain |
| **Data-Fetcher** (2) | Sammelt Kontext aus DB (Kundendaten, Preise, Historie) | SQLite, Python |
| **Executive** (3) | Erstellt Lösungsvorschlag mit Rabatt, Betreff und Nachricht | DeepSeek-Chat (JSON-Mode) |

### Human-in-the-Loop

Kritische Aktionen (Rabatt > 15% oder explizites Flag) werden **vor der Ausführung gestoppt** und warten auf Freigabe:
- `ja` → Aktion wird ausgeführt
- `nein` → Aktion wird abgelehnt
- `eigen` → KI erstellt einen Alternativ-Vorschlag

---

## Quick Start

### Voraussetzungen

- Python 3.11+
- DeepSeek API-Key (oder anderer OpenAI-kompatibler Anbieter)

### Installation

```bash
# Repository klonen
git clone https://github.com/Danial36947112/Enterprise-Projekt.git
cd Enterprise-Projekt

# Venv erstellen
python -m venv .venv
source .venv/Scripts/activate    # Windows
# source .venv/bin/activate      # Linux/Mac

# Pakete installieren
pip install -r requirements.txt

# API-Key konfigurieren
echo "DEEPSEEK_API_KEY=sk-..." > .env
```

### Ausführen

```bash
# Einmaligen Graph-Durchlauf starten
python src/graph/workflow.py
```

Das System sucht automatisch das dringendste offene Ticket (Kündigung > Beschwerde > Preisanfrage > Sonstiges), klassifiziert es, sammelt Daten, erstellt einen Lösungsvorschlag und fragt bei kritischen Aktionen nach Freigabe.

### Beispiele

**Ein kompletter Durchlauf** (gekürzt):
```
📋 ABSCHLUSSBERICHT
============================================================
  Ticket #5 [kuendigung]
  Kunde: Martina Schulze (Premium)
  Betreff: Kündigung meines Vertrags
  Status: ✅ Genehmigt
  Aktion: angebot | Rabatt: 20%
  Antwort: Wir bedauern Ihre Kündigung. Als geschätzter Premium-Kunde
  möchten wir Ihnen 20% Rabatt auf Ihren aktuellen Tarif anbieten.
```

### Tests

```bash
pytest tests/ -v
# 55 passed in 3.32s
```

---

## Projektstruktur

```
Enterprise-Projekt/
├── .env                         # DeepSeek API-Key
├── .venv/                       # Python Virtual Environment
├── data/
│   └── mock_customers.db        # SQLite-Mock-DB
├── src/
│   ├── agents/
│   │   ├── triage_agent.py      # Agent 1: Klassifikation
│   │   ├── data_fetcher_agent.py # Agent 2: Daten sammeln
│   │   └── executive_agent.py   # Agent 3: Lösungen
│   ├── graph/
│   │   └── workflow.py          # LangGraph: State, Nodes, Edges
│   ├── tools/
│   │   ├── db_tools.py          # SQLite-Datenbankzugriff
│   │   ├── llm.py              # DeepSeek-API + JSON-Parser
│   │   └── logger.py           # Zentrale Logging-Konfiguration
│   └── test_hitl.py            # HITL-Testskript (Kündigungen)
├── tests/                       # 55 Pytest-Tests
├── main.py                      # CLI-Einstiegspunkt
└── requirements.txt
```

---

## Tech Stack

| Komponente | Technologie |
|------------|-------------|
| Agenten-Orchestrierung | [LangGraph](https://www.langchain.com/langgraph) (StateGraph) |
| LLM | DeepSeek Chat (via [LangChain OpenAI](https://python.langchain.com/)) |
| Datenbank | SQLite (50 Kunden, 30 Tickets, 80 Bestellungen) |
| Human-in-the-Loop | Console-basiert (ja/nein/eigen) |
| Tests | Pytest (55 Unit- + Integrationstests) |
| Sprache | Python 3.11+ (type hints, f-strings, pathlib) |

---

## Was ich gelernt habe

- **LangGraph StateGraph**: Zustandsgesteuerte Agenten-Workflows bauen mit `add_node`, `add_conditional_edges` und TypedDict-State
- **Multi-Agent-Architektur**: Spezialisierte Agenten (Triage → Data → Executive) statt einem monolithischen LLM-Call
- **Human-in-the-Loop**: Kritische Entscheidungen vor der automatischen Ausführung stoppen
- **LLM-Integration**: DeepSeek über ChatOpenAI-API mit robustem JSON-Parsing und Retry-Logik
- **Error-Handling**: Jeder Agent hat Fallbacks, damit das System nie komplett abstürzt
- **Testen mit Mocks**: LLM- und DB-Zugriffe in Integrationstests mocken für schnelle, deterministische Tests

---

## Lizenz

MIT
