"""Batch SaaS integration dataset analysis.

Processes multiple integrations in a single request, detects shared
tokens across integrations, and produces per-item reports with an
aggregate summary.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.models.scan_models import (
    DatasetAnalysisRequest,
    DatasetAnalysisResponse,
    DatasetAnalysisSummary,
    DatasetItemResult,
    PipelineRequest,
    RuleSet,
)
from app.services.pipeline import run_pipeline
from app.services.risk_engine import risk_level_from_score


def _extract_token_candidates(payload: Any) -> list[str]:
    tokens: list[str] = []

    def _walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                lowered = key.lower()
                if isinstance(nested, str) and (
                    "token" in lowered or "secret" in lowered or "api_key" in lowered
                ):
                    tokens.append(nested.strip())
                _walk(nested)
        elif isinstance(value, list):
            for item in value:
                _walk(item)

    _walk(payload)
    return [t for t in tokens if t]


def analyze_dataset(payload: DatasetAnalysisRequest, rule_set: RuleSet) -> DatasetAnalysisResponse:
    token_counts: Counter[str] = Counter()
    for item in payload.items:
        if item.json_data is not None:
            token_counts.update(_extract_token_candidates(item.json_data))

    results: list[DatasetItemResult] = []

    for item in payload.items:
        metadata = dict(item.metadata)
        if item.json_data is not None:
            item_tokens = _extract_token_candidates(item.json_data)
            if any(token_counts.get(token, 0) > 1 for token in item_tokens):
                metadata["token_shared_across_integrations"] = True

        req = PipelineRequest(
            target=item.integration_id,
            text=item.text,
            json_data=item.json_data,
            metadata=metadata,
        )
        pipeline_result = run_pipeline(req, rule_set=rule_set)
        assert pipeline_result.report is not None  # noqa: S101

        signals = pipeline_result.saas_signals
        score = pipeline_result.report.risk_score

        results.append(
            DatasetItemResult(
                integration_id=item.integration_id,
                risk_score=score,
                risk_level=risk_level_from_score(score),
                oauth_over_permission_detected=signals.oauth.over_permissioned,
                token_misuse_detected=bool(signals.tokens.misuse_patterns),
                credential_exposure_detected=signals.credentials.exposed_credentials > 0,
                cross_platform_risk_detected=signals.data_flow.cross_platform_risk,
                report=pipeline_result.report,
            )
        )

    total = len(results)
    avg_score = round(sum(r.risk_score for r in results) / total, 2) if total else 0.0

    summary = DatasetAnalysisSummary(
        total_integrations=total,
        high_risk_integrations=sum(1 for r in results if r.risk_score >= 60),
        average_risk_score=avg_score,
        oauth_over_permission_hits=sum(1 for r in results if r.oauth_over_permission_detected),
        token_misuse_hits=sum(1 for r in results if r.token_misuse_detected),
        credential_exposure_hits=sum(1 for r in results if r.credential_exposure_detected),
        cross_platform_risk_hits=sum(1 for r in results if r.cross_platform_risk_detected),
    )

    return DatasetAnalysisResponse(
        dataset_name=payload.dataset_name,
        summary=summary,
        results=results,
    )
