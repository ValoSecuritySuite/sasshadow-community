"""API + webhook detection for SaaS integration artifacts.

Goes beyond keyword-based ``_infer_link_type`` in
:mod:`app.analysis.integration_mapper` by inspecting the full payload tree
and raw text for:

- REST endpoints (URL pattern with TLD + path)
- GraphQL artifacts (``/graphql`` paths or ``query {`` strings)
- gRPC manifests (``proto`` files, ``grpc://`` URLs)
- Webhook URLs (callback / webhook fields)
- OpenAPI / Swagger blocks (``openapi`` / ``swagger`` keys)
- HAR files (``log.entries[].request``)
- Postman collections (``info._postman_id`` + ``item[].request``)
- SOAP (``wsdl`` URLs or namespace markers)

It also infers authentication mode (Bearer, Basic, API key, OAuth2, mTLS,
none) from auth headers and credential fields.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger
from app.models.saas_map_models import (
    ApiAuthMode,
    ApiDetectionResult,
    ApiEndpointDetection,
    ApiProtocol,
)

logger = get_logger(__name__)


_URL_REGEX = re.compile(
    r"\bhttps?://[a-zA-Z0-9_.\-]+\.[a-zA-Z]{2,}(?:/[\w\-./%~?=&+:#@!$',;*]*)?",
    re.IGNORECASE,
)
_GRPC_URL_REGEX = re.compile(r"\bgrpc(?:s)?://[a-zA-Z0-9_.\-]+", re.IGNORECASE)
_GRAPHQL_REGEX = re.compile(r"/graphql\b|\bquery\s*\{|\bmutation\s*\{|\bsubscription\s*\{", re.IGNORECASE)
_OPENAPI_REGEX = re.compile(r'\b(?:openapi|swagger)\s*[:=]\s*["\']?\d', re.IGNORECASE)
_WSDL_REGEX = re.compile(r"\bwsdl\b|<\s*soap:envelope|http://schemas\.xmlsoap\.org/", re.IGNORECASE)
_BEARER_HEADER = re.compile(r'(?i)authorization\s*[:=]\s*["\']?bearer\b')
_BASIC_HEADER = re.compile(r'(?i)authorization\s*[:=]\s*["\']?basic\b')
_API_KEY_HEADER = re.compile(r'(?i)\b(x[-_]?api[-_]?key|x[-_]?functions[-_]?key|apikey)\s*[:=]')

_WEBHOOK_KEYS = {
    "webhook", "webhook_url", "webhookurl", "callback", "callback_url",
    "callbackurl", "event_url", "events_url", "notification_url",
}
_API_ENDPOINT_KEYS = {
    "api_endpoint", "endpoint", "endpoint_url", "base_url", "baseurl", "api_url",
    "url", "uri", "host", "server",
}
_OAUTH_KEYS = {
    "oauth", "oauth2", "oauth_config", "oauth_provider", "authorization_url",
    "auth_url", "token_url", "redirect_uri",
}
_API_KEY_FIELDS = {"api_key", "apikey", "x-api-key", "x_api_key", "x-functions-key"}
_BASIC_AUTH_FIELDS = {"basic_auth", "username_password"}
_MTLS_FIELDS = {"client_certificate", "mtls_cert", "tls_client_cert", "client_cert"}
_ENDPOINT_LIMIT = 50


def _iter_nodes(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _iter_nodes(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_nodes(item)


def _redact_url(url: str, max_len: int = 120) -> str:
    """Strip token-like query params and trim length for evidence display."""
    if not url:
        return ""
    redacted = re.sub(
        r"((?:access_token|token|api_key|apikey|secret|key|bearer)=)[^&#\s]+",
        r"\1***",
        url,
        flags=re.IGNORECASE,
    )
    if len(redacted) > max_len:
        redacted = redacted[: max_len - 3] + "..."
    return redacted


def _classify_url_protocol(url: str) -> ApiProtocol:
    if "/graphql" in url.lower():
        return "graphql"
    if "wsdl" in url.lower():
        return "soap"
    return "rest"


def _is_webhook_url(url: str) -> bool:
    lower = url.lower()
    return (
        "webhook" in lower
        or "/hooks/" in lower
        or "://hooks." in lower
        or "callback" in lower
    )


def _detect_auth_in_text(text: str) -> set[ApiAuthMode]:
    modes: set[ApiAuthMode] = set()
    if not text:
        return modes
    if _BEARER_HEADER.search(text):
        modes.add("bearer")
    if _BASIC_HEADER.search(text):
        modes.add("basic")
    if _API_KEY_HEADER.search(text):
        modes.add("api_key")
    return modes


def _detect_auth_in_node(node: dict[str, Any]) -> set[ApiAuthMode]:
    modes: set[ApiAuthMode] = set()
    keys_lower = {k.lower() for k in node.keys()}
    if keys_lower & _OAUTH_KEYS or keys_lower & {"scope", "scopes"}:
        modes.add("oauth2")
    if keys_lower & {"access_token", "refresh_token", "bearer", "bearer_token"}:
        modes.add("bearer")
    if keys_lower & _API_KEY_FIELDS:
        modes.add("api_key")
    if keys_lower & _BASIC_AUTH_FIELDS or (
        "username" in keys_lower and "password" in keys_lower
    ):
        modes.add("basic")
    if keys_lower & _MTLS_FIELDS:
        modes.add("mtls")
    return modes


def _walk_payload(
    payload: Any,
) -> tuple[list[ApiEndpointDetection], set[ApiProtocol], set[ApiAuthMode], dict[str, bool]]:
    """Walk ``payload`` and collect endpoints, protocols, and auth modes."""
    endpoints: list[ApiEndpointDetection] = []
    protocols: set[ApiProtocol] = set()
    auth_modes: set[ApiAuthMode] = set()
    flags = {
        "has_webhook": False,
        "has_rest": False,
        "has_graphql": False,
        "has_openapi": False,
        "has_grpc": False,
        "has_har": False,
        "has_postman": False,
    }
    seen_urls: set[str] = set()

    if not isinstance(payload, (dict, list)):
        return endpoints, protocols, auth_modes, flags

    for node in _iter_nodes(payload):
        if not isinstance(node, dict):
            continue

        auth_modes |= _detect_auth_in_node(node)

        if "openapi" in node or "swagger" in node:
            flags["has_openapi"] = True
            protocols.add("openapi")
            protocols.add("rest")
            flags["has_rest"] = True

        log_block = node.get("log")
        if isinstance(log_block, dict) and isinstance(log_block.get("entries"), list):
            flags["has_har"] = True
            protocols.add("har")
            protocols.add("rest")
            flags["has_rest"] = True
            for entry in log_block["entries"][:_ENDPOINT_LIMIT]:
                request = entry.get("request") if isinstance(entry, dict) else None
                if isinstance(request, dict):
                    url = str(request.get("url") or "")
                    method = str(request.get("method") or "").upper()
                    if url and url not in seen_urls and len(endpoints) < _ENDPOINT_LIMIT:
                        seen_urls.add(url)
                        endpoints.append(
                            ApiEndpointDetection(
                                url=_redact_url(url),
                                method=method,
                                protocol=_classify_url_protocol(url),
                                auth_mode="unknown",
                                evidence="HAR entry",
                            )
                        )

        info = node.get("info")
        if isinstance(info, dict) and isinstance(info.get("_postman_id"), str):
            flags["has_postman"] = True
            protocols.add("postman")
            protocols.add("rest")
            flags["has_rest"] = True

        items = node.get("item")
        if isinstance(items, list) and flags.get("has_postman"):
            for item in items[:_ENDPOINT_LIMIT]:
                if not isinstance(item, dict):
                    continue
                request = item.get("request")
                if isinstance(request, dict):
                    url = request.get("url")
                    if isinstance(url, dict):
                        url = url.get("raw") or url.get("url") or ""
                    url = str(url or "")
                    method = str(request.get("method") or "").upper()
                    if url and url not in seen_urls and len(endpoints) < _ENDPOINT_LIMIT:
                        seen_urls.add(url)
                        endpoints.append(
                            ApiEndpointDetection(
                                url=_redact_url(url),
                                method=method,
                                protocol=_classify_url_protocol(url),
                                auth_mode="unknown",
                                evidence="Postman item",
                            )
                        )

        for key, value in node.items():
            key_lower = key.lower()
            if isinstance(value, str):
                value_str = value.strip()
                if not value_str:
                    continue
                # Direct webhook/endpoint fields
                if key_lower in _WEBHOOK_KEYS and value_str.startswith(("http://", "https://")):
                    flags["has_webhook"] = True
                    protocols.add("webhook")
                    flags["has_rest"] = True
                    protocols.add("rest")
                    if value_str not in seen_urls and len(endpoints) < _ENDPOINT_LIMIT:
                        seen_urls.add(value_str)
                        endpoints.append(
                            ApiEndpointDetection(
                                url=_redact_url(value_str),
                                method="POST",
                                protocol="webhook",
                                auth_mode="unknown",
                                evidence=f"key={key}",
                            )
                        )
                elif key_lower in _API_ENDPOINT_KEYS and value_str.startswith(("http://", "https://")):
                    proto: ApiProtocol = _classify_url_protocol(value_str)
                    if proto == "graphql":
                        flags["has_graphql"] = True
                    if _is_webhook_url(value_str):
                        flags["has_webhook"] = True
                        proto = "webhook"
                    protocols.add(proto)
                    flags["has_rest"] = flags["has_rest"] or proto == "rest"
                    if value_str not in seen_urls and len(endpoints) < _ENDPOINT_LIMIT:
                        seen_urls.add(value_str)
                        endpoints.append(
                            ApiEndpointDetection(
                                url=_redact_url(value_str),
                                method="",
                                protocol=proto,
                                auth_mode="unknown",
                                evidence=f"key={key}",
                            )
                        )
                # gRPC URLs in any string value
                if _GRPC_URL_REGEX.search(value_str):
                    flags["has_grpc"] = True
                    protocols.add("grpc")

    return endpoints, protocols, auth_modes, flags


def _walk_text(
    text: str,
) -> tuple[list[ApiEndpointDetection], set[ApiProtocol], set[ApiAuthMode], dict[str, bool]]:
    """Walk raw text content for URLs and auth markers."""
    endpoints: list[ApiEndpointDetection] = []
    protocols: set[ApiProtocol] = set()
    auth_modes: set[ApiAuthMode] = set()
    flags = {
        "has_webhook": False,
        "has_rest": False,
        "has_graphql": False,
        "has_openapi": False,
        "has_grpc": False,
    }
    if not text:
        return endpoints, protocols, auth_modes, flags

    auth_modes |= _detect_auth_in_text(text)

    if _OPENAPI_REGEX.search(text):
        flags["has_openapi"] = True
        protocols.add("openapi")
        protocols.add("rest")
        flags["has_rest"] = True
    if _GRAPHQL_REGEX.search(text):
        flags["has_graphql"] = True
        protocols.add("graphql")
    if _GRPC_URL_REGEX.search(text):
        flags["has_grpc"] = True
        protocols.add("grpc")
    if _WSDL_REGEX.search(text):
        protocols.add("soap")

    seen: set[str] = set()
    for match in _URL_REGEX.finditer(text):
        url = match.group(0)
        if url in seen or len(endpoints) >= _ENDPOINT_LIMIT:
            continue
        seen.add(url)
        proto: ApiProtocol = _classify_url_protocol(url)
        if proto == "graphql":
            flags["has_graphql"] = True
        if _is_webhook_url(url):
            flags["has_webhook"] = True
            proto = "webhook"
            protocols.add("webhook")
        else:
            flags["has_rest"] = flags["has_rest"] or proto == "rest"
        protocols.add(proto)
        endpoints.append(
            ApiEndpointDetection(
                url=_redact_url(url),
                method="",
                protocol=proto,
                auth_mode="unknown",
                evidence="text scan",
            )
        )
    return endpoints, protocols, auth_modes, flags


def _confidence(
    endpoints_count: int,
    protocols: set[ApiProtocol],
    auth_modes: set[ApiAuthMode],
) -> float:
    """Heuristic confidence: more signal -> higher confidence (capped 0..1)."""
    score = 0.0
    if endpoints_count > 0:
        score += min(0.5, endpoints_count * 0.05)
    score += min(0.3, len(protocols) * 0.1)
    if auth_modes - {"unknown", "none"}:
        score += 0.2
    return round(min(1.0, score), 2)


def detect(payload: Any = None, text: str = "") -> ApiDetectionResult:
    """Run API detection over the structured payload and raw text.

    Returns aggregated endpoints (capped), unique protocols/auth modes,
    boolean flags per protocol, and a heuristic confidence score.
    """
    p_endpoints, p_protos, p_auth, p_flags = _walk_payload(payload)
    t_endpoints, t_protos, t_auth, t_flags = _walk_text(text or "")

    seen: set[str] = set()
    merged_endpoints: list[ApiEndpointDetection] = []
    for ep in p_endpoints + t_endpoints:
        if ep.url and ep.url not in seen and len(merged_endpoints) < _ENDPOINT_LIMIT:
            seen.add(ep.url)
            merged_endpoints.append(ep)

    protocols = p_protos | t_protos
    auth_modes = p_auth | t_auth
    flags = {**p_flags, **t_flags}
    for k, v in p_flags.items():
        flags[k] = bool(v) or bool(flags.get(k))

    if auth_modes:
        auth_modes.discard("unknown")
    if not auth_modes:
        auth_modes = {"unknown"}

    if merged_endpoints and "unknown" in {ep.auth_mode for ep in merged_endpoints}:
        primary = next(iter(sorted(auth_modes - {"unknown"}))) if (auth_modes - {"unknown"}) else "unknown"
        merged_endpoints = [
            ep.model_copy(update={"auth_mode": primary if ep.auth_mode == "unknown" else ep.auth_mode})
            for ep in merged_endpoints
        ]

    return ApiDetectionResult(
        endpoints=merged_endpoints,
        protocols=sorted(protocols),
        auth_modes=sorted(auth_modes),
        has_webhook=bool(flags.get("has_webhook")),
        has_rest=bool(flags.get("has_rest")),
        has_graphql=bool(flags.get("has_graphql")),
        has_openapi=bool(flags.get("has_openapi")),
        has_grpc=bool(flags.get("has_grpc")),
        confidence=_confidence(len(merged_endpoints), protocols, auth_modes),
    )
