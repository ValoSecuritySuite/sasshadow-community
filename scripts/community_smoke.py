#!/usr/bin/env python3
"""Smoke test for SaaSShadow Community Edition.

Runs a handful of end-to-end checks that the community surface works and
that extended commercial routes are not exposed.

By default it exercises the app in-process via FastAPI's TestClient (no
server needed), which is what CI uses:

    python scripts/community_smoke.py

To run against a live server instead:

    uvicorn app.main:app --port 8000 &
    python scripts/community_smoke.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

# Allow running as `python scripts/community_smoke.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class _Client:
    """Minimal GET/POST client over a live base URL."""

    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    def get(self, path: str):
        req = urllib.request.Request(self._base + path, method="GET")
        return self._send(req)

    def post(self, path: str, body: dict):
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            self._base + path,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        return self._send(req)

    @staticmethod
    def _send(req):
        import urllib.error

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()


class _Response:
    def __init__(self, status: int, raw: bytes) -> None:
        self.status_code = status
        self._raw = raw

    def json(self):
        return json.loads(self._raw.decode())


class _LiveAdapter:
    def __init__(self, base_url: str) -> None:
        self._c = _Client(base_url)

    def get(self, path: str):
        status, raw = self._c.get(path)
        return _Response(status, raw)

    def post(self, path: str, json: dict | None = None):
        status, raw = self._c.post(path, json or {})
        return _Response(status, raw)


def _build_client(base_url: str | None):
    if base_url:
        return _LiveAdapter(base_url)
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default=None,
        help="Live server URL. Omit to run in-process via TestClient.",
    )
    args = parser.parse_args()
    client = _build_client(args.base_url)

    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        if ok:
            print(f"OK   {name}")
        else:
            print(f"FAIL {name} {detail}")
            failures.append(name)

    resp = client.get("/health")
    check("health", resp.status_code == 200 and resp.json().get("status") == "ok")

    resp = client.get("/meta/edition")
    body = resp.json() if resp.status_code == 200 else {}
    check(
        "meta/edition",
        resp.status_code == 200
        and body.get("edition") == "community"
        and "features" not in body,
        str(body)[:200],
    )

    resp = client.post(
        "/scan/analyze",
        json={
            "target": "smoke-test",
            "json_data": {
                "source_app": "salesforce",
                "destination_app": "slack",
                "oauth": {"scopes": ["files.readwrite.all", "admin"]},
                "data_types": ["pii"],
            },
        },
    )
    body = resp.json() if resp.status_code == 200 else {}
    check(
        "scan/analyze",
        resp.status_code == 200 and "combined_score" in body,
        str(body)[:200],
    )

    resp = client.get("/scans")
    check("scans history", resp.status_code == 200 and "scans" in resp.json())

    resp = client.get("/connectors")
    ids = {c["id"] for c in resp.json().get("connectors", [])} if resp.status_code == 200 else set()
    check("connectors limited to entra+slack", ids == {"entra", "slack"}, str(ids))

    resp = client.get("/dashboard/overview")
    check("dashboard overview", resp.status_code == 200 and "scans_total" in resp.json())

    resp = client.get("/playbooks")
    check("no extended playbook API", resp.status_code == 404, f"status={resp.status_code}")

    if failures:
        print(f"\n{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("\nAll community smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
