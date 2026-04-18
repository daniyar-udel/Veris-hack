from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
SLA_HOURS = {
    "respond_5min": 0.08,
    "respond_1h": 1,
    "respond_24h": 24,
    "respond_72h": 72,
    "archive": 0,
}

CLASSIFICATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
        "category": {
            "type": "string",
            "enum": ["inbound_lead", "customer", "vendor", "internal", "spam"],
        },
        "summary": {"type": "string"},
        "cost_to_ignore": {"type": "integer", "minimum": 0},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "suggested_action": {
            "type": "string",
            "enum": ["respond_5min", "respond_1h", "respond_24h", "respond_72h", "archive"],
        },
        "draft_opening": {"type": "string"},
    },
    "required": [
        "priority",
        "category",
        "summary",
        "cost_to_ignore",
        "confidence",
        "suggested_action",
        "draft_opening",
    ],
}


def extract_email_address(from_value: str) -> str:
    match = re.search(r"<([^>]+)>", from_value or "")
    if match:
        return match.group(1).strip().lower()
    return (from_value or "").strip().strip('"').lower()


def extract_sender_name(from_value: str) -> str:
    text = (from_value or "").strip()
    if not text:
        return "Unknown sender"
    match = re.match(r'"?([^"<]+?)"?\s*<', text)
    if match:
        return match.group(1).strip()
    local_part = extract_email_address(text).split("@", 1)[0]
    return local_part.replace(".", " ").replace("_", " ").title()


def build_classification_prompt(email: dict[str, Any]) -> str:
    return (
        "Classify this inbound email for a revenue-focused inbox triage assistant.\n"
        "Return strict JSON only.\n\n"
        f"From: {email.get('from', '')}\n"
        f"Subject: {email.get('subject', '')}\n"
        f"Hint: {email.get('hint', '')}\n"
        f"Body:\n{email.get('body', '')}\n"
    )


def clamp_confidence(value: Any, default: float = 0.65) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return round(max(0.0, min(1.0, numeric)), 2)


def parse_money_mentions(text: str) -> int:
    best_value = 0.0
    pattern = re.compile(r"\$?\s*(\d[\d,]*(?:\.\d+)?)\s*([kKmM]?)")
    for match in pattern.finditer(text or ""):
        raw_number, suffix = match.groups()
        number = float(raw_number.replace(",", ""))
        if suffix.lower() == "k":
            number *= 1_000
        elif suffix.lower() == "m":
            number *= 1_000_000
        if number >= best_value:
            best_value = number

    if best_value <= 0:
        return 0
    if best_value >= 100_000:
        return int(best_value * 0.24)
    if best_value >= 25_000:
        return int(best_value * 0.35)
    return int(best_value * 0.5)


def normalize_classification(raw: dict[str, Any], email: dict[str, Any]) -> dict[str, Any]:
    priority = raw.get("priority", "P2")
    if priority not in PRIORITY_ORDER:
        priority = "P2"

    category = raw.get("category", "vendor")
    if category not in {"inbound_lead", "customer", "vendor", "internal", "spam"}:
        category = "vendor"

    suggested_action = raw.get("suggested_action", "respond_24h")
    if suggested_action not in SLA_HOURS:
        suggested_action = "respond_24h"

    cost_to_ignore = raw.get("cost_to_ignore", 0)
    try:
        cost_to_ignore = max(0, int(cost_to_ignore))
    except (TypeError, ValueError):
        cost_to_ignore = 0

    summary = str(raw.get("summary") or email.get("subject") or "Inbox item needs review").strip()
    draft_opening = str(
        raw.get("draft_opening")
        or f"Hi {extract_sender_name(email.get('from', ''))}, thanks for reaching out."
    ).strip()

    normalized = {
        "priority": priority,
        "category": category,
        "summary": summary,
        "cost_to_ignore": cost_to_ignore,
        "confidence": clamp_confidence(raw.get("confidence"), 0.7),
        "suggested_action": suggested_action,
        "draft_opening": draft_opening,
    }

    normalized["sender_name"] = extract_sender_name(email.get("from", ""))
    normalized["sender_email"] = extract_email_address(email.get("from", ""))
    normalized["sla_hours"] = SLA_HOURS[normalized["suggested_action"]]
    return normalized


def classify_with_baseten(email: dict[str, Any]) -> dict[str, Any] | None:
    api_key = os.getenv("BASETEN_API_KEY")
    if not api_key:
        return None

    base_url = os.getenv("BASETEN_BASE_URL", "https://inference.baseten.co/v1").rstrip("/")
    model = os.getenv("BASETEN_MODEL", "meta-llama/Llama-4-Scout-17B-16E-Instruct")

    headers = {
        "Authorization": f"Api-Key {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": 0,
        "seed": 42,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are LeadGuard, an AI revenue triage assistant for B2B SaaS sales teams. "
                    "Classify inbound emails by urgency and revenue impact. "
                    "Return strict JSON only, no markdown.\n\n"
                    "PRIORITY RULES — apply in order, stop at first match:\n\n"
                    "P0 — All three must be explicitly stated in the email:\n"
                    "  1. Sender role shows decision-making authority (VP, Director, CEO, CIO, procurement lead, steering committee member)\n"
                    "  2. A specific dollar budget is mentioned (e.g. '$500K', '$380,000')\n"
                    "  3. A hard deadline within 7 days is stated (e.g. 'today', 'by Thursday', '48 hours', 'close of business', 'this week')\n"
                    "  If any one of the three is missing, do not assign P0.\n\n"
                    "P0 VERIFICATION — Before assigning P0, you must be able to quote all three directly from the email text:\n"
                    "  - The exact dollar figure (e.g. '$500K')\n"
                    "  - The exact deadline phrase (e.g. 'by Thursday')\n"
                    "  - The sender's explicit job title or authority role\n"
                    "  If you cannot quote all three verbatim from the email, you must assign P1 or lower.\n\n"
                    "P1 — Strong buying signal present. Examples: vendor shortlist, active procurement, pricing request, "
                    "implementation timeline discussion, existing customer renewal or expansion, pilot evaluation in progress. "
                    "Budget OR urgency present but not both.\n\n"
                    "P2 — Early-stage interest only. No budget, no deadline, no active procurement. "
                    "Sender is exploring, asking general questions, or requesting an intro with no commitment signals.\n\n"
                    "P3 — Spam, phishing, newsletters, event invitations, internal digests, billing notices, "
                    "'final notice' or 'wire transfer' emails, no-reply senders, personal curiosity with no business context. "
                    "Always: suggested_action = 'archive', cost_to_ignore = 0.\n\n"
                    "CATEGORY RULES:\n"
                    "- inbound_lead: new prospect reaching out for the first time\n"
                    "- customer: existing customer (mentions renewal, current contract, pilot already started, expansion)\n"
                    "- vendor: someone trying to sell you something\n"
                    "- internal: your own company domain\n"
                    "- spam: unsolicited, fraudulent, or irrelevant\n\n"
                    "COST TO IGNORE:\n"
                    "- If an explicit dollar amount is written in the email body, use it directly.\n"
                    "- If no dollar amount is written in the email body, set to 0. No exceptions.\n"
                    "- Do not estimate, infer, or derive a number from context, company size, or deal signals.\n\n"
                    "SUGGESTED ACTION — must match priority exactly:\n"
                    "- P0 → respond_5min\n"
                    "- P1 → respond_1h\n"
                    "- P2 → respond_72h\n"
                    "- P3 → archive\n\n"
                    "STRICT RULE — Base every field on evidence in the email only. "
                    "Do not infer authority, budget, or deadlines not written in the email. "
                    "If no clear business evidence exists, classify as P3 and archive."
                ),
            },
            {"role": "user", "content": build_classification_prompt(email)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "email_triage",
                "strict": True,
                "schema": CLASSIFICATION_SCHEMA,
            },
        },
    }

    response = requests.post(
        f"{base_url}/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
        )

    parsed = json.loads(content)
    normalized = normalize_classification(parsed, email)
    normalized["classification_mode"] = "baseten"
    normalized["model_used"] = model
    return normalized


def heuristic_classification(email: dict[str, Any]) -> dict[str, Any]:
    subject = str(email.get("subject", ""))
    body = str(email.get("body", ""))
    hint = str(email.get("hint", ""))
    sender = extract_email_address(email.get("from", ""))
    sender_name = extract_sender_name(email.get("from", ""))
    text = f"{subject}\n{body}\n{hint}".lower()

    spam_signals = [
        "unsubscribe",
        "newsletter",
        "gift card",
        "wire transfer",
        "invoice overdue",
        "click here",
        "crypto",
        "final notice",
        "password reset",
    ]
    internal_signals = ["@inboxroi.ai", "@yourcompany.com", "@veris.ai"]
    customer_signals = ["renewal", "contract", "seats", "expansion", "existing customer", "upgrade"]
    lead_signals = [
        "budget",
        "demo",
        "procurement",
        "pilot",
        "rollout",
        "proposal",
        "rfp",
        "rfq",
        "vendor selection",
        "evaluate",
        "decision",
    ]
    urgent_signals = ["today", "tomorrow", "48h", "48 h", "this week", "urgent", "asap", "close of business"]

    if any(signal in text for signal in spam_signals) or sender.startswith(("newsletter@", "noreply@", "billing@")):
        raw = {
            "priority": "P3",
            "category": "spam",
            "summary": "Promotional or suspicious email with no clear business upside.",
            "cost_to_ignore": 0,
            "confidence": 0.96,
            "suggested_action": "archive",
            "draft_opening": "No response needed.",
        }
        return normalize_classification(raw, email)

    if any(signal in sender for signal in internal_signals):
        raw = {
            "priority": "P2",
            "category": "internal",
            "summary": "Internal coordination note that should be handled but is not revenue critical.",
            "cost_to_ignore": 0,
            "confidence": 0.83,
            "suggested_action": "respond_72h",
            "draft_opening": f"Hi {sender_name}, I saw this and will take a look.",
        }
        return normalize_classification(raw, email)

    category = "vendor"
    if any(signal in text for signal in customer_signals):
        category = "customer"
    elif any(signal in text for signal in lead_signals) or hint.upper() == "VIP":
        category = "inbound_lead"

    cost_to_ignore = parse_money_mentions(text)
    if hint.upper() == "VIP":
        cost_to_ignore = max(cost_to_ignore, 90_000)
    if "renewal" in text:
        cost_to_ignore = max(cost_to_ignore, 30_000)
    if "procurement" in text or "decision" in text or "budget" in text:
        cost_to_ignore = max(cost_to_ignore, 42_000)

    priority = "P2"
    confidence = 0.74

    if hint.upper() == "VIP" or (
        category in {"inbound_lead", "customer"}
        and any(signal in text for signal in urgent_signals)
        and cost_to_ignore >= 30_000
    ):
        priority = "P0"
        confidence = 0.91
    elif category in {"inbound_lead", "customer"} or cost_to_ignore >= 25_000:
        priority = "P1"
        confidence = 0.85

    suggested_action = {
        "P0": "respond_1h",
        "P1": "respond_24h",
        "P2": "respond_72h",
        "P3": "archive",
    }[priority]

    summary = subject.strip() or "Email requires triage"
    if priority == "P0" and category == "customer":
        summary = "High-value customer request with near-term revenue or renewal risk."
    elif priority == "P0":
        summary = "High-value lead with executive urgency and material upside."
    elif priority == "P1" and category == "customer":
        summary = "Important customer follow-up that may affect renewal or expansion."
    elif priority == "P1":
        summary = "Promising inbound opportunity worth responding to within a day."

    if category == "customer":
        draft = f"Hi {sender_name}, thanks for the note. We can move quickly on this and will send a concrete next step shortly."
    elif category == "inbound_lead":
        draft = f"Hi {sender_name}, thanks for reaching out. This looks aligned, and I'd love to keep momentum moving on your timeline."
    else:
        draft = f"Hi {sender_name}, thanks for reaching out. I reviewed this and will follow up with the right next step."

    raw = {
        "priority": priority,
        "category": category,
        "summary": summary,
        "cost_to_ignore": cost_to_ignore,
        "confidence": confidence,
        "suggested_action": suggested_action,
        "draft_opening": draft,
    }
    return normalize_classification(raw, email)


def classify_email(email: dict[str, Any]) -> dict[str, Any]:
    enriched_email = deepcopy(email)
    try:
        result = classify_with_baseten(enriched_email)
        if result is None:
            raise RuntimeError("Baseten API key missing")
    except Exception as exc:
        result = heuristic_classification(enriched_email)
        result["classification_mode"] = "heuristic"
        result["classification_error"] = str(exc)

    merged = deepcopy(enriched_email)
    merged.update(result)
    return merged


def sort_emails(emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        emails,
        key=lambda item: (
            PRIORITY_ORDER.get(item.get("priority", "P3"), 99),
            -int(item.get("cost_to_ignore", 0)),
            item.get("sender_name", "").lower(),
        ),
    )


def classify_all(emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with ThreadPoolExecutor(max_workers=10) as executor:
        classified = list(executor.map(classify_email, emails))
    return sort_emails(classified)
