from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet

from memory_engine.config.settings import get_settings


SUMMARY_KEYS = {"summary", "topic", "canonical_customer_id", "domain", "city", "country"}


def _derived_dev_key(secret: str) -> str:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8")


def get_fernet() -> Fernet:
    settings = get_settings()
    key = settings.sensitive_encryption_key
    if not key:
        if settings.environment != "dev":
            raise RuntimeError("MEMORYENGINE_SENSITIVE_ENCRYPTION_KEY is required outside dev")
        key = _derived_dev_key(settings.auth_secret)
    return Fernet(key.encode("utf-8"))


def _coarse_payload(payload: dict[str, Any]) -> dict[str, Any]:
    coarse = {key: value for key, value in payload.items() if key in SUMMARY_KEYS and value is not None}
    if "summary" not in coarse:
        if "address" in payload and payload.get("address"):
            coarse["summary"] = str(payload["address"]).split(",")[0].strip()
        elif "customer" in payload and payload.get("customer"):
            coarse["summary"] = str(payload["customer"])
    return coarse


def protect_payload(payload: dict[str, Any], sensitivity: str) -> tuple[dict[str, Any], str | None]:
    if sensitivity in {"S0_PUBLIC", "S1_INTERNAL"}:
        return payload, None
    token = get_fernet().encrypt(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return _coarse_payload(payload), token.decode("utf-8")


def restore_payload(clear_payload: dict[str, Any], encrypted_payload: str | None) -> dict[str, Any]:
    if not encrypted_payload:
        return clear_payload
    decrypted = get_fernet().decrypt(encrypted_payload.encode("utf-8"))
    protected = json.loads(decrypted.decode("utf-8"))
    return {**clear_payload, **protected}
