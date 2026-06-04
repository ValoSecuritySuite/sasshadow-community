"""API token entropy and exposure analyzer.

Detects token misuse patterns in SaaS integration configurations:
- Tokens without expiry
- Long-lived tokens (>= 90 days)
- Weak/short tokens
- Tokens embedded in URL query strings
- Disabled token rotation
- Token reuse across integrations
- High-entropy string detection via Shannon entropy
"""

from __future__ import annotations

import math
import re
from typing import Any

from app.core.logging import get_logger
from app.models.scan_models import TokenAnalysis

logger = get_logger(__name__)

_TOKEN_KEYS = {
    "token", "access_token", "refresh_token",
    "api_key", "apikey", "client_secret", "secret",
}
_EXPIRY_KEYS = {
    "expires_in", "expires_in_days", "token_ttl_days",
    "token_ttl", "ttl_days",
}

_MIN_TOKEN_LENGTH = 20
_ENTROPY_THRESHOLD = 4.3
_LONG_LIVED_DAYS = 90


def _iter_nodes(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _iter_nodes(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_nodes(item)


def _extract_token_values(payload: Any) -> list[str]:
    token_values: list[str] = []
    for node in _iter_nodes(payload):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            normalized_key = key.lower()
            if normalized_key not in _TOKEN_KEYS and "token" not in normalized_key and "secret" not in normalized_key:
                continue
            if isinstance(value, str) and value.strip():
                token_values.append(value.strip())
    return token_values


def _extract_expiry_days(payload: Any) -> float | None:
    for node in _iter_nodes(payload):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            if key.lower() not in _EXPIRY_KEYS:
                continue
            try:
                raw = float(value)
            except (TypeError, ValueError):
                continue
            if raw > 3650:
                return raw / 86400.0
            return raw
    return None


def shannon_entropy(data: str) -> float:
    """Calculate Shannon entropy of a string (bits per character)."""
    if not data:
        return 0.0
    freq: dict[str, int] = {}
    for ch in data:
        freq[ch] = freq.get(ch, 0) + 1
    length = len(data)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def analyze_tokens(
    content: str,
    payload: Any,
    metadata: dict[str, Any],
) -> TokenAnalysis:
    """Analyze API tokens in a SaaS integration payload for misuse patterns."""
    token_values = _extract_token_values(payload)
    expiry_days = _extract_expiry_days(payload)

    misuse_patterns: list[str] = []
    high_entropy_count = 0
    weak_count = 0
    tokens_in_urls = 0
    long_lived_count = 0

    if token_values and expiry_days is None:
        misuse_patterns.append("token_without_expiry")

    if expiry_days is not None and expiry_days >= _LONG_LIVED_DAYS:
        misuse_patterns.append("long_lived_token")
        long_lived_count = 1

    for token in token_values:
        if len(token) < _MIN_TOKEN_LENGTH:
            weak_count += 1
        if shannon_entropy(token) >= _ENTROPY_THRESHOLD:
            high_entropy_count += 1

    if weak_count > 0:
        misuse_patterns.append("weak_token_format")

    url_matches = re.findall(
        r"(?:access_token|token|api_key)=[^\s&]+", content, re.IGNORECASE
    )
    tokens_in_urls = len(url_matches)
    if tokens_in_urls > 0:
        misuse_patterns.append("token_in_url_query")

    rotation_disabled = metadata.get("token_rotation_enabled") is False
    if rotation_disabled:
        misuse_patterns.append("rotation_disabled")

    shared = metadata.get("token_shared_across_integrations") is True
    if shared:
        misuse_patterns.append("token_reuse_across_integrations")

    # De-duplicate while preserving order
    seen: set[str] = set()
    stable_misuse: list[str] = []
    for p in misuse_patterns:
        if p not in seen:
            seen.add(p)
            stable_misuse.append(p)

    # Risk score
    base = 0.0
    if stable_misuse:
        base = 30.0
        base += min(len(stable_misuse) * 10.0, 40.0)
        if rotation_disabled:
            base += 10.0
        if shared:
            base += 10.0
        if tokens_in_urls > 0:
            base += 10.0
    token_risk_score = round(min(100.0, base), 2)

    return TokenAnalysis(
        tokens_found=len(token_values),
        misuse_patterns=stable_misuse,
        high_entropy_tokens=high_entropy_count,
        weak_tokens=weak_count,
        tokens_in_urls=tokens_in_urls,
        long_lived_tokens=long_lived_count,
        rotation_disabled=rotation_disabled,
        shared_across_integrations=shared,
        token_risk_score=token_risk_score,
    )
