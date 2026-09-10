# SupportFlow — Kontrollierte KI für den Kundenservice

SupportFlow priorisiert Support-Tickets, erstellt mit DeepSeek einen deutschen Lösungsvorschlag und lässt deterministischen Policy-Code über Risiko und Freigabepflicht entscheiden. Kritische Fälle pausieren dauerhaft für eine menschliche Prüfung. Es werden keine echten E-Mails, Erstattungen, Kündigungen oder CRM-Aktionen ausgeführt; die Finalisierung bleibt lokal und alle Beispieldaten sind synthetisch.

## Ablauf

```text
Ticket Queue → Triage → Resolution Proposal → Deterministic Policy
             → Human Approval (wenn nötig) → Local Finalization
```

- Metadaten werden bevorzugt; unbekannte Kategorien werden nicht stillschweigend umgedeutet.
- DeepSeek-Ausgaben werden strikt typisiert und validiert.
- Provider- und Validierungsfehler bleiben als fehlgeschlagene Läufe sichtbar.
- LangGraph-Interrupts und Freigaben werden in SQLite gespeichert und sind fortsetzbar.
- Tickets werden erst nach erfolgreicher lokaler Finalisierung als verarbeitet markiert.

## Setup

```powershell
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
Copy-Item .env.example .env
```

Trage für echte Modellaufrufe `DEEPSEEK_API_KEY` in `.env` ein. Tests verwenden Stubs und benötigen keinen Schlüssel.

## CLI

```powershell
.venv/Scripts/python.exe main.py seed --force
.venv/Scripts/python.exe main.py queue
.venv/Scripts/python.exe main.py process --ticket 2
.venv/Scripts/python.exe main.py approvals
.venv/Scripts/python.exe main.py review --run RUN-ID --decision approve --reviewer dania --notes "Geprüft"
.venv/Scripts/python.exe main.py show --run RUN-ID
.venv/Scripts/python.exe main.py doctor
.venv/Scripts/python.exe main.py doctor --live
```

`doctor` prüft standardmäßig nur die lokale Konfiguration. Nur `doctor --live` sendet einen expliziten DeepSeek-Smoke-Test.

## Frontend-Demo

Die interviewfähige Operations-Oberfläche liegt in `app.py` und verwendet dieselbe Service-Grenze wie die CLI. Sie zeigt Ticket-Warteschlange, Agenten-Timeline, Vorschlag, deterministische Policy-Entscheidung und den Human-in-the-loop-Schritt gemeinsam in einer Ansicht.

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
.venv/Scripts/python.exe -m streamlit run app.py
```

Wenn die Datenbank leer ist, kann die synthetische CSV-Demo über `Demo-Ticketwarteschlange laden` in der Seitenleiste importiert werden. `Agenten für dieses Ticket starten` startet den echten resumierbaren Workflow; ein Lauf mit Freigabepflicht erscheint als sichtbare menschliche Prüfstelle.

## Drei-Minuten-Demo

1. `seed --force` lädt fünf synthetische Tickets.
2. `queue` zeigt die Reihenfolge nach Priorität und Alter.
3. `process --ticket 2` erstellt einen Kündigungsvorschlag und pausiert bei `awaiting_review`.
4. `approvals` zeigt Belege, Policy-Entscheidung und Entwurf.
5. `review ... --decision approve` setzt denselben Lauf fort und finalisiert ihn lokal.
6. `show --run ...` zeigt Fallbericht, Entscheidungsquelle, Policy-Regeln und Freigabestatus.

## Backend-Grenzen

Die UI-unabhängigen Operationen liegen in `src/services/support_operations.py`:

- `list_ticket_queue()`
- `start_ticket_run(ticket_id)`
- `list_pending_reviews()`
- `review_run(run_id, command)`
- `get_run(run_id)`

Eine spätere FastAPI-Oberfläche kann diese Funktionen aufrufen, ohne Workflow-Logik in Routen zu verschieben.

## Qualität

```powershell
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m pytest -q
```

GitHub Actions führt Ruff und pytest mit Python 3.12 ohne Live-DeepSeek-Aufruf aus.
