from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_DATA_PATH = Path(__file__).resolve().parent / "data" / "emails.json"


def load_emails(path: str | Path = DEFAULT_DATA_PATH) -> list[dict[str, Any]]:
    data_path = Path(path)
    with data_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_emails(emails: list[dict[str, Any]], path: str | Path = DEFAULT_DATA_PATH) -> Path:
    data_path = Path(path)
    data_path.parent.mkdir(parents=True, exist_ok=True)
    with data_path.open("w", encoding="utf-8") as handle:
        json.dump(emails, handle, indent=2)
    return data_path


def build_email_record(raw: dict[str, Any], index: int) -> dict[str, Any]:
    body = str(raw.get("body") or raw.get("message") or raw.get("text") or "").strip()
    subject = str(raw.get("subject") or "(no subject)").strip()
    sender = str(raw.get("from") or raw.get("sender") or "unknown@example.com").strip()
    return {
        "id": str(raw.get("id") or f"email-{index + 1:02d}"),
        "from": sender,
        "subject": subject,
        "body": body[:500],
        "hint": raw.get("hint", ""),
    }


def generate_from_huggingface(
    dataset_name: str = "corbt/enron-emails",
    split: str = "train",
    limit: int = 20,
    output_path: str | Path = DEFAULT_DATA_PATH,
) -> Path:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError("Install the 'datasets' package to regenerate emails.json") from exc

    dataset = load_dataset(dataset_name, split=split)
    emails: list[dict[str, Any]] = []

    for index, raw in enumerate(dataset):
        email = build_email_record(raw, index)
        if email["body"]:
            emails.append(email)
        if len(emails) == limit:
            break

    for vip_index in (0, 1, 3):
        if vip_index < len(emails):
            emails[vip_index]["hint"] = "VIP"

    return save_emails(emails, output_path)


if __name__ == "__main__":
    path = generate_from_huggingface()
    print(f"Saved demo dataset to {path}")
