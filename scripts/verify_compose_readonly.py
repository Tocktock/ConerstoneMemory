from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


@dataclass(frozen=True)
class VerificationSettings:
    web_base: str
    api_base: str
    email: str
    password: str


def _normalize_base(url: str) -> str:
    return url.rstrip("/")


def _request(
    method: str,
    url: str,
    *,
    data: dict | None = None,
    headers: dict[str, str] | None = None,
    allow_redirects: bool = True,
) -> tuple[int, dict[str, str], bytes]:
    payload = json.dumps(data).encode("utf-8") if data is not None else None
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
    opener = urllib.request.build_opener() if allow_redirects else urllib.request.build_opener(NoRedirectHandler)
    try:
        with opener.open(request) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _decode_json(payload: bytes) -> object:
    return json.loads(payload.decode("utf-8"))


def _assert_no_schema_errors(payload: bytes) -> None:
    text = payload.decode("utf-8", errors="ignore").lower()
    disallowed = (
        "undefinedtable",
        "does not exist",
        "internal server error",
        "traceback",
    )
    _expect(not any(token in text for token in disallowed), f"unexpected backend error payload: {text[:400]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only verification for the local Docker Compose stack.")
    parser.add_argument("--web-base", default="http://localhost:3000")
    parser.add_argument("--api-base", default="http://localhost:8001")
    parser.add_argument("--email", default="operator@memoryengine.local")
    parser.add_argument("--password", default="operator")
    args = parser.parse_args()

    settings = VerificationSettings(
        web_base=_normalize_base(args.web_base),
        api_base=_normalize_base(args.api_base),
        email=args.email,
        password=args.password,
    )

    status, headers, _ = _request("GET", f"{settings.web_base}/", allow_redirects=False)
    header_map = {key.lower(): value for key, value in headers.items()}
    _expect(status in {302, 307, 308}, f"expected redirect from /, got {status}")
    _expect(
        header_map.get("location") == "/config/api-ontology",
        f"unexpected redirect target: {header_map.get('location')}",
    )
    print("PASS web / redirect")

    status, _, body = _request("GET", f"{settings.web_base}/login")
    _expect(status == 200, f"expected 200 from /login, got {status}")
    _expect("Operator login" in body.decode("utf-8", errors="ignore"), "login page is missing expected content")
    print("PASS web /login")

    status, _, body = _request("GET", f"{settings.api_base}/health")
    _expect(status == 200, f"expected 200 from /health, got {status}")
    _expect(_decode_json(body) == {"status": "ok"}, "unexpected /health payload")
    print("PASS api /health")

    status, _, body = _request(
        "POST",
        f"{settings.api_base}/v1/auth/login",
        data={"email": settings.email, "password": settings.password},
    )
    _expect(status == 200, f"expected 200 from /v1/auth/login, got {status}")
    login = _decode_json(body)
    _expect(isinstance(login, dict) and bool(login.get("token")), "login did not return a token")
    token = login["token"]
    print("PASS api /v1/auth/login")

    auth_headers = {"Authorization": f"Bearer {token}"}

    status, _, body = _request("GET", f"{settings.api_base}/v1/auth/me", headers=auth_headers)
    _expect(status == 200, f"expected 200 from /v1/auth/me, got {status}")
    me = _decode_json(body)
    _expect(isinstance(me, dict) and me.get("user", {}).get("email") == settings.email, "unexpected /v1/auth/me payload")
    print("PASS api /v1/auth/me")

    readonly_paths = [
        "/v1/control/configs",
        "/v1/control/validation",
        "/v1/control/simulation",
        "/v1/control/publications",
        "/v1/memory/decisions",
        "/v1/control/audit-log",
    ]
    for path in readonly_paths:
        status, _, body = _request("GET", f"{settings.api_base}{path}", headers=auth_headers)
        _expect(status == 200, f"expected 200 from {path}, got {status}")
        _assert_no_schema_errors(body)
        payload = _decode_json(body)
        _expect(isinstance(payload, list), f"expected list payload from {path}, got {type(payload).__name__}")
        print(f"PASS api {path} ({len(payload)} rows)")

    print("PASS compose read-only verification")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - defensive CLI handling
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
