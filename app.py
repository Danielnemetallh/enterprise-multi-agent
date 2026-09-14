"""Streamlit operations console for the SupportFlow agent workflow."""

from __future__ import annotations

import json
import os
from html import escape
from pathlib import Path
from typing import Any

import streamlit as st

from src.services.support_operations import (
    list_pending_reviews,
    list_ticket_queue,
    review_run,
    start_ticket_run,
)
from src.tools import db_tools
from src.tools.import_tickets import import_tickets_from_csv
from src.tools.llm import get_llm_config

PROJECT_ROOT = Path(__file__).resolve().parent
DEMO_CSV = PROJECT_ROOT / "data" / "synthetic_support_tickets.csv"
DEMO_MAPPING = PROJECT_ROOT / "data" / "mappings" / "kaggle_support.json"
DEMO_SOURCE_DATASET = "kaggle_customer_support"

AGENT_STAGES = (
    ("triage_agent", "Triage"),
    ("resolution_agent", "Lösung"),
    ("policy_agent", "Richtlinie"),
    ("human_review", "Menschliche Prüfung"),
    ("finalize_action", "Abschluss"),
)

DISPLAY_LABELS = {
    "open": "Offen",
    "awaiting_review": "Wartet auf Prüfung",
    "completed": "Abgeschlossen",
    "failed": "Fehlgeschlagen",
    "rejected": "Abgelehnt",
    "running": "Läuft",
    "queued": "Warteschlange",
    "active": "Aktiv",
    "complete": "Abgeschlossen",
    "blocked": "Wartet",
    "critical": "Kritisch",
    "high": "Hoch",
    "medium": "Mittel",
    "low": "Niedrig",
    "technical_issue": "Technisches Problem",
    "refund_request": "Erstattungsanfrage",
    "cancellation_request": "Kündigungsanfrage",
    "product_inquiry": "Produktanfrage",
    "billing_inquiry": "Rechnungsanfrage",
    "offer_discount": "Rabatt anbieten",
    "send_apology": "Entschuldigung senden",
    "provide_information": "Information bereitstellen",
    "process_cancellation": "Kündigung bearbeiten",
    "auto_approved": "Automatisch freigegeben",
    "needs_approval": "Freigabe erforderlich",
    "not_required": "Nicht erforderlich",
    "pending": "Ausstehend",
}


st.set_page_config(
    page_title="SupportFlow · Operations-Konsole",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');

        :root {
            --sf-bg: #0b100f;
            --sf-surface: #111817;
            --sf-surface-2: #16201e;
            --sf-border: rgba(222, 232, 223, 0.13);
            --sf-muted: #82908a;
            --sf-text: #eff4ee;
            --sf-lime: #c6f56b;
            --sf-coral: #ff8c73;
            --sf-amber: #f1c65b;
        }

        html, body, [class*="css"] { font-family: 'Manrope', sans-serif; }
        .stApp {
            background:
                radial-gradient(circle at 78% 0%, rgba(198, 245, 107, 0.06), transparent 28rem),
                linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.018) 1px, transparent 1px),
                var(--sf-bg);
            background-size: auto, 28px 28px, 28px 28px, auto;
            color: var(--sf-text);
        }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stSidebar"] {
            background: rgba(13, 20, 18, 0.94);
            border-right: 1px solid var(--sf-border);
        }
        [data-testid="stSidebar"] > div:first-child { padding-top: 1.4rem; }
        .block-container { max-width: 1660px; padding: 1.7rem 2.2rem 3rem; }
        h1, h2, h3, h4 { letter-spacing: -0.04em; }
        h1 { font-size: clamp(2.2rem, 3vw, 4.2rem) !important; line-height: 0.98 !important; }
        h2 { font-size: 1.45rem !important; }
        h3 { font-size: 1.08rem !important; }
        .mono, code, [data-testid="stMetricValue"] { font-family: 'DM Mono', monospace; }
        .brand-lockup { display:flex; align-items:center; gap:.72rem; margin-bottom: 2rem; }
        .brand-mark {
            width: 2rem; height: 2rem; border-radius: .62rem; display:grid; place-items:center;
            color: #09100c; background: var(--sf-lime); font-weight: 800; font-size: 1.05rem;
            box-shadow: 0 0 24px rgba(198,245,107,.18);
        }
        .brand-name { font-size: 1.12rem; font-weight: 800; letter-spacing: -.05em; }
        .brand-sub { color: var(--sf-muted); font-size: .68rem; letter-spacing: .08em; text-transform: uppercase; }
        .eyebrow { color: var(--sf-lime); text-transform: uppercase; letter-spacing: .15em; font-size: .68rem; font-weight: 700; }
        .page-intro { display:flex; justify-content:space-between; align-items:end; gap: 1rem; margin-bottom: 1.45rem; }
        .page-intro p { color: var(--sf-muted); margin: .7rem 0 0; max-width: 44rem; line-height: 1.65; }
        .live-pill, .chip {
            display:inline-flex; align-items:center; gap:.42rem; border:1px solid var(--sf-border);
            background: rgba(198,245,107,.07); color: var(--sf-lime); padding:.38rem .68rem;
            border-radius: 999px; font-size:.72rem; font-weight:700; white-space:nowrap;
        }
        .live-dot { width:.42rem; height:.42rem; border-radius:50%; background:var(--sf-lime); box-shadow:0 0 0 .2rem rgba(198,245,107,.1); }
        .metric-card, .panel, .agent-card, .callout {
            background: linear-gradient(135deg, rgba(23,34,31,.92), rgba(13,20,18,.92));
            border: 1px solid var(--sf-border); border-radius: 12px;
        }
        .metric-card { padding: 1rem 1.1rem; min-height: 6rem; }
        .metric-label { color: var(--sf-muted); font-size: .71rem; text-transform: uppercase; letter-spacing: .11em; }
        .metric-value { font-size: 1.75rem; font-weight: 700; letter-spacing: -.06em; margin-top: .5rem; }
        .metric-note { color: var(--sf-muted); font-size: .72rem; margin-top: .2rem; }
        .panel { padding: 1.15rem; height: 100%; }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: linear-gradient(135deg, rgba(23,34,31,.92), rgba(13,20,18,.92));
            border-color: var(--sf-border); border-radius: 12px; padding: .15rem .25rem;
        }
        .panel-title { display:flex; justify-content:space-between; align-items:center; gap:1rem; margin-bottom: 1rem; }
        .panel-title h3 { margin:0; }
        .panel-kicker { color: var(--sf-muted); font-size:.74rem; }
        .ticket-highlight { border: 1px solid rgba(198,245,107,.65); background: rgba(198,245,107,.07); border-radius: 10px; padding: .95rem; margin-bottom: 1rem; }
        .ticket-id { color: var(--sf-lime); font-family:'DM Mono', monospace; font-size:.72rem; }
        .ticket-subject { font-size: 1.02rem; font-weight: 700; line-height:1.35; margin:.45rem 0; }
        .ticket-customer { color: var(--sf-muted); font-size: .76rem; }
        .key-row { display:flex; justify-content:space-between; gap:.8rem; border-bottom:1px solid rgba(222,232,223,.08); padding:.58rem 0; font-size:.77rem; }
        .key-row span:first-child { color:var(--sf-muted); }
        .key-row span:last-child { text-align:right; }
        .status-text { display:inline-flex; align-items:center; gap:.4rem; font-size:.73rem; }
        .status-dot { width:.44rem; height:.44rem; border-radius:50%; display:inline-block; background:var(--sf-muted); }
        .status-dot.complete, .status-dot.active { background:var(--sf-lime); box-shadow:0 0 0 .2rem rgba(198,245,107,.08); }
        .status-dot.review { background:var(--sf-coral); box-shadow:0 0 0 .2rem rgba(255,140,115,.1); }
        .status-dot.warning { background:var(--sf-amber); }
        .timeline { position:relative; padding:.2rem 0 .1rem .1rem; }
        .timeline:before { content:''; position:absolute; left:.58rem; top:.85rem; bottom:.9rem; width:1px; background:rgba(222,232,223,.18); }
        .timeline-item { position:relative; display:grid; grid-template-columns:1.15rem 1fr; gap:.85rem; padding:.28rem 0 .98rem; }
        .timeline-node { z-index:1; width:1.05rem; height:1.05rem; border:1px solid rgba(222,232,223,.45); border-radius:50%; background:var(--sf-bg); display:grid; place-items:center; font-size:.58rem; }
        .timeline-node.complete { border-color:var(--sf-lime); color:var(--sf-lime); }
        .timeline-node.active { border-color:var(--sf-coral); color:var(--sf-coral); box-shadow:0 0 0 .24rem rgba(255,140,115,.1); }
        .timeline-node.blocked { border-color:rgba(222,232,223,.2); color:var(--sf-muted); }
        .timeline-name { font-size:.84rem; font-weight:700; }
        .timeline-desc { color:var(--sf-muted); font-size:.72rem; line-height:1.5; margin-top:.2rem; }
        .timeline-meta { color:var(--sf-muted); font-family:'DM Mono', monospace; font-size:.65rem; margin-top:.38rem; }
        .proposal-box, .draft-box, .policy-box { padding: .9rem; border-radius: 9px; border:1px solid rgba(222,232,223,.1); background:rgba(7,12,11,.34); }
        .proposal-box strong, .draft-box strong, .policy-box strong { display:block; font-size:.7rem; text-transform:uppercase; letter-spacing:.1em; color:var(--sf-muted); margin-bottom:.5rem; }
        .proposal-main { font-size: 1.04rem; font-weight: 700; line-height:1.35; }
        .proposal-copy { color:#c8d0c9; font-size:.8rem; line-height:1.65; }
        .policy-pass { color:var(--sf-lime); font-size:1.02rem; font-weight:800; }
        .policy-review { color:var(--sf-coral); font-size:1.02rem; font-weight:800; }
        .policy-rule { display:flex; gap:.5rem; font-size:.76rem; color:#c8d0c9; margin-top:.58rem; line-height:1.45; }
        .policy-rule:before { content:'✓'; color:var(--sf-lime); font-family:'DM Mono', monospace; }
        .empty-state { padding: 2rem 1rem; border:1px dashed rgba(222,232,223,.22); border-radius: 10px; color:var(--sf-muted); text-align:center; }
        .section-spacer { height: 1.1rem; }
        .small-note { color:var(--sf-muted); font-size:.72rem; line-height:1.5; }
        div[data-testid="stButton"] > button, div[data-testid="stFormSubmitButton"] > button {
            border-radius: 8px; border: 1px solid rgba(198,245,107,.4); background: var(--sf-lime); color:#0b100f;
            font-weight:800; min-height: 2.45rem;
        }
        div[data-testid="stButton"] > button:hover, div[data-testid="stFormSubmitButton"] > button:hover { border-color:var(--sf-lime); background:#d7ff8c; color:#0b100f; }
        button[kind="secondary"] { background:transparent !important; color:var(--sf-text) !important; border-color:var(--sf-border) !important; }
        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
            background:rgba(9,15,13,.7); border-color:var(--sf-border); color:var(--sf-text);
        }
        [data-testid="stDataFrame"] { border:1px solid var(--sf-border); border-radius:10px; overflow:hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def safe_text(value: Any, fallback: str = "—") -> str:
    if value is None or value == "":
        return escape(fallback)
    return escape(str(value))


def title_case(value: Any) -> str:
    raw_value = str(value or "").strip()
    return safe_text(DISPLAY_LABELS.get(raw_value.lower(), raw_value.replace("_", " ").title()))


def load_data() -> tuple[list[dict], list[dict], list[dict]]:
    db_tools.ensure_db()
    queue = list_ticket_queue()
    pending = list_pending_reviews()
    runs = db_tools.list_workflow_runs()
    return queue, pending, runs


def seed_demo_dataset() -> bool:
    db_tools.ensure_db()
    if db_tools.count_tickets(DEMO_SOURCE_DATASET):
        return False
    import_tickets_from_csv(str(DEMO_CSV), str(DEMO_MAPPING), force=False)
    return True


def run_for_ticket(ticket_id: int, runs: list[dict]) -> dict | None:
    for run in runs:
        if run.get("ticket_id") == ticket_id:
            return run
    return None


def trace_has(trace: list[str], prefix: str) -> bool:
    return any(item.lower().startswith(prefix.lower()) for item in trace)


def stage_state(stage_key: str, run: dict | None) -> str:
    if not run:
        return "blocked"
    state = run.get("state") or {}
    trace = state.get("workflow_trace") or []
    status = run.get("status")

    if stage_key == "triage_agent":
        return "complete" if trace_has(trace, "Triage ->") else "active"
    if stage_key == "resolution_agent":
        return "complete" if trace_has(trace, "Resolution ->") else "blocked"
    if stage_key == "policy_agent":
        return "complete" if trace_has(trace, "Policy ->") else "blocked"
    if stage_key == "human_review":
        if trace_has(trace, "Review ->"):
            return "complete"
        return "active" if status == "awaiting_review" else "blocked"
    if stage_key == "finalize_action":
        if trace_has(trace, "Finalization ->"):
            return "complete"
        return "active" if status == "running" else "blocked"
    return "blocked"


def render_sidebar(queue: list[dict], pending: list[dict]) -> None:
    st.sidebar.markdown(
        '<div class="brand-lockup"><div class="brand-mark">✦</div><div><div class="brand-name">SupportFlow</div><div class="brand-sub">Kontrollierte KI-Unterstützung</div></div></div>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown('<div class="eyebrow">Arbeitsbereich</div>', unsafe_allow_html=True)
    st.sidebar.markdown("### Operations-Konsole")
    st.sidebar.caption("Eine Live-Ansicht von Triage, Lösung, Richtlinie und menschlicher Kontrolle.")
    st.sidebar.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)

    st.sidebar.markdown(
        f'<div class="key-row"><span>Offene Tickets</span><span>{len(queue):02d}</span></div>'
        f'<div class="key-row"><span>Benötigen Prüfung</span><span style="color:var(--sf-coral)">{len(pending):02d}</span></div>'
        '<div class="key-row"><span>Laufzeit</span><span style="color:var(--sf-lime)">SQLite lokal</span></div>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="eyebrow">Demo-Steuerung</div>', unsafe_allow_html=True)
    if st.sidebar.button("Demo-Ticketwarteschlange laden", width="stretch"):
        loaded = seed_demo_dataset()
        st.session_state["notice"] = (
            "Demo-Tickets aus dem CSV-Datensatz geladen."
            if loaded
            else "Der Demo-Datensatz ist bereits geladen; es wurden keine Duplikate erstellt."
        )
        st.rerun()
    if st.sidebar.button("Arbeitsbereich aktualisieren", width="stretch", type="secondary"):
        st.rerun()
    st.sidebar.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
    st.sidebar.markdown(
        '<div class="small-note">Richtlinienentscheidungen sind deterministisch und werden vom Projekt kontrolliert. Das Modell erstellt nur einen Lösungsvorschlag.</div>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
    llm_config = get_llm_config()
    if llm_config.demo_mode:
        provider_label = "Interview-Demo"
        provider_name = "deterministisch"
        model_name = "lokal, kein Modellaufruf"
        provider_status = "aktiv"
        provider_color = "var(--sf-lime)"
    else:
        provider_label = "Modellanbieter"
        provider_name = llm_config.provider or "OpenAI-kompatibel"
        model_name = llm_config.model or "nicht angegeben"
        provider_status = "konfiguriert" if llm_config.is_configured else "nicht konfiguriert"
        provider_color = "var(--sf-lime)" if llm_config.is_configured else "var(--sf-amber)"
    st.sidebar.markdown(
        f'<div class="key-row"><span>{provider_label}</span><span style="color:{provider_color}">{provider_status}</span></div>'
        f'<div class="key-row"><span>Profil</span><span>{safe_text(provider_name)}</span></div>'
        f'<div class="key-row"><span>Modell</span><span>{safe_text(model_name)}</span></div>',
        unsafe_allow_html=True,
    )


def render_metrics(queue: list[dict], pending: list[dict], runs: list[dict]) -> None:
    completed = sum(run.get("status") == "completed" for run in runs)
    failed = sum(run.get("status") in {"failed", "rejected"} for run in runs)
    metrics = (
        ("Offene Tickets", len(queue), "nach Priorität sortiert"),
        ("Warten auf Prüfung", len(pending), "menschliche Prüfung aktiv"),
        ("Lokal abgeschlossen", completed, "Fallakten gespeichert"),
        ("Ausnahmen", failed, "fehlgeschlagene oder abgelehnte Läufe"),
    )
    columns = st.columns(4)
    for column, (label, value, note) in zip(columns, metrics):
        with column:
            st.markdown(
                f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value:02d}</div><div class="metric-note">{note}</div></div>',
                unsafe_allow_html=True,
            )


def render_queue(queue: list[dict]) -> int | None:
    st.markdown('<div class="panel-title"><h3>Ticketwarteschlange</h3><span class="panel-kicker">Prioritätsbasiert · CSV-gestützt</span></div>', unsafe_allow_html=True)
    if not queue:
        st.markdown(
            '<div class="empty-state">Noch keine offenen Tickets geladen.<br><br>Nutze <strong>Demo-Ticketwarteschlange laden</strong> in der Seitenleiste, um den bereitgestellten Datensatz zu importieren.</div>',
            unsafe_allow_html=True,
        )
        return None

    rows = [
        {
            "Ticket": ticket["ticket_id"],
            "Kunde": ticket["customer_name"],
            "Anliegen": ticket["subject"],
            "Priorität": title_case(ticket.get("priority")),
            "Kanal": safe_text(ticket.get("channel")),
            "Status": title_case(ticket.get("status")),
        }
        for ticket in queue
    ]
    st.dataframe(rows, width="stretch", hide_index=True, height=min(390, 92 + len(rows) * 48))
    ticket_labels = {
        ticket["id"]: f'{ticket["ticket_id"]} · {ticket["subject"]}' for ticket in queue
    }
    return st.selectbox(
        "Ticket untersuchen",
        options=list(ticket_labels),
        format_func=lambda ticket_id: ticket_labels[ticket_id],
        label_visibility="collapsed",
    )


def render_run_history(runs: list[dict]) -> dict | None:
    """Let the operator reopen persisted runs, including finalized tickets."""
    if not runs:
        return None
    run_labels = {"": "Keine gespeicherte Fallakte öffnen"}
    run_labels.update(
        {
            run["run_id"]: f'{run["run_id"]} · {title_case(run.get("status"))}'
            for run in reversed(runs)
        }
    )
    selected_run_id = st.selectbox(
        "Gespeicherten Lauf öffnen",
        options=list(run_labels),
        format_func=lambda run_id: run_labels[run_id],
    )
    if not selected_run_id:
        return None
    return next(run for run in runs if run["run_id"] == selected_run_id)


def render_timeline(run: dict | None, ticket: dict | None) -> None:
    ticket_reference = safe_text((ticket or {}).get("ticket_id"), "Kein Ticket ausgewählt")
    st.markdown(
        f'<div class="panel-title"><div><h3>Agenten-Timeline</h3><span class="panel-kicker">{ticket_reference}</span></div><span class="live-pill"><span class="live-dot"></span>{title_case((run or {}).get("status", "queued"))}</span></div>',
        unsafe_allow_html=True,
    )
    state = (run or {}).get("state") or {}
    action = state.get("proposed_action") or {}
    descriptions = {
        "triage_agent": f'Klassifikation: {title_case(state.get("classification"))} · Quelle: {safe_text(state.get("triage_source"), "ausstehend")}',
        "resolution_agent": f'Vorschlag: {title_case(action.get("action_type"))} · {safe_text(action.get("discount_percent", 0))}% Rabatt',
        "policy_agent": f'Urteil: {title_case(action.get("policy_outcome"))} · Quelle: deterministic_policy',
        "human_review": safe_text(action.get("approval_reason"), "Für diesen Vorschlag ist keine menschliche Prüfung erforderlich"),
        "finalize_action": safe_text(state.get("finalization_result"), "Der Workflow ist noch nicht abgeschlossen"),
    }
    for stage_key, label in AGENT_STAGES:
        status = stage_state(stage_key, run)
        icon = "✓" if status == "complete" else ("•" if status == "active" else "")
        st.markdown(
            f'<div class="timeline-item"><div class="timeline-node {status}">{icon}</div><div><div class="timeline-name">{label}</div><div class="timeline-desc">{descriptions[stage_key]}</div><div class="timeline-meta">{title_case(status)}</div></div></div>',
            unsafe_allow_html=True,
        )


def render_ticket_detail(ticket: dict | None, run: dict | None) -> None:
    if not ticket:
        st.markdown('<div class="empty-state">Wähle ein Ticket aus, um den Fall zu untersuchen.</div>', unsafe_allow_html=True)
        return
    st.markdown(
        f'<div class="panel-title"><h3>Ausgewählter Fall</h3><span class="chip">Priorität: {title_case(ticket.get("priority"))}</span></div>'
        f'<div class="ticket-highlight"><div class="ticket-id">{safe_text(ticket.get("ticket_id"))}</div><div class="ticket-subject">{safe_text(ticket.get("subject"))}</div><div class="ticket-customer">{safe_text(ticket.get("customer_name"))} · {safe_text(ticket.get("customer_email"))}</div></div>',
        unsafe_allow_html=True,
    )
    for label, value in (
        ("Kategorie", title_case(ticket.get("category"))),
        ("Produkt", safe_text(ticket.get("product"))),
        ("Kanal", safe_text(ticket.get("channel"))),
        ("Ticketstatus", title_case(ticket.get("status"))),
    ):
        st.markdown(f'<div class="key-row"><span>{label}</span><span>{value}</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
    st.markdown('<div class="small-note">Kundennachricht</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="proposal-copy">{safe_text(ticket.get("description"))}</div>', unsafe_allow_html=True)
    if run is None:
        if st.button("Agenten für dieses Ticket starten", width="stretch"):
            st.session_state["run_result"] = start_ticket_run(int(ticket["id"]))
            st.rerun()
    else:
        st.markdown(f'<div class="small-note" style="margin-top:1rem">Lauf <span class="mono">{run["run_id"]}</span> · {title_case(run.get("status"))}</div>', unsafe_allow_html=True)


def render_proposal_and_policy(run: dict | None) -> None:
    st.markdown('<div class="panel-title"><h3>Entscheidungsübersicht</h3><span class="panel-kicker">Vorschlag → Richtlinie → Aktion</span></div>', unsafe_allow_html=True)
    if not run:
        st.markdown('<div class="empty-state">Starte einen Ticketlauf, um Vorschlag und Richtlinienbelege zu sehen.</div>', unsafe_allow_html=True)
        return
    state = run.get("state") or {}
    action = state.get("proposed_action") or {}
    is_policy_rejection = bool(action.get("rejected"))
    if run.get("status") == "failed" and not is_policy_rejection:
        error_message = str(run.get("error_message") or "")
        if "configuration" in error_message.lower():
            st.error(
                "Der Modellanbieter ist nicht vollständig konfiguriert. Setze "
                "LLM_API_KEY, LLM_BASE_URL und LLM_MODEL oder aktiviere "
                "SUPPORTFLOW_DEMO_MODE=true."
            )
        else:
            st.error(
                "Dieser Workflow-Lauf ist fehlgeschlagen, bevor eine Fallakte "
                "gespeichert werden konnte. Der Fehlerstatus bleibt im Lauf erhalten."
            )
        return
    case_file = run.get("case_file") or {}
    policy = case_file.get("policy_review") or {}
    if is_policy_rejection:
        st.warning("Der Vorschlag wurde von der deterministischen Richtlinie abgelehnt und nicht ausgeführt.")
    st.markdown(
        f'<div class="proposal-box"><strong>Vorschlag des Lösungsagenten</strong><div class="proposal-main">{title_case(action.get("action_type"))} · {safe_text(action.get("discount_percent", 0))}%</div><div class="proposal-copy" style="margin-top:.55rem">{safe_text(action.get("business_reason"))}</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
    policy_outcome = policy.get("outcome") or action.get("policy_outcome")
    policy_class = "policy-review" if policy_outcome in {"needs_approval", "rejected"} else "policy-pass"
    if policy_outcome == "needs_approval":
        policy_title = "Menschliche Freigabe erforderlich"
    elif policy_outcome == "rejected":
        policy_title = "Durch Richtlinie abgelehnt"
    else:
        policy_title = title_case(policy_outcome)
    rules = policy.get("policy_rules") or action.get("policy_rules") or []
    rule_html = "".join(
        f'<div class="policy-rule">{safe_text(rule)}</div>' for rule in rules
    ) or '<div class="policy-rule">Keine Freigaberegel der festen Richtlinie wurde ausgelöst.</div>'
    st.markdown(
        f'<div class="policy-box"><strong>Deterministisches Richtlinienurteil</strong><div class="{policy_class}">{safe_text(policy_title)}</div><div class="proposal-copy" style="margin-top:.4rem">Entscheidungsquelle: <span class="mono">{safe_text(policy.get("decision_source"), "deterministic_policy")}</span></div>{rule_html}</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
    draft = action.get("customer_message") or case_file.get("customer_draft")
    st.markdown(
        f'<div class="draft-box"><strong>Kundenentwurf · Deutsch</strong><div class="proposal-copy">{safe_text(draft, "Kein Kundenentwurf vorhanden")}</div></div>',
        unsafe_allow_html=True,
    )
    with st.expander("Strukturierte Fallakte öffnen"):
        st.json(case_file or {"status": run.get("status"), "case_file": "not available"})


def render_review_panel(run: dict | None) -> None:
    if not run or run.get("status") != "awaiting_review":
        return
    st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="callout" style="padding:1rem 1.1rem;border-color:rgba(255,140,115,.5);background:rgba(255,140,115,.06)"><div class="eyebrow" style="color:var(--sf-coral)">Menschliche Prüfung aktiv</div><div style="font-size:1.05rem;font-weight:800;margin:.35rem 0">Dieser Vorschlag kann sich nicht selbst abschließen.</div><div class="small-note">Prüfe den deutschen Kundenentwurf und die deterministischen Richtlinienbelege, bevor du den Lauf freigibst oder ablehnst.</div></div>',
        unsafe_allow_html=True,
    )
    with st.form(f"review-{run['run_id']}"):
        reviewer = st.text_input("Prüfer:in", value=os.getenv("USERNAME") or "interview-reviewer")
        notes = st.text_area("Prüfnotizen", placeholder="Warum ist diese Entscheidung lokal sicher ausführbar?")
        edited_draft = st.text_area(
            "Optional bearbeiteter Kundenentwurf",
            value=((run.get("state") or {}).get("proposed_action") or {}).get("customer_message", ""),
            height=130,
        )
        approve, reject = st.columns(2)
        approve_clicked = approve.form_submit_button("Freigeben & abschließen", width="stretch")
        reject_clicked = reject.form_submit_button("Vorschlag ablehnen", width="stretch")
    if not (approve_clicked or reject_clicked):
        return
    decision = "approve" if approve_clicked else "reject"
    try:
        st.session_state["run_result"] = review_run(
            run["run_id"],
            {
                "decision": decision,
                "reviewer": reviewer,
                "notes": notes,
                "edited_draft": edited_draft,
            },
        )
        st.rerun()
    except (LookupError, ValueError) as exc:
        st.error(str(exc))


def main() -> None:
    inject_styles()
    queue, pending, runs = load_data()
    render_sidebar(queue, pending)

    st.markdown(
        '<div class="page-intro"><div><div class="eyebrow">Support Operations / Live-Arbeitsbereich</div><h1>Agentenarbeit sichtbar machen.</h1><p>Verfolge jedes Ticket von der Metadaten-Triage bis zur lokal gespeicherten Fallakte – mit deterministischer Richtlinie und sichtbarer menschlicher Prüfstelle.</p></div><span class="live-pill"><span class="live-dot"></span>Laufzeit lokal online</span></div>',
        unsafe_allow_html=True,
    )
    notice = st.session_state.pop("notice", None)
    if notice:
        st.success(notice)
    render_metrics(queue, pending, runs)
    st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)

    selected_ticket_id = render_queue(queue)
    saved_run = render_run_history(runs)
    if saved_run is not None:
        selected_ticket_id = int(saved_run["ticket_id"])
    if selected_ticket_id is not None:
        st.session_state["last_ticket_id"] = selected_ticket_id
    selected_ticket_id = selected_ticket_id or st.session_state.get("last_ticket_id")
    selected_ticket = next((ticket for ticket in queue if ticket["id"] == selected_ticket_id), None)
    if selected_ticket is None and selected_ticket_id is not None:
        selected_ticket = db_tools.query_ticket_by_id(int(selected_ticket_id))
    selected_run = saved_run or (run_for_ticket(selected_ticket_id, runs) if selected_ticket_id else None)
    if st.session_state.get("run_result"):
        result = st.session_state.pop("run_result")
        selected_run = result
        if result and result.get("ticket"):
            selected_ticket = result["ticket"]

    st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
    left, middle, right = st.columns([1.05, 1.25, 1.35], gap="medium")
    with left:
        with st.container(border=True):
            render_ticket_detail(selected_ticket, selected_run)
    with middle:
        with st.container(border=True):
            render_timeline(selected_run, selected_ticket)
    with right:
        with st.container(border=True):
            render_proposal_and_policy(selected_run)

    render_review_panel(selected_run)
    st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
    with st.expander("So ist diese Demo verbunden"):
        st.markdown(
            "Die Oberfläche verwendet `list_ticket_queue()`, `start_ticket_run()`, `list_pending_reviews()`, `review_run()` und `get_run()` aus der bestehenden Service-Grenze. SQLite bleibt der Laufzeitdatenspeicher; die CSV bleibt der importierte Quelldatensatz; der feste Richtliniencode kontrolliert Freigabe- und Risikoentscheidungen."
        )
        st.code(json.dumps({"workflow": [label for _, label in AGENT_STAGES], "database": db_tools.DB_PATH}, indent=2), language="json")


if __name__ == "__main__":
    main()
