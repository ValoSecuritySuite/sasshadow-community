"""Core API routes — health, readiness, rule evaluation, plugins, policies, compliance.

SaaS-specific scan endpoints live in ``api/scan.py`` and are mounted
under the ``/scan`` prefix.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.compliance.framework_mapper import (
    SupportedFrameworksResponse,
    get_supported_frameworks,
)
from app.core.limiter import limiter
from app.core.config import settings
from app.models.scan_models import (
    ContextRuleSummary,
    HealthResponse,
    RuleEngineResult,
    RuleEvalRequest,
    RuleSet,
    RuleSetResponse,
    RulesInfo,
    TextScanRuleSummary,
)
from app.services.oauth_parser import get_oauth_policy
from app.services.rule_engine import evaluate
from app.services.rules_loader import load_rules

router = APIRouter()


# ---------------------------------------------------------------------------
# Plugins list (serialisable metadata only; no hook callables)
# ---------------------------------------------------------------------------

def _plugins_list() -> list[dict]:
    """Build list of plugin metadata for JSON response (no callables)."""
    from app.plugins.plugin_loader import get_loaded_plugins
    registry = get_loaded_plugins()
    out = []
    for name, info in registry.items():
        entry = {
            "name": name,
            "version": info.get("version", ""),
            "description": info.get("description", ""),
            "author": info.get("author", ""),
            "enabled": info.get("enabled", True),
            "hook_names": list(info.get("hooks", {}).keys()),
        }
        if info.get("tags"):
            entry["tags"] = info["tags"]
        out.append(entry)
    return out


def _build_rules_info(rule_set: RuleSet) -> RulesInfo:
    path = settings.rules_path
    ctx_summaries = [
        ContextRuleSummary(
            name=r.name,
            severity=r.severity,
            weight=r.weight,
            enabled=r.enabled,
            pattern_count=len(r.patterns),
        )
        for r in rule_set.rules
    ]
    ts_summaries = [
        TextScanRuleSummary(
            id=r.id,
            category=r.category,
            severity=r.severity,
            weight=r.weight,
            enabled=r.enabled,
            description=r.description,
        )
        for r in rule_set.text_scan_rules
    ]
    return RulesInfo(
        filename=path.name,
        filepath=str(path.resolve()),
        context_rule_count=len(rule_set.rules),
        text_scan_rule_count=len(rule_set.text_scan_rules),
        total_rule_count=len(rule_set.rules) + len(rule_set.text_scan_rules),
        context_rules=ctx_summaries,
        text_scan_rules=ts_summaries,
    )


def get_rules_service() -> RuleSetResponse:
    rules = load_rules()
    return RuleSetResponse(
        rules=rules.rules,
        text_scan_rules=rules.text_scan_rules,
        rules_info=_build_rules_info(rules),
    )


@router.get("/health", response_model=HealthResponse, tags=["Health"])
@limiter.limit("60/minute")
def health(request: Request) -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=HealthResponse, tags=["Health"])
@limiter.limit("60/minute")
def readiness(request: Request):
    from fastapi.responses import JSONResponse

    from app.core.config import settings

    if not settings.rules_path.exists():
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "rules_file_missing"},
        )
    return HealthResponse(status="ok")


@router.get("/rules", response_model=RuleSetResponse, tags=["Rules"])
@limiter.limit("100/minute")
def get_rules(
    request: Request,
    rules: Annotated[RuleSetResponse, Depends(get_rules_service)],
) -> RuleSetResponse:
    return rules


@router.post("/rules/evaluate", response_model=RuleEngineResult, tags=["Rules"])
@limiter.limit("60/minute")
def evaluate_rules(request: Request, payload: RuleEvalRequest) -> RuleEngineResult:
    rules = load_rules(use_cache=False)
    return evaluate(payload.context, rules)


@router.post("/rules/reload", tags=["Rules"])
@limiter.limit("10/minute")
def reload_rules(request: Request) -> dict:
    """Re-read ``default_yml_rule.yml`` from disk so a YAML edit takes
    effect without restarting the service."""
    from app.services.rules_loader import clear_rules_cache

    clear_rules_cache()
    rules = load_rules(use_cache=False)
    return {
        "status": "reloaded",
        "context_rules": len(rules.rules),
        "text_scan_rules": len(rules.text_scan_rules),
    }


@router.get("/plugins", tags=["Plugins"])
@limiter.limit("100/minute")
def list_plugins(request: Request) -> dict:
    """Return the list of loaded plugins (metadata only; hook callables are not exposed)."""
    return {"plugins": _plugins_list()}


# ---------------------------------------------------------------------------
# Policies & Compliance (for tooling/docs)
# ---------------------------------------------------------------------------

@router.get("/policies/oauth", tags=["Policies"])
@limiter.limit("100/minute")
def get_policies_oauth(request: Request) -> dict:
    """Return the parsed OAuth scope policy from oauth_scopes.yaml for tooling/docs."""
    return get_oauth_policy()


@router.get("/compliance/frameworks", response_model=SupportedFrameworksResponse, tags=["Compliance"])
@limiter.limit("100/minute")
def get_compliance_frameworks(request: Request) -> SupportedFrameworksResponse:
    """List supported compliance frameworks and control IDs for UI or integrations."""
    return get_supported_frameworks()
