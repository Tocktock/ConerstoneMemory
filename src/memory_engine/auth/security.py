from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from memory_engine.config.settings import get_settings
from memory_engine.id_utils import utcnow


security_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    email: str
    display_name: str
    role: str


def _pbkdf2(secret: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt.encode("utf-8"), 600_000)
    return base64.urlsafe_b64encode(digest).decode("utf-8")


def _get_seed_users() -> dict[str, tuple[str, AuthUser]]:
    settings = get_settings()
    users: dict[str, tuple[str, AuthUser]] = {}
    for item in settings.auth_seed_users.split(";"):
        if not item.strip():
            continue
        email, password, role = item.split(":")
        salt = email
        users[email] = (
            _pbkdf2(password, salt),
            AuthUser(email=email, display_name=email.split("@")[0].title(), role=role),
        )
    return users


def authenticate(email: str, password: str) -> AuthUser:
    users = _get_seed_users()
    record = users.get(email)
    if record is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    stored_hash, user = record
    if not hmac.compare_digest(stored_hash, _pbkdf2(password, email)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user


def issue_token(user: AuthUser) -> str:
    settings = get_settings()
    payload = {
        "sub": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "exp": int((utcnow() + timedelta(minutes=settings.auth_token_ttl_minutes)).timestamp()),
    }
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded = base64.urlsafe_b64encode(serialized).decode("utf-8")
    signature = hmac.new(settings.auth_secret.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def decode_token(token: str) -> AuthUser:
    settings = get_settings()
    try:
        encoded, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    expected = hmac.new(settings.auth_secret.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    payload = json.loads(base64.urlsafe_b64decode(encoded.encode("utf-8") + b"==="))
    if int(payload["exp"]) < int(utcnow().timestamp()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    return AuthUser(
        email=payload["sub"],
        display_name=payload["display_name"],
        role=payload["role"],
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> AuthUser:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return decode_token(credentials.credentials)


def require_roles(*roles: str):
    def _dependency(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return _dependency
