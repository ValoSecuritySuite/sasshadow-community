"""Microsoft Entra (Azure AD) app manifest analyzer.

Parses ``requiredResourceAccess`` blocks from Entra / Microsoft Graph
application manifests. Each block contains ``resourceAccess`` entries
with permission GUIDs and a type of ``"Scope"`` (delegated) or
``"Role"`` (application-level).

The analyzer maps well-known Microsoft Graph permission GUIDs to
human-readable scope names, classifies risk, and converts the result
into an :class:`OAuthAnalysis` that plugs directly into the existing
scoring pipeline.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.models.scan_models import OAuthAnalysis, OAuthScopeRisk

logger = get_logger(__name__)

# Microsoft Graph resource app ID
_MS_GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"

# Well-known Microsoft Graph permission GUIDs → human-readable names.
# Sourced from https://learn.microsoft.com/en-us/graph/permissions-reference
_GRAPH_PERMISSION_MAP: dict[str, str] = {
    # Delegated (Scope)
    "e1fe6dd8-ba31-4d61-89e7-88639da4683d": "User.Read",
    "14dad69e-099b-42c9-810b-d002981feec1": "profile",
    "37f7f235-527c-4136-accd-4a02d197296e": "openid",
    "7427e0e9-2fba-42fe-b0c0-848c9e6a8182": "offline_access",
    "570282fd-fa5c-430d-a7fd-fc8dc98a9dca": "email",
    "024d486e-b451-40bb-833d-3e66d98c5c73": "Mail.Read",
    "e383f46e-2787-4529-855e-0e479a3ffac0": "Mail.Send",
    "b633e1c5-b582-4048-a93e-9f11b44c7e96": "Mail.ReadWrite",
    "863451e7-0667-486c-a5d6-d135439485f0": "Files.ReadWrite.All",
    "10465720-29dd-4523-a11a-6a75c743c9d9": "Files.Read.All",
    "e2a3a72e-5f79-4c64-b1b1-878b674786c9": "Directory.ReadWrite.All",
    "06da0dbc-49e2-44d2-8312-53f166ab848a": "Directory.Read.All",
    "5b567255-7703-4780-807c-7be8301ae99b": "Group.Read.All",
    "4e46008b-f24c-477d-8fff-7bb4ec7aafe0": "Group.ReadWrite.All",
    "204e0828-b5ca-4571-a349-6743c2258ba2": "User.ReadWrite.All",
    "741f803b-c850-494e-b5df-cde7c675a1ca": "User.ReadWrite",
    "df021288-bdef-4463-88db-98f22de89214": "User.Read.All",
    "09850681-111b-4a89-9571-53f2b3456e57": "Sites.Read.All",
    "65e50fdc-43b7-4571-ae61-b6e17feeb0b8": "Sites.Manage.All",
    # Application (Role)
    "798ee544-9d2d-430c-a058-570e29e34338": "Calendars.Read (App)",
    "ef54d2bf-783f-4e0f-bca1-3210c0444d99": "Calendars.ReadWrite (App)",
    "089fe4d0-434a-44c5-8827-41ba8a0b17f5": "Contacts.Read (App)",
    "6918b873-d688-4a76-8b30-e12c220e0284": "Contacts.ReadWrite (App)",
    "810c84a8-4a9e-49e6-bf7d-12d183f40d01": "Mail.Read (App)",
    "b633e1c5-b582-4048-a93e-9f11b44c7e96_app": "Mail.ReadWrite (App)",
    "e2a3a72e-5f79-4c64-b1b1-878b674786c9_app": "Directory.ReadWrite.All (App)",
    "7ab1d382-f21e-4acd-a863-ba3e13f7da61": "Directory.Read.All (App)",
    "19dbc75e-c2e2-444c-a770-ec596d67c8f0": "User.ReadWrite.All (App)",
    "df021288-bdef-4463-88db-98f22de89214_app": "User.Read.All (App)",
}

_HIGH_RISK_PATTERNS = {
    "readwrite.all", "directory.readwrite", "user.readwrite.all",
    "mail.send", "sites.manage", "organization.readwrite",
    "(app)",
}

_SAFE_SCOPE_NAMES = {"user.read", "profile", "openid", "email", "offline_access"}


def _is_high_risk(scope_name: str) -> tuple[bool, int, str]:
    lowered = scope_name.lower()
    for pattern in _HIGH_RISK_PATTERNS:
        if pattern in lowered:
            if "(app)" in lowered:
                return True, 5, "Application-level permission — no user consent required"
            if "directory" in lowered or "user.readwrite.all" in lowered:
                return True, 5, "Organization-wide write access"
            if "mail.send" in lowered:
                return True, 4, "Can send email on behalf of users — phishing vector"
            if "sites.manage" in lowered:
                return True, 5, "SharePoint management — data exfiltration risk"
            return True, 4, f"Broad write access: {scope_name}"
    return False, 1, ""


def _is_wildcard(scope_name: str) -> bool:
    lowered = scope_name.lower()
    return any(p in lowered for p in (".all", "full_access", ".*"))


def analyze_entra_manifest(payload: Any) -> OAuthAnalysis | None:
    """Analyze a Microsoft Entra app manifest for OAuth permission risks.

    Returns ``None`` if the payload does not look like an Entra manifest
    (i.e. no ``requiredResourceAccess`` key), allowing the caller to
    fall back to the generic OAuth parser.
    """
    if not isinstance(payload, dict):
        return None

    rra = payload.get("requiredResourceAccess")
    if not isinstance(rra, list) or not rra:
        return None

    logger.info("Entra manifest detected — parsing requiredResourceAccess")

    scopes: list[str] = []
    high_risk_scopes: list[OAuthScopeRisk] = []
    wildcard_scopes: list[str] = []
    safe_scopes: list[str] = []

    for resource_block in rra:
        if not isinstance(resource_block, dict):
            continue
        resource_app_id = resource_block.get("resourceAppId", "")
        access_list = resource_block.get("resourceAccess", [])
        if not isinstance(access_list, list):
            continue

        for entry in access_list:
            if not isinstance(entry, dict):
                continue
            perm_id = str(entry.get("id", "")).lower()
            perm_type = str(entry.get("type", "")).lower()

            # Resolve human-readable name
            lookup_key = perm_id
            if perm_type == "role":
                lookup_key = f"{perm_id}_app"
            scope_name = _GRAPH_PERMISSION_MAP.get(lookup_key)
            if not scope_name:
                scope_name = _GRAPH_PERMISSION_MAP.get(perm_id)
            if not scope_name:
                scope_name = f"unknown:{perm_id[:8]}({perm_type})"

            scopes.append(scope_name)

            if scope_name.lower() in _SAFE_SCOPE_NAMES:
                safe_scopes.append(scope_name)
                continue

            is_wc = _is_wildcard(scope_name)
            if is_wc:
                wildcard_scopes.append(scope_name)

            is_hr, sev, desc = _is_high_risk(scope_name)
            if perm_type == "role" and not is_hr:
                is_hr = True
                sev = max(sev, 4)
                desc = desc or "Application-level permission — no user consent required"

            if is_hr or is_wc:
                high_risk_scopes.append(OAuthScopeRisk(
                    scope=scope_name,
                    risk_level=_risk_level(sev),
                    severity=sev,
                    description=desc,
                    is_wildcard=is_wc,
                ))

    over_permissioned = bool(
        len(wildcard_scopes) >= 1
        or len(high_risk_scopes) >= 2
        or len(scopes) >= 8
    )

    if not high_risk_scopes:
        scope_risk_score = 0.0
    else:
        max_sev = max(s.severity for s in high_risk_scopes)
        breadth = min(len(high_risk_scopes) * 8.0, 30.0)
        base = {5: 60.0, 4: 45.0, 3: 30.0, 2: 15.0, 1: 5.0}.get(max_sev, 10.0)
        scope_risk_score = min(100.0, base + breadth + (10.0 if over_permissioned else 0.0))

    return OAuthAnalysis(
        total_scopes=len(scopes),
        scopes=scopes,
        high_risk_scopes=high_risk_scopes,
        wildcard_scopes=wildcard_scopes,
        safe_scopes=safe_scopes,
        over_permissioned=over_permissioned,
        scope_risk_score=round(scope_risk_score, 2),
    )


def _risk_level(sev: int) -> str:
    if sev >= 5:
        return "CRITICAL"
    if sev >= 4:
        return "HIGH"
    if sev >= 3:
        return "MEDIUM"
    if sev >= 2:
        return "LOW"
    return "MINIMAL"
