"""Slack connector.

Uses a bot or user token to call auth.test (and reads x-oauth-scopes from the
response header). Builds one integration record for the app represented by the token,
then runs the pipeline and stores the result.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_SLACK_AUTH_TEST = "https://slack.com/api/auth.test"
_TIMEOUT = 30


def _slack_post(token: str, url: str = _SLACK_AUTH_TEST) -> tuple[dict[str, Any], dict[str, str]]:
    """POST to Slack API with Bearer token. Returns (json_body, response_headers)."""
    req = urllib.request.Request(url, data=b"", method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        headers = {k.lower(): v for k, v in resp.headers.items()}
    return body, headers


def fetch_slack_integration(token: str) -> tuple[str, dict[str, Any]]:
    """Call auth.test; build (target, json_data) from response and x-oauth-scopes header.

    Raises on invalid token or non-ok response.
    """
    body, headers = _slack_post(token)
    if not body.get("ok"):
        raise RuntimeError(body.get("error", "invalid_auth"))
    # Scopes are in response header (apps.permissions.info is deprecated)
    scopes_header = headers.get("x-oauth-scopes", "") or ""
    scopes = [s.strip() for s in scopes_header.split(",") if s.strip()]
    team_id = body.get("team_id") or ""
    team_name = (body.get("team") or "").replace(" ", "_")[:32]
    bot_id = body.get("bot_id") or ""
    user_id = body.get("user_id") or ""
    target = f"slack_{team_id}_{bot_id or user_id}"[:80]
    if not target.strip("_"):
        target = "slack_unknown"
    json_data: dict[str, Any] = {
        "source_app": "slack",
        "destination_app": "",
        "oauth": {"scopes": scopes},
        "credentials": {"has_bot_token": bool(bot_id)},
        "metadata": {"team": body.get("team"), "team_id": team_id, "url": body.get("url")},
    }
    if body.get("user_count") is not None:
        json_data["user_count"] = body["user_count"]
    if body.get("last_used") is not None:
        json_data["last_used"] = body["last_used"]
    return target, json_data


def sync_slack(
    token: str,
    *,
    customer_id: str | None = None,
    run_pipeline_and_store: Any = None,
) -> tuple[int, list[dict[str, Any]], list[str]]:
    """Fetch Slack app for token, run pipeline, and store result.

    run_pipeline_and_store(target, json_data, customer_id) must be provided by the API layer.
    Returns (synced_count, scans, errors). Count is 0 or 1.
    """
    if run_pipeline_and_store is None:
        raise ValueError("run_pipeline_and_store is required")
    try:
        target, json_data = fetch_slack_integration(token)
    except Exception as e:
        logger.warning("Slack fetch failed: %s", e)
        return 0, [], [str(e)]
    scans: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        scan_info = run_pipeline_and_store(target=target, json_data=json_data, customer_id=customer_id)
        if scan_info:
            scans.append(scan_info)
    except Exception as e:
        errors.append(f"{target}: {e}")
        logger.debug("Slack scan failed for %s: %s", target, e)
    return len(scans), scans, errors
