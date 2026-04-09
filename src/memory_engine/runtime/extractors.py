from __future__ import annotations

import re
from typing import Any


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def address_parser(fields: dict[str, Any]) -> dict[str, Any] | None:
    address = fields.get("address")
    if not address:
        return None
    normalized = " ".join(str(address).split()).strip()
    return {
        "value": {"address": normalized, "summary": normalized.split(",")[0]},
        "canonical_key": normalize_key(normalized),
        "sensitivity": "S2_PERSONAL",
    }


def topic_extractor(fields: dict[str, Any]) -> dict[str, Any] | None:
    source = fields.get("topic") or fields.get("document_title") or fields.get("query")
    if not source:
        return None
    normalized = normalize_key(str(source))
    return {
        "value": {"topic": normalized, "raw": str(source)},
        "canonical_key": normalized,
        "sensitivity": "S1_INTERNAL",
    }


def customer_parser(fields: dict[str, Any]) -> dict[str, Any] | None:
    customer = fields.get("customer")
    domain = fields.get("domain")
    if not customer and not domain:
        return None
    canonical = normalize_key(str(domain or customer))
    return {
        "value": {"customer": customer, "domain": domain, "canonical_customer_id": canonical},
        "canonical_key": canonical,
        "sensitivity": "S2_PERSONAL",
    }


EXTRACTOR_REGISTRY = {
    "address_parser": address_parser,
    "topic_extractor": topic_extractor,
    "customer_parser": customer_parser,
}

