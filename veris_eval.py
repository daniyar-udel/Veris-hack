from __future__ import annotations

import json
from statistics import mean
from typing import Any

from agent import classify_email

SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "true_p0_enterprise_ceo",
        "email": {
            "id": "veris-p0",
            "from": "Maya Reynolds <maya@fortuna500.com>",
            "subject": "CEO intro: $500K budget approved, decision in 48 hours",
            "body": (
                "We're finalizing our shortlist now. I have a $500K budget signed off, "
                "need a recommendation by Friday, and want to speak today if possible."
            ),
            "hint": "VIP",
        },
    },
    {
        "name": "spam_invoice",
        "email": {
            "id": "veris-spam",
            "from": "billing@random-payments.co",
            "subject": "Final notice: invoice overdue, pay now",
            "body": (
                "Your account has been suspended. Click here and wire payment immediately "
                "to avoid penalties."
            ),
        },
    },
    {
        "name": "vip_renewal",
        "email": {
            "id": "veris-renewal",
            "from": "Lisa Park <lisa@umbrellainc.com>",
            "subject": "Renewal decision next week for $30K annual contract",
            "body": (
                "We're deciding whether to renew and potentially expand seats. "
                "Please send timing and pricing updates before Tuesday."
            ),
            "hint": "VIP",
        },
    },
]


def scenario_passed(name: str, result: dict[str, Any]) -> bool:
    if name == "true_p0_enterprise_ceo":
        return result["priority"] == "P0" and int(result["cost_to_ignore"]) > 50_000
    if name == "spam_invoice":
        return (
            result["priority"] == "P3"
            and int(result["cost_to_ignore"]) == 0
            and result["category"] == "spam"
        )
    if name == "vip_renewal":
        return result["priority"] in {"P0", "P1"} and result["category"] == "customer"
    return False


def run_local_eval() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        prediction = classify_email(scenario["email"])
        results.append(
            {
                "scenario": scenario["name"],
                "passed": scenario_passed(scenario["name"], prediction),
                "prediction": prediction,
            }
        )

    allowed_p0_scenarios = {"true_p0_enterprise_ceo", "vip_renewal"}
    p0_predictions = [item for item in results if item["prediction"]["priority"] == "P0"]
    true_positive_p0 = [
        item
        for item in results
        if item["scenario"] in allowed_p0_scenarios and item["prediction"]["priority"] == "P0"
    ]
    spam_false_p0 = [
        item for item in results if item["scenario"] == "spam_invoice" and item["prediction"]["priority"] == "P0"
    ]

    return {
        "total_scenarios": len(results),
        "pass_rate": round(mean(1 if item["passed"] else 0 for item in results), 2),
        "p0_precision": round(len(true_positive_p0) / len(p0_predictions), 2) if p0_predictions else 0.0,
        "no_false_p0_on_spam": len(spam_false_p0) == 0,
        "results": results,
    }


if __name__ == "__main__":
    print(json.dumps(run_local_eval(), indent=2))
