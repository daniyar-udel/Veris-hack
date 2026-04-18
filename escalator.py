from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

from agent import extract_sender_name

load_dotenv()


def demo_mode_enabled() -> bool:
    return os.getenv("DEMO_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}


def build_call_script(email: dict[str, Any]) -> str:
    sender_name = extract_sender_name(email.get("from", ""))
    subject = email.get("subject", "No subject")
    summary = email.get("summary", "Important inbox alert")
    cost = int(email.get("cost_to_ignore", 0))
    action = str(email.get("suggested_action", "respond_1h")).replace("_", " ")

    return (
        f"Urgent Inbox ROI alert. {sender_name} sent a priority {email.get('priority', 'P0')} email. "
        f"Subject: {subject}. Summary: {summary}. Estimated cost to ignore: ${cost:,.0f}. "
        f"Recommended action: {action}. Open the app and respond now."
    )


def trigger_call(email: dict[str, Any]) -> dict[str, Any]:
    script = build_call_script(email)
    api_key = os.getenv("VOICERUN_API_KEY")
    agent_id = os.getenv("VOICERUN_AGENT_ID")
    environment = os.getenv("VOICERUN_ENVIRONMENT", "production")
    phone_number = os.getenv("PHONE_NUMBER")

    missing = [
        name
        for name, value in {
            "VOICERUN_API_KEY": api_key,
            "VOICERUN_AGENT_ID": agent_id,
            "PHONE_NUMBER": phone_number,
        }.items()
        if not value
    ]

    if missing:
        return {
            "success": demo_mode_enabled(),
            "simulated": True,
            "message": f"VoiceRun not fully configured. Missing: {', '.join(missing)}.",
            "script": script,
        }

    payload = {
        "inputType": "phone",
        "inputParameters": {"phoneNumber": phone_number},
        "environment": environment,
        "parameters": {
            "script": script,
            "sender_name": extract_sender_name(email.get("from", "")),
            "voice": "nova",
            "priority": email.get("priority", "P0"),
            "subject": email.get("subject", ""),
        },
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            f"https://api.primvoices.com/v1/agents/{agent_id}/sessions/start",
            headers=headers,
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        data = response.json() if response.content else {}
        return {
            "success": True,
            "simulated": False,
            "message": "VoiceRun outbound call started successfully.",
            "script": script,
            "session_id": data.get("sessionId") or data.get("id"),
        }
    except Exception as exc:
        return {
            "success": demo_mode_enabled(),
            "simulated": demo_mode_enabled(),
            "message": f"VoiceRun call failed: {exc}",
            "script": script,
        }
