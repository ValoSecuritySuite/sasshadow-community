"""Tests for app/analysis/ispm_classifier.py."""

from __future__ import annotations

import pytest

from app.analysis.ispm_classifier import (
    classify,
    clear_policy_cache,
    load_ispm_config,
    posture_grade,
)
from app.models.saas_map_models import PostureThresholds


@pytest.fixture(autouse=True)
def _reset_ispm_state() -> None:
    """Reset ISPM disk cache before each test."""
    clear_policy_cache()


class TestLoadConfig:
    def test_disk_config_has_categories(self) -> None:
        cfg = load_ispm_config()
        assert cfg.categories
        assert any(c.id == "identity" for c in cfg.categories)
        assert any(c.id == "communication" for c in cfg.categories)

    def test_provider_map_includes_known_providers(self) -> None:
        cfg = load_ispm_config()
        assert cfg.provider_map.get("microsoft_entra") == "identity"
        assert cfg.provider_map.get("slack") == "communication"
        assert cfg.provider_map.get("github") == "dev_code"


class TestClassify:
    def test_known_provider(self) -> None:
        assignment = classify("microsoft_entra")
        assert assignment.category_id == "identity"
        assert assignment.is_default is False

    def test_normalization(self) -> None:
        assignment = classify("Microsoft Entra")
        assert assignment.category_id == "identity"

    def test_unknown_provider_falls_back_to_default(self) -> None:
        assignment = classify("nonexistent_xyz_42")
        assert assignment.category_id == "other"
        assert assignment.is_default is True


class TestPostureGrade:
    def test_compliant_when_below_threshold(self) -> None:
        thresholds = PostureThresholds(compliant=30, at_risk=60)
        assert posture_grade(0, thresholds) == "COMPLIANT"
        assert posture_grade(30, thresholds) == "COMPLIANT"

    def test_at_risk_in_middle_band(self) -> None:
        thresholds = PostureThresholds(compliant=30, at_risk=60)
        assert posture_grade(31, thresholds) == "AT_RISK"
        assert posture_grade(60, thresholds) == "AT_RISK"

    def test_critical_above_at_risk(self) -> None:
        thresholds = PostureThresholds(compliant=30, at_risk=60)
        assert posture_grade(61, thresholds) == "CRITICAL"
        assert posture_grade(100, thresholds) == "CRITICAL"

    def test_clamps_negative(self) -> None:
        thresholds = PostureThresholds(compliant=30, at_risk=60)
        assert posture_grade(-5, thresholds) == "COMPLIANT"
