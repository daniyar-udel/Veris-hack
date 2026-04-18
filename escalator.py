from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

from agent import extract_sender_name

load_dotenv()


def demo_mode_enabled() -> bool:
    return os.getenv("DEMO_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}


def action_to_voice_phrase(action: str) -> str:
    phrases = {
        "respond_1h": "respond within 1 hour",
        "respond_24h": "respond within 24 hours",
        "respond_72h": "respond within 72 hours",
        "archive": "archive with no response",
    }
    return phrases.get(action, action.replace("_", " "))


def trim_sentence(text: str) -> str:
    return str(text or "").strip().rstrip(".!?")


def voicerun_config_status() -> dict[str, Any]:
    status = {
        "VOICERUN_API_KEY": bool(os.getenv("VOICERUN_API_KEY")),
        "VOICERUN_AGENT_ID": bool(os.getenv("VOICERUN_AGENT_ID")),
        "VOICERUN_ENVIRONMENT": bool(os.getenv("VOICERUN_ENVIRONMENT")),
        "PHONE_NUMBER": bool(os.getenv("PHONE_NUMBER")),
    }
    missing = [name for name, present in status.items() if not present and name != "VOICERUN_ENVIRONMENT"]
    return {
        "configured": not missing,
        "missing": missing,
        "status": status,
        "base_url": os.getenv("VOICERUN_BASE_URL", "https://api.primvoices.com/v1"),
        "environment": os.getenv("VOICERUN_ENVIRONMENT", "production"),
    }


def build_call_script(email: dict[str, Any]) -> str:
    sender_name = extract_sender_name(email.get("from", ""))
    subject = trim_sentence(email.get("subject", "No subject"))
    summary = trim_sentence(email.get("summary", "Important inbox alert"))
    cost = int(email.get("cost_to_ignore", 0))
    action = action_to_voice_phrase(str(email.get("suggested_action", "respond_1h")))

    return (
        f"Urgent Inbox ROI alert. {sender_name} sent a priority {email.get('priority', 'P0')} email. "
        f"Subject: {subject}. Summary: {summary}. Estimated cost to ignore: ${cost:,.0f}. "
        f"Recommended action: {action}. Open the app and respond now."
    )


def trigger_call(email: dict[str, Any]) -> dict[str, Any]:
    script = build_call_script(email)
    config = voicerun_config_status()
    api_key = os.getenv("VOICERUN_API_KEY")
    agent_id = os.getenv("VOICERUN_AGENT_ID")
    environment = config["environment"]
    phone_number = os.getenv("PHONE_NUMBER")
    base_url = str(config["base_url"]).rstrip("/")
    voice = os.getenv("VOICERUN_VOICE", "nova")

    missing = config["missing"]

    if missing:
        return {
            "success": demo_mode_enabled(),
            "simulated": True,
            "message": f"VoiceRun not fully configured. Missing: {', '.join(missing)}.",
            "script": script,
            "config_status": config,
        }

    payload = {
        "inputType": "phone",
        "inputParameters": {"phoneNumber": phone_number},
        "environment": environment,
        "parameters": {
            "script": script,
            "sender_name": extract_sender_name(email.get("from", "")),
            "voice": voice,
            "priority": email.get("priority", "P0"),
            "subject": email.get("subject", ""),
            "summary": email.get("summary", ""),
            "cost_to_ignore": int(email.get("cost_to_ignore", 0)),
            "suggested_action": email.get("suggested_action", "respond_1h"),
        },
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            f"{base_url}/agents/{agent_id}/sessions/start",
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
            "config_status": config,
        }
    except requests.HTTPError as exc:
        response = exc.response
        body = ""
        if response is not None:
            try:
                body = response.text[:1000]
            except Exception:
                body = "<unable to read response body>"
        return {
            "success": demo_mode_enabled(),
            "simulated": demo_mode_enabled(),
            "message": f"VoiceRun call failed: {exc}",
            "script": script,
            "config_status": config,
            "http_status": response.status_code if response is not None else None,
            "response_body": body,
        }
    except Exception as exc:
        return {
            "success": demo_mode_enabled(),
            "simulated": demo_mode_enabled(),
            "message": f"VoiceRun call failed: {exc}",
            "script": script,
            "config_status": config,
        }
