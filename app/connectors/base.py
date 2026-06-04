"""Shared HTTP and sync helpers for connectors."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_TIMEOUT = 30


def http_get(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    """GET URL and return JSON. Raises on non-2xx or parse error."""
    req = urllib.request.Request(url, method="GET")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"HTTP {resp.status} from {url}")
        return json.loads(resp.read().decode("utf-8"))


def http_post(
    url: str,
    data: dict[str, Any] | list[Any] | None = None,
    body_bytes: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """POST URL with JSON or raw body. Returns JSON."""
    if body_bytes is None:
        body_bytes = json.dumps(data or {}).encode("utf-8") if data is not None else b"{}"
    req = urllib.request.Request(url, data=body_bytes, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"HTTP {resp.status} from {url}")
        return json.loads(resp.read().decode("utf-8"))
