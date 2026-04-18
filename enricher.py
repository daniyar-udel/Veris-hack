from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

from agent import extract_email_address

load_dotenv()

PERSONAL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
}

DEMO_INTEL: dict[str, dict[str, str]] = {
    "acmecorp.com": {
        "company": "Acme Corp",
        "snippet": "Workflow automation company, Series B, roughly 420 employees, actively expanding enterprise operations.",
        "source_url": "https://acmecorp.com",
    },
    "globex.com": {
        "company": "Globex",
        "snippet": "Global operating company with IPO-stage momentum and large procurement processes across multiple business units.",
        "source_url": "https://globex.com",
    },
    "initech.io": {
        "company": "Initech",
        "snippet": "Seed-stage infrastructure software startup with a lean team and fast buying cycles.",
        "source_url": "https://initech.io",
    },
    "umbrellainc.com": {
        "company": "Umbrella Inc",
        "snippet": "PE-backed operator with a sizable installed base and recurring contract footprint.",
        "source_url": "https://umbrellainc.com",
    },
    "northstarretail.com": {
        "company": "Northstar Retail",
        "snippet": "Multi-region retail operator modernizing store operations and analytics systems.",
        "source_url": "https://northstarretail.com",
    },
    "redwoodhealth.org": {
        "company": "Redwood Health",
        "snippet": "Regional healthcare network with compliance-heavy workflows and long procurement cycles.",
        "source_url": "https://redwoodhealth.org",
    },
}


def extract_domain(from_value: str) -> str:
    email_address = extract_email_address(from_value)
    if "@" not in email_address:
        return ""
    return email_address.split("@", 1)[1].lower()


def fetch_company_intel(domain: str) -> dict[str, str] | None:
    if not domain or domain in PERSONAL_DOMAINS:
        return None

    api_key = os.getenv("YOUCOM_API_KEY")
    if not api_key:
        return DEMO_INTEL.get(domain)

    base_url = os.getenv("YOUCOM_BASE_URL", "https://api.ydc-index.io").rstrip("/")
    headers = {"X-API-Key": api_key}
    params = {"query": f"{domain} company funding employees size", "count": 5}

    try:
        response = requests.get(f"{base_url}/v1/search", headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        web_results = (data.get("results") or {}).get("web") or []
        if not web_results:
            return DEMO_INTEL.get(domain)

        top = web_results[0]
        snippets = top.get("snippets") or []
        snippet = snippets[0] if snippets else top.get("description") or "Company intel unavailable."
        return {
            "company": top.get("title") or domain,
            "snippet": snippet,
            "source_url": top.get("url") or "",
        }
    except Exception:
        return DEMO_INTEL.get(domain)


def enrich_email(email: dict[str, Any]) -> dict[str, Any]:
    if email.get("priority") not in {"P0", "P1"}:
        return email

    domain = extract_domain(email.get("from", ""))
    intel = fetch_company_intel(domain)
    enriched = dict(email)
    enriched["company_intel"] = intel
    enriched["company_domain"] = domain
    return enriched


def enrich_classified_emails(emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_email(email) for email in emails]
