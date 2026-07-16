# Enterprise Multi-Agent Support System

An autonomous customer support triage system built with **LangGraph** and **DeepSeek**. Classifies incoming support tickets, applies policy-based approval rules, and routes critical cases through a Human-in-the-Loop review step before executing actions.

## Architecture

```
Input → Triage Agent → Executive Agent → Policy Check → Execute
                                               ↓ (critical)
                                        Human-in-the-Loop (WAIT)
```

- **Triage Agent** — metadata-first classification with LLM fallback (complaint / cancellation / price inquiry)
- **Executive Agent** — LLM-driven decision + deterministic policy evaluation
- **Policy Engine** — rule-based approval gates (no LLM calls, fully testable)
- **HITL Node** — console-based review step for high-risk actions; planned expansion to Slack/Gmail
- **Case File Output** — structured English case summary per ticket

## Data Pipeline

```
data/customer_support_tickets.csv
  → import_tickets.py + column mapping profile
  → SQLite ticket store (data/support_tickets.db)
  → LangGraph agents
  → policy check / HITL
  → case file
```

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph (StateGraph) |
| LLM | DeepSeek `deepseek-chat` via OpenAI-compatible API |
| DB | SQLite (runtime) |
| Data import | pandas + custom schema normalization |
| Tests | pytest — 63 tests |

## Project Structure

```
src/
├── agents/
│   ├── triage_agent.py       # metadata-first classification
│   └── executive_agent.py    # LLM decision + policy evaluation
├── graph/
│   └── workflow.py           # LangGraph StateGraph (entrypoint)
└── tools/
    ├── db_tools.py           # SQLite queries
    ├── import_tickets.py     # bulk CSV import
    ├── ticket_schema.py      # category/status normalization
    ├── policy.py             # deterministic approval rules
    ├── case_file.py          # structured case output
    └── llm.py                # DeepSeek client
data/
├── customer_support_tickets.csv   # source dataset (Kaggle)
└── mappings/kaggle_support.json   # column mapping profile
tests/                        # 63 pytest tests
```

## Setup

```powershell
# 1. Clone and create virtual environment
python -m venv .venv
.venv/Scripts/Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Add your DeepSeek API key to .env

# 4. Create the runtime database
python src/tools/db_tools.py --force
python src/tools/import_tickets.py --csv data/customer_support_tickets.csv --mapping data/mappings/kaggle_support.json --force

# 5. Run
python src/graph/workflow.py

# 6. Tests
pytest
```

## Environment Variables

```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

## Status

- [x] Multi-agent LangGraph workflow
- [x] DeepSeek LLM integration
- [x] CSV ingestion pipeline with column mapping
- [x] Policy engine with deterministic approval rules
- [x] Human-in-the-Loop (console) — Slack/Gmail expansion planned
- [x] 63 passing tests
