from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from agent import classify_all
from email_loader import load_emails
from enricher import enrich_classified_emails
from escalator import trigger_call

load_dotenv()

st.set_page_config(page_title="InboxROI Agent", layout="wide")


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
          --bg: #fbf9f4;
          --card: #f0ece4;
          --border: #ded8cc;
          --text: #1f1f1f;
          --muted: #666055;
          --accent: #d65b4a;
          --amber: #b67a2a;
          --green: #2f6a4f;
        }

        .stApp {
          background:
            radial-gradient(circle at top left, rgba(214, 91, 74, 0.06), transparent 24%),
            linear-gradient(180deg, #fcfbf8 0%, #f7f3ec 100%);
        }

        .top-shell {
          background: rgba(255, 255, 255, 0.84);
          border: 1px solid var(--border);
          border-radius: 24px;
          padding: 1.4rem 1.8rem 1.8rem;
          box-shadow: 0 14px 40px rgba(37, 32, 24, 0.06);
        }

        .title-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 1rem;
          margin-bottom: 1.2rem;
        }

        .brand {
          font-size: 2rem;
          font-weight: 700;
          letter-spacing: -0.03em;
          color: var(--text);
        }

        .brand span {
          color: var(--accent);
        }

        .run-meta {
          color: var(--muted);
          font-size: 1.0rem;
        }

        .metric-card {
          background: var(--card);
          border-radius: 18px;
          border: 1px solid rgba(214, 208, 197, 0.75);
          padding: 1rem 1.2rem;
          min-height: 118px;
        }

        .metric-label {
          font-size: 0.9rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--muted);
        }

        .metric-value {
          font-size: 2.15rem;
          font-weight: 700;
          line-height: 1.1;
          margin-top: 0.55rem;
          color: var(--text);
        }

        .metric-value.alert {
          color: var(--accent);
        }

        .metric-value.warm {
          color: var(--amber);
        }

        .table-head {
          margin-top: 1.5rem;
          padding: 0 1rem 0.75rem;
          border-bottom: 1px solid var(--border);
          color: var(--muted);
          font-size: 0.86rem;
          text-transform: uppercase;
          letter-spacing: 0.06em;
        }

        .sender-block {
          display: flex;
          gap: 0.6rem;
          align-items: flex-start;
        }

        .sender-dot {
          width: 10px;
          height: 10px;
          border-radius: 999px;
          margin-top: 0.52rem;
          background: var(--accent);
          flex: 0 0 auto;
        }

        .sender-name {
          font-size: 1.1rem;
          font-weight: 650;
          color: var(--text);
        }

        .sender-meta {
          color: var(--muted);
          font-size: 0.98rem;
          line-height: 1.35;
        }

        .priority-pill {
          display: inline-block;
          border-radius: 10px;
          padding: 0.18rem 0.62rem;
          font-weight: 650;
          font-size: 0.92rem;
        }

        .p0 { background: #f8e4e0; color: #b34739; }
        .p1 { background: #f4e7cf; color: #9c6a22; }
        .p2 { background: #e7ecef; color: #576675; }
        .p3 { background: #ece9e2; color: #6d665e; }

        .row-summary {
          font-size: 1.02rem;
          color: var(--text);
          margin-bottom: 0.2rem;
        }

        .intel {
          color: var(--muted);
          font-size: 0.92rem;
          line-height: 1.4;
        }

        .cost {
          font-size: 1.1rem;
          font-weight: 650;
          color: var(--text);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def cached_load_emails() -> list[dict[str, Any]]:
    return load_emails()


def relative_run_time(iso_timestamp: str | None, scanned_count: int) -> str:
    if not iso_timestamp:
        return f"{scanned_count} emails loaded"
    try:
        then = datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return f"{scanned_count} emails scanned"

    now = datetime.now(timezone.utc)
    delta = max(0, int((now - then).total_seconds()))
    if delta < 60:
        ago = "just now"
    elif delta < 3600:
        ago = f"{delta // 60} min ago"
    else:
        ago = f"{delta // 3600} hr ago"
    return f"{scanned_count} emails scanned · last run {ago}"


def get_action_label(action: str) -> str:
    labels = {
        "respond_1h": "Respond in 1h",
        "respond_24h": "Respond in 24h",
        "respond_72h": "Respond in 72h",
        "archive": "Auto-archive",
    }
    return labels.get(action, action.replace("_", " "))


def compute_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    p0_count = sum(1 for item in results if item.get("priority") == "P0")
    total_at_risk = sum(int(item.get("cost_to_ignore", 0)) for item in results)
    drafts_ready = sum(1 for item in results if item.get("suggested_action") != "archive")
    non_archive = [item for item in results if int(item.get("sla_hours", 0)) > 0]
    avg_sla = round(sum(int(item["sla_hours"]) for item in non_archive) / len(non_archive), 1) if non_archive else 0
    return {
        "p0_count": p0_count,
        "total_at_risk": total_at_risk,
        "emails_scanned": len(results),
        "drafts_ready": drafts_ready,
        "avg_sla": avg_sla,
    }


def run_pipeline(emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    classified = classify_all(emails)
    return enrich_classified_emails(classified)


def ensure_session_defaults(emails: list[dict[str, Any]]) -> None:
    if "results" not in st.session_state:
        st.session_state["results"] = []
    if "last_run" not in st.session_state:
        st.session_state["last_run"] = None
    if "open_detail_id" not in st.session_state:
        st.session_state["open_detail_id"] = None
    if "call_results" not in st.session_state:
        st.session_state["call_results"] = {}
    if not st.session_state["results"] and not os.getenv("BASETEN_API_KEY"):
        st.session_state["results"] = run_pipeline(emails)
        st.session_state["last_run"] = datetime.now(timezone.utc).isoformat()


def render_setup_banner() -> None:
    missing = []
    if not os.getenv("BASETEN_API_KEY"):
        missing.append("Baseten")
    if not os.getenv("YOUCOM_API_KEY"):
        missing.append("You.com")
    if not os.getenv("VOICERUN_API_KEY"):
        missing.append("VoiceRun")

    if missing:
        st.info(
            "Demo mode is active for: "
            + ", ".join(missing)
            + ". The app still works with bundled data and safe fallbacks."
        )


def render_metric_cards(metrics: dict[str, Any]) -> None:
    columns = st.columns(4)
    cards = [
        ("P0 Unread", str(metrics["p0_count"]), "alert"),
        ("Total At Risk", f"${metrics['total_at_risk'] / 1000:,.0f}K", "alert"),
        ("Avg Response SLA", f"{metrics['avg_sla']} hrs", "warm"),
        ("Drafts Ready", str(metrics["drafts_ready"]), ""),
    ]

    for column, (label, value, variant) in zip(columns, cards):
        with column:
            st.markdown(
                f"""
                <div class="metric-card">
                  <div class="metric-label">{label}</div>
                  <div class="metric-value {variant}">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def sender_meta(email: dict[str, Any]) -> str:
    pieces = []
    intel = email.get("company_intel") or {}
    if intel.get("company"):
        pieces.append(intel["company"])
    if email.get("company_domain"):
        pieces.append(email["company_domain"])
    if not pieces:
        pieces.append(email.get("sender_email", ""))
    return " · ".join(piece for piece in pieces if piece)


def render_results(results: list[dict[str, Any]]) -> None:
    st.markdown(
        """
        <div class="table-head">
          <div style="display:grid;grid-template-columns:2.2fr 1fr 3.2fr 1.5fr 1.7fr;gap:1rem;">
            <div>Sender</div>
            <div>Priority</div>
            <div>Summary</div>
            <div>Cost To Ignore</div>
            <div>Action</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for email in results:
        email_id = email["id"]
        priority = str(email.get("priority", "P2")).lower()
        summary = email.get("summary", "No summary")
        intel = email.get("company_intel") or {}

        with st.container(border=False):
            cols = st.columns([2.2, 0.9, 3.2, 1.5, 1.7], vertical_alignment="center")

            with cols[0]:
                dot = "" if email.get("priority") != "P0" else '<div class="sender-dot"></div>'
                st.markdown(
                    f"""
                    <div class="sender-block">
                      {dot}
                      <div>
                        <div class="sender-name">{email.get('sender_name')}</div>
                        <div class="sender-meta">{sender_meta(email)}</div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with cols[1]:
                st.markdown(
                    f'<span class="priority-pill {priority}">{email.get("priority")}</span>',
                    unsafe_allow_html=True,
                )

            with cols[2]:
                intel_line = ""
                if intel:
                    intel_line = f'<div class="intel">Company Intel: {intel.get("snippet", "")}</div>'
                st.markdown(
                    f"""
                    <div class="row-summary">{summary}</div>
                    {intel_line}
                    """,
                    unsafe_allow_html=True,
                )

            with cols[3]:
                st.markdown(
                    f'<div class="cost">${int(email.get("cost_to_ignore", 0)):,.0f}</div>',
                    unsafe_allow_html=True,
                )

            with cols[4]:
                if email.get("priority") == "P0":
                    if st.button("Call me now", key=f"call-{email_id}", use_container_width=True):
                        st.session_state["call_results"][email_id] = trigger_call(email)
                if email.get("suggested_action") == "archive":
                    st.caption("Auto-archived")
                else:
                    if st.button("Draft reply", key=f"draft-{email_id}", use_container_width=True):
                        st.session_state["open_detail_id"] = email_id

            call_result = st.session_state["call_results"].get(email_id)
            if call_result:
                message_type = st.warning if call_result.get("simulated") else st.success
                message_type(call_result["message"])

            with st.expander(
                "Details",
                expanded=st.session_state.get("open_detail_id") == email_id or email.get("priority") == "P0",
            ):
                left, right = st.columns([1.35, 1])
                with left:
                    st.write(f"**Subject:** {email.get('subject')}")
                    st.write(f"**Suggested action:** {get_action_label(email.get('suggested_action', 'respond_24h'))}")
                    st.write(f"**Confidence:** {float(email.get('confidence', 0)):.0%}")
                    st.write(f"**Category:** {email.get('category')}")
                    st.write("**Body excerpt:**")
                    st.write(email.get("body") or "_No body available_")
                with right:
                    st.write("**Draft opening**")
                    st.code(email.get("draft_opening") or "No draft available.", language="text")
                    if intel:
                        st.write("**Company intel source**")
                        st.write(intel.get("source_url") or "Bundled demo data")
                    if call_result:
                        st.write("**VoiceRun script**")
                        st.code(call_result.get("script", ""), language="text")


inject_styles()
emails = cached_load_emails()
ensure_session_defaults(emails)

with st.container():
    results = st.session_state["results"]
    metrics = compute_metrics(results) if results else {"p0_count": 0, "total_at_risk": 0, "emails_scanned": len(emails), "drafts_ready": 0, "avg_sla": 0}

    st.markdown('<div class="top-shell">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="title-row">
          <div class="brand">Inbox<span>ROI</span> Agent</div>
          <div class="run-meta">{relative_run_time(st.session_state.get('last_run'), metrics['emails_scanned'])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_setup_banner()

    actions_left, actions_right = st.columns([1, 3])
    with actions_left:
        if st.button("Scan & Classify", type="primary", use_container_width=True):
            with st.spinner("Scanning inbox and classifying priority..."):
                st.session_state["results"] = run_pipeline(emails)
                st.session_state["last_run"] = datetime.now(timezone.utc).isoformat()
            st.rerun()

    if st.session_state["results"]:
        render_metric_cards(compute_metrics(st.session_state["results"]))
        render_results(st.session_state["results"])
    else:
        st.caption("Click 'Scan & Classify' to process the bundled 20-email demo inbox.")

    st.markdown("</div>", unsafe_allow_html=True)
