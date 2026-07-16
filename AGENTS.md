# Enterprise Multi-Agent System

LangGraph workflow: **Triage → Executive → (HITL) → Execute**.
LLM: DeepSeek via OpenAI-compatible API (`src/tools/llm.py`). DB: SQLite (`data/support_tickets.db`).

## Dev commands

```powershell
.venv/Scripts/Activate.ps1                          # activate venv (Win)
python src/tools/db_tools.py --force                # create empty runtime DB
python src/tools/import_tickets.py --csv data/customer_support_tickets.csv --mapping data/mappings/kaggle_support.json --force
python src/graph/workflow.py                        # run full LangGraph
python src/test_hitl.py                             # HITL test (interactive)
pytest                                              # run test suite
python src/tools/llm.py                             # quick LLM smoke-test
```

## Architecture

- `src/graph/workflow.py` — compiled `StateGraph` (entrypoint, conditional edges, 4 nodes)
- `src/agents/triage_agent.py` — metadata-first classification with LLM fallback
- `src/agents/executive_agent.py` — LLM decision + policy evaluation
- `src/tools/db_tools.py` — English SQLite ticket store and query functions
- `src/tools/import_tickets.py` — bulk CSV import with column mapping profiles
- `src/tools/ticket_schema.py` — category/status normalization for imported datasets
- `src/tools/policy.py` — deterministic approval rules
- `src/tools/case_file.py` — English case file output
- `src/tools/llm.py` — `get_llm()` returns `ChatOpenAI` pointed at DeepSeek
- HITL is console-based (`input()` in `human_review` node) — no Slack/Gmail wired yet
- `pytest` + `tests/` cover import, triage, policy, graph integration, and case output

## Data flow

```text
data/customer_support_tickets.csv
-> import_tickets.py + mapping JSON
-> SQLite support_tickets runtime store
-> LangGraph agents
-> policy check / HITL
-> case file + customer draft
```

## Gotchas

- Venv activation is PowerShell: `.venv/Scripts/Activate.ps1` (not `source`)
- DB path is `data/support_tickets.db` (gitignored via `*.db`). Create with `db_tools.py --force`.
- All agents import via `src.*` — run from project root, not from `src/`
- `requirements.txt` is used (no `pyproject.toml` or `setup.cfg`)
- `pandas` is used only for CSV import, not runtime agent execution
- The `.env.example` contains LM Studio variables; actual `.env` uses DeepSeek vars

## Source of truth

- `CLAUDE.md` — project brief with architecture, status, and connected services
