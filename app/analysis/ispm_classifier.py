"""ISPM (Integration Security Posture Management) classifier.

Resolves SaaS providers to ISPM categories and grades posture based on
risk score thresholds. Configuration is loaded from
``app/policies/ispm_categories.yaml``.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any, Optional

import yaml

from app.core.logging import get_logger
from app.models.saas_map_models import (
    IspmCategory,
    IspmCategoryAssignment,
    IspmConfig,
    PostureGrade,
    PostureThresholds,
)

logger = get_logger(__name__)


_POLICY_PATH = Path(__file__).resolve().parent.parent / "policies" / "ispm_categories.yaml"


# Disk policy cache (thread-safe). Customer overlays are read fresh on each
# load_ispm_config() call to keep admin updates visible immediately.
_disk_cache_lock = threading.Lock()
_disk_cache: dict[str, Any] | None = None


def _load_disk_policy() -> dict[str, Any]:
    """Load and cache the on-disk YAML policy."""
    global _disk_cache
    with _disk_cache_lock:
        if _disk_cache is not None:
            return _disk_cache
        if not _POLICY_PATH.exists():
            logger.warning(
                "ISPM policy not found at %s, using empty defaults", _POLICY_PATH
            )
            _disk_cache = {}
            return _disk_cache
        try:
            with _POLICY_PATH.open("r", encoding="utf-8") as fh:
                _disk_cache = yaml.safe_load(fh) or {}
        except Exception:
            logger.warning("Failed to parse ISPM policy YAML", exc_info=True)
            _disk_cache = {}
        return _disk_cache


def clear_policy_cache() -> None:
    """Reset disk cache (useful in tests and after admin writes)."""
    global _disk_cache
    with _disk_cache_lock:
        _disk_cache = None


def _normalize_provider(provider_id: str) -> str:
    """Lowercase and collapse whitespace; strip non-alnum runs to underscores."""
    if not provider_id:
        return ""
    cleaned = provider_id.strip().lower()
    cleaned = re.sub(r"[\s.\-/]+", "_", cleaned)
    return cleaned


def _coerce_thresholds(value: Any) -> PostureThresholds:
    if isinstance(value, PostureThresholds):
        return value
    if isinstance(value, dict):
        try:
            return PostureThresholds.model_validate(value)
        except Exception:
            return PostureThresholds()
    return PostureThresholds()


def _coerce_categories(raw: Any) -> list[IspmCategory]:
    out: list[IspmCategory] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            out.append(IspmCategory.model_validate(item))
        except Exception:
            cid = str(item.get("id") or "").strip().lower()
            label = str(item.get("label") or cid or "").strip()
            if cid:
                out.append(
                    IspmCategory(
                        id=cid,
                        label=label or cid,
                        description=item.get("description"),
                        posture_thresholds=_coerce_thresholds(
                            item.get("posture_thresholds")
                        ),
                    )
                )
    return out


def _build_config_from_dict(raw: dict[str, Any]) -> IspmConfig:
    categories = _coerce_categories(raw.get("categories"))
    provider_map_raw = raw.get("provider_map") or {}
    provider_map: dict[str, str] = {}
    if isinstance(provider_map_raw, dict):
        for key, value in provider_map_raw.items():
            nk = _normalize_provider(str(key))
            nv = str(value or "").strip().lower()
            if nk and nv:
                provider_map[nk] = nv
    default_category = str(raw.get("default_category_id") or "other").strip().lower()
    default_thresholds = _coerce_thresholds(raw.get("default_thresholds"))
    if not categories:
        categories = [
            IspmCategory(
                id=default_category,
                label=default_category.title() or "Other",
                posture_thresholds=default_thresholds,
            )
        ]
    return IspmConfig(
        categories=categories,
        provider_map=provider_map,
        default_category_id=default_category,
        default_thresholds=default_thresholds,
    )


def load_ispm_config(customer_id: Optional[str] = None) -> IspmConfig:
    """Return the ISPM config from the on-disk default catalog.

    The ``customer_id`` argument is accepted for interface compatibility;
    Community Edition always resolves the default ``ispm_categories.yaml``
    catalog.
    """
    base = dict(_load_disk_policy() or {})
    return _build_config_from_dict(base)


def classify(
    provider_id: str,
    config: IspmConfig | None = None,
    customer_id: Optional[str] = None,
) -> IspmCategoryAssignment:
    """Resolve provider -> category, falling back to default_category_id."""
    cfg = config or load_ispm_config(customer_id)
    norm = _normalize_provider(provider_id)
    raw_norm = (provider_id or "").strip().lower()
    candidates = [norm, raw_norm]
    category_id: str | None = None
    for cand in candidates:
        if cand and cand in cfg.provider_map:
            category_id = cfg.provider_map[cand]
            break
    is_default = category_id is None
    if is_default:
        category_id = cfg.default_category_id

    cat = next((c for c in cfg.categories if c.id == category_id), None)
    label = cat.label if cat else (category_id.replace("_", " ").title() if category_id else "Other")
    thresholds = cat.posture_thresholds if cat else cfg.default_thresholds
    return IspmCategoryAssignment(
        provider_id=norm or raw_norm,
        category_id=category_id or cfg.default_category_id,
        label=label,
        is_default=is_default,
        posture_thresholds=thresholds,
    )


def posture_grade(risk_score: float, thresholds: PostureThresholds) -> PostureGrade:
    """Return COMPLIANT / AT_RISK / CRITICAL for a risk score given thresholds."""
    score = max(0.0, min(100.0, float(risk_score or 0.0)))
    if score <= thresholds.compliant:
        return "COMPLIANT"
    if score <= thresholds.at_risk:
        return "AT_RISK"
    return "CRITICAL"


def aggregate_overall_grade(
    grade_counts: dict[PostureGrade, int],
) -> PostureGrade:
    """Reduce a per-grade count map to a single overall grade.

    Worst-grade-wins semantics: if any CRITICAL exists, overall is CRITICAL;
    else if any AT_RISK, overall is AT_RISK; else COMPLIANT.
    """
    if grade_counts.get("CRITICAL", 0) > 0:
        return "CRITICAL"
    if grade_counts.get("AT_RISK", 0) > 0:
        return "AT_RISK"
    return "COMPLIANT"
