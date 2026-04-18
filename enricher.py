from __future__ import annotations

from functools import lru_cache
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


def normalize_youcom_base_url(raw_url: str | None = None) -> str:
    base_url = (raw_url or os.getenv("YOUCOM_BASE_URL") or "https://ydc-index.io").strip().rstrip("/")
    if base_url == "https://api.ydc-index.io":
        return "https://ydc-index.io"
    return base_url


def youcom_config_status() -> dict[str, Any]:
    api_key = os.getenv("YOUCOM_API_KEY")
    return {
        "configured": bool(api_key),
        "status": {
            "YOUCOM_API_KEY": bool(api_key),
            "YOUCOM_BASE_URL": bool(os.getenv("YOUCOM_BASE_URL")),
        },
        "base_url": normalize_youcom_base_url(),
    }


def extract_domain(from_value: str) -> str:
    email_address = extract_email_address(from_value)
    if "@" not in email_address:
        return ""
    return email_address.split("@", 1)[1].lower()


def fallback_company_name(domain: str) -> str:
    root = domain.split(".", 1)[0].replace("-", " ").replace("_", " ").strip()
    return root.title() if root else domain


def clean_text(text: str, max_length: int = 220) -> str:
    compact = " ".join(str(text or "").split()).strip()
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 3].rstrip() + "..."


def pick_best_web_result(web_results: list[dict[str, Any]], domain: str) -> dict[str, Any] | None:
    if not web_results:
        return None

    domain_matches = []
    for result in web_results:
        url = str(result.get("url") or "").lower()
        title = str(result.get("title") or "").lower()
        if domain in url or domain in title:
            domain_matches.append(result)

    if domain_matches:
        return domain_matches[0]
    return web_results[0]


@lru_cache(maxsize=128)
def fetch_company_intel(domain: str) -> dict[str, str] | None:
    if not domain or domain in PERSONAL_DOMAINS:
        return None

    api_key = os.getenv("YOUCOM_API_KEY")
    if not api_key:
        intel = DEMO_INTEL.get(domain)
        if intel:
            return {**intel, "source": "demo", "query": ""}
        return None

    base_url = normalize_youcom_base_url()
    headers = {"X-API-Key": api_key}
    query = f"{domain} company funding employees size"
    params = {"query": query, "count": 5}

    try:
        response = requests.get(f"{base_url}/v1/search", headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        web_results = (data.get("results") or {}).get("web") or []
        if not web_results:
            intel = DEMO_INTEL.get(domain)
            if intel:
                return {**intel, "source": "demo", "query": query}
            return None

        top = pick_best_web_result(web_results, domain)
        if not top:
            return None

        snippets = top.get("snippets") or []
        snippet = snippets[0] if snippets else top.get("description") or "Company intel unavailable."
        return {
            "company": clean_text(top.get("title") or fallback_company_name(domain), max_length=80),
            "snippet": clean_text(snippet, max_length=240),
            "source_url": top.get("url") or "",
            "source": "youcom",
            "query": query,
        }
    except Exception:
        intel = DEMO_INTEL.get(domain)
        if intel:
            return {**intel, "source": "demo", "query": query}
        return None


def enrich_email(email: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(email)
    if email.get("priority") not in {"P0", "P1"}:
        enriched["company_intel_status"] = "skipped_low_priority"
        return enriched

    domain = extract_domain(email.get("from", ""))
    enriched["company_domain"] = domain
    if not domain:
        enriched["company_intel"] = None
        enriched["company_intel_status"] = "missing_domain"
        return enriched

    if domain in PERSONAL_DOMAINS:
        enriched["company_intel"] = None
        enriched["company_intel_status"] = "skipped_personal_domain"
        return enriched

    intel = fetch_company_intel(domain)
    enriched["company_intel"] = intel
    if intel:
        enriched["company_intel_status"] = intel.get("source", "available")
    else:
        enriched["company_intel_status"] = "unavailable"
    return enriched


def enrich_classified_emails(emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_email(email) for email in emails]
