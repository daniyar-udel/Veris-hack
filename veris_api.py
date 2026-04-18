from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI

from agent import classify_email

app = FastAPI(title="InboxROI Veris Adapter")


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/classify")
def classify(payload: dict[str, Any]) -> dict[str, Any]:
    if "message" in payload and isinstance(payload["message"], str):
        email = {
            "id": "veris-message",
            "from": "veris-scenario@example.com",
            "subject": payload["message"][:120],
            "body": payload["message"],
        }
    else:
        email = {
            "id": payload.get("id", "veris-email"),
            "from": payload.get("from", "veris-scenario@example.com"),
            "subject": payload.get("subject", "(no subject)"),
            "body": payload.get("body", payload.get("message", "")),
            "hint": payload.get("hint", ""),
        }

    result = classify_email(email)
    return {"response": json.dumps(result), "classification": result}
