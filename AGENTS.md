# SupportFlow

LangGraph workflow: **Triage → Resolution → Policy → (HITL) → Finalize**. DeepSeek is accessed through `src/tools/llm.py`; SQLite stores tickets, checkpoints, runs, and reviews in `data/support_tickets.db`.

## Dev commands

```powershell
.venv/Scripts/Activate.ps1
python main.py seed --force
python main.py queue
python main.py process --ticket 2
python main.py approvals
python main.py doctor
ruff check .
pytest
```

## Architecture

- `src/graph/workflow.py` — resumable `StateGraph` with interruption
- `src/agents/triage_agent.py` — metadata-first classification with typed failure behavior
- `src/agents/executive_agent.py` — German resolution proposal and strict model validation
- `src/services/support_operations.py` — queue, run, review, and lookup boundary
- `src/tools/db_tools.py` — SQLite ticket, run, and review persistence
- `src/tools/policy.py` — deterministic risk and approval decisions
- `src/tools/case_file.py` — auditable case reports and customer-draft checks
- `src/tools/import_tickets.py` — synthetic CSV import with mapping profiles

## Data flow

```text
data/synthetic_support_tickets.csv
-> import and normalization
-> SQLite queue
-> triage and resolution proposal
-> deterministic policy
-> persisted review when required
-> local finalization and case file
```

## Conventions and safety

- Run all commands from the repository root; imports use `src.*`.
- Use Python 3.12 and `requirements.txt`.
- Keep customer-facing output German and code/policy identifiers English.
- Never commit `.env`; tests must not require live DeepSeek credentials.
- No real email, refund, cancellation, or CRM action is executed.
- Deterministic code owns risk and approval decisions.
- Failed and rejected tickets remain open.
