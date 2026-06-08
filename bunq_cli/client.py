"""Thin HTTP client for the bunq REST API.

All requests that carry a private key are signed per the bunq signing spec:
  {METHOD} {path+query}\\n
  {Header}: {value}\\n  (Cache-Control, User-Agent, X-Bunq-* sorted A-Z)
  \\n
  {body}
"""

import json
import uuid

import httpx

from .config import get_base_url
from .crypto import sign

_USER_AGENT = "bunq-cli/0.1.0"
_SIGN_HEADERS = frozenset({"Cache-Control", "User-Agent"})


class BunqAPIError(Exception):
    def __init__(self, descriptions: list[str], status_code: int) -> None:
        super().__init__(" | ".join(descriptions))
        self.status_code = status_code


def _build_headers(token: str | None) -> dict[str, str]:
    headers = {
        "Cache-Control": "no-cache",
        "User-Agent": _USER_AGENT,
        "X-Bunq-Client-Request-Id": str(uuid.uuid4()),
        "X-Bunq-Geolocation": "0 0 0 0 000",
        "X-Bunq-Language": "en_US",
        "X-Bunq-Region": "en_US",
        "Content-Type": "application/json",
    }
    if token:
        headers["X-Bunq-Client-Authentication"] = token
    return headers


_SIGN_EXCLUDE = frozenset({"X-Bunq-Client-Signature"})


def _signing_string(method: str, path: str, headers: dict[str, str], body: str) -> bytes:
    relevant = {
        k: v
        for k, v in headers.items()
        if k in _SIGN_HEADERS or k.startswith("X-Bunq-")
        if k not in _SIGN_EXCLUDE
    }
    header_block = "\n".join(f"{k}: {v}" for k, v in sorted(relevant.items()))
    return f"{method.upper()} /v1{path}\n{header_block}\n\n{body}".encode()


def _raise_for_error(response: httpx.Response) -> None:
    if response.is_success:
        return
    try:
        errors = [e["error_description"] for e in response.json().get("Error", [])]
    except Exception:
        errors = [response.text]
    raise BunqAPIError(errors or [f"HTTP {response.status_code}"], response.status_code)


def request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    token: str | None = None,
    private_pem: str | None = None,
) -> dict:
    """Make a signed (or unsigned) call to the bunq API and return the parsed JSON."""
    url = f"{get_base_url()}/v1{path}"
    headers = _build_headers(token)
    body_str = json.dumps(body) if body is not None else ""

    if private_pem:
        sig = sign(private_pem, _signing_string(method, path, headers, body_str))
        headers["X-Bunq-Client-Signature"] = sig

    response = httpx.request(method, url, content=body_str, headers=headers)
    _raise_for_error(response)
    return response.json()


def extract(response: dict, key: str) -> dict | None:
    """Pull the first matching object out of a bunq Response array."""
    for item in response.get("Response", []):
        if key in item:
            return item[key]
    return None
