# Enterprise Multi-Agent System

LangGraph workflow: **Triage → Data-Fetcher → Executive → (HITL) → Execute**.
LLM: DeepSeek via OpenAI-compatible API (`src/tools/llm.py`). DB: SQLite (`data/mock_customers.db`).

## Dev commands

```powershell
.venv/Scripts/Activate.ps1                          # activate venv (Win)
python src/tools/db_tools.py --force                # regenerate mock DB
python src/graph/workflow.py                        # run full LangGraph
python src/test_hitl.py                             # HITL test (interactive)
python src/tools/llm.py                             # quick LLM smoke-test
```

## Architecture

- `src/graph/workflow.py` — compiled `StateGraph` (entrypoint, conditional edges, 5 nodes)
- `src/agents/*.py` — 3 agents: `triage_agent` (LLM classification), `data_fetcher_agent` (DB queries), `executive_agent` (LLM decision)
- `src/tools/db_tools.py` — SQLite schema + mock data generator + query functions
- `src/tools/llm.py` — `get_llm()` returns `ChatOpenAI` pointed at DeepSeek
- HITL is console-based (`input()` in `human_review` node) — no Slack/Gmail wired yet
- No CI, no tests, no lint/typecheck config — just `python some_file.py`

## Gotchas

- **`main.py` was deleted** — API-Key war hardcoded und `.env.example` war inkonsistent. Nutze `src/tools/llm.py` + `.env`.
- Venv activation is PowerShell: `.venv/Scripts/Activate.ps1` (not `source`)
- DB path is `data/mock_customers.db` (gitignored via `*.db`). Regenerate with `--force`.
- All agents import via `src.*` — run from project root, not from `src/`
- `requirements.txt` is used (no `pyproject.toml` or `setup.cfg`)
- The `.env.example` contains LM Studio variables; actual `.env` uses DeepSeek vars

## Source of truth

- `CLAUDE.md` — project brief with architecture, status, and connected services
