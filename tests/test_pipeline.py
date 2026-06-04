"""Pipeline, normalizer, detection, and SaaS analysis tests."""

import json

import pytest
from fastapi.testclient import TestClient

from app.models.scan_models import (
    DetectionFlags,
    NormalizedInput,
    PipelineRequest,
    PipelineResult,
    RuleSet,
    TextScanRule,
)
from app.services.detection import detect
from app.services.normalizer import (
    normalize,
    normalize_bytes,
    normalize_json,
    normalize_text,
)
from app.services.pipeline import run_pipeline, run_pipeline_raw


# ── Normalizer ────────────────────────────────────────────────────────────────


class TestNormalizeText:
    def test_returns_normalized_input(self) -> None:
        result = normalize_text("hello world")
        assert isinstance(result, NormalizedInput)
        assert result.input_kind == "text"

    def test_content_is_cleaned(self) -> None:
        result = normalize_text("line1\r\nline2\r\n  spaces  ")
        assert "\r" not in result.content
        assert result.content == "line1\nline2\n  spaces"

    def test_content_length_matches(self) -> None:
        text = "some content here"
        result = normalize_text(text)
        assert result.content_length == len(result.content)

    def test_target_is_stored(self) -> None:
        result = normalize_text("x", target="my-file.py")
        assert result.target == "my-file.py"

    def test_metadata_is_stored(self) -> None:
        result = normalize_text("x", metadata={"severity": 3})
        assert result.metadata["severity"] == 3

    def test_encoding_is_utf8(self) -> None:
        result = normalize_text("text")
        assert result.encoding == "utf-8"


class TestNormalizeJson:
    def test_returns_normalized_input(self) -> None:
        result = normalize_json({"key": "value"})
        assert isinstance(result, NormalizedInput)
        assert result.input_kind == "json"

    def test_content_is_serialised_json(self) -> None:
        data = {"name": "Alice", "score": 42}
        result = normalize_json(data)
        parsed = json.loads(result.content)
        assert parsed["name"] == "Alice"
        assert parsed["score"] == 42

    def test_json_keys_merged_into_metadata(self) -> None:
        data = {"severity": 4, "source": "api"}
        result = normalize_json(data)
        assert result.metadata["severity"] == 4
        assert result.metadata["source"] == "api"

    def test_extra_metadata_preserved(self) -> None:
        result = normalize_json({"key": "v"}, metadata={"extra": True})
        assert result.metadata["extra"] is True


class TestNormalizeBytes:
    def test_utf8_bytes_decoded_correctly(self) -> None:
        raw = "hello world".encode("utf-8")
        result = normalize_bytes(raw, target="file.txt")
        assert result.content == "hello world"
        assert result.encoding == "utf-8"

    def test_utf8_bom_detected(self) -> None:
        raw = "\ufeffhello".encode("utf-8-sig")
        result = normalize_bytes(raw)
        assert "hello" in result.content
        assert result.encoding == "utf-8-sig"

    def test_filename_stored_in_metadata(self) -> None:
        raw = b"content"
        result = normalize_bytes(raw, filename="report.txt")
        assert result.metadata.get("filename") == "report.txt"

    def test_input_kind_is_bytes(self) -> None:
        result = normalize_bytes(b"data")
        assert result.input_kind == "bytes"

    def test_latin1_fallback_for_binary(self) -> None:
        raw = bytes(range(128, 256))
        result = normalize_bytes(raw)
        assert isinstance(result.content, str)


class TestNormalizeDispatch:
    def test_str_dispatches_to_text(self) -> None:
        result = normalize("hello")
        assert result.input_kind == "text"

    def test_dict_dispatches_to_json(self) -> None:
        result = normalize({"a": 1})
        assert result.input_kind == "json"

    def test_bytes_dispatches_to_bytes(self) -> None:
        result = normalize(b"raw bytes")
        assert result.input_kind == "bytes"


# ── Detection utilities ───────────────────────────────────────────────────────


class TestDetect:
    def _norm(self, content: str, kind: str = "text") -> NormalizedInput:
        return NormalizedInput(
            target="test", content=content, input_kind=kind, content_length=len(content)  # type: ignore[arg-type]
        )

    def test_returns_detection_flags(self) -> None:
        result = detect(self._norm("hello world"))
        assert isinstance(result, DetectionFlags)

    def test_email_flag(self) -> None:
        result = detect(self._norm("Contact us at admin@example.com today"))
        assert "contains_email" in result.flags

    def test_ip_flag(self) -> None:
        result = detect(self._norm("Server at 192.168.1.1 responded"))
        assert "contains_ip" in result.flags

    def test_url_flag(self) -> None:
        result = detect(self._norm("Visit https://example.com/api"))
        assert "contains_url" in result.flags

    def test_secret_keyword_flag(self) -> None:
        result = detect(self._norm("my password is hunter2"))
        assert "contains_secret_keyword" in result.flags

    def test_ssn_flag(self) -> None:
        result = detect(self._norm("SSN: 123-45-6789"))
        assert "contains_ssn_pattern" in result.flags

    def test_python_language_detected(self) -> None:
        code = "import os\ndef main():\n    pass"
        result = detect(self._norm(code))
        assert result.detected_language == "python"

    def test_json_content_type(self) -> None:
        result = detect(self._norm('{"key": "value"}', kind="json"))
        assert result.content_type == "json"

    def test_token_and_line_count(self) -> None:
        content = "word1 word2\nword3"
        result = detect(self._norm(content))
        assert result.token_count == 3
        assert result.line_count == 2

    def test_no_flags_for_clean_text(self) -> None:
        result = detect(self._norm("The quick brown fox jumps over the lazy dog."))
        for flag in ("contains_email", "contains_ssn_pattern", "contains_secret_keyword"):
            assert flag not in result.flags


# ── Pipeline orchestrator ─────────────────────────────────────────────────────


class TestRunPipeline:
    def _make_rules(self) -> RuleSet:
        return RuleSet(
            rules=[],
            text_scan_rules=[
                TextScanRule(
                    id="kw_password",
                    category="keyword",
                    pattern="password",
                    severity=3,
                    weight=20.0,
                )
            ],
        )

    def test_returns_pipeline_result(self) -> None:
        req = PipelineRequest(text="hello world")
        result = run_pipeline(req, rule_set=self._make_rules())
        assert isinstance(result, PipelineResult)

    def test_normalized_field_populated(self) -> None:
        req = PipelineRequest(text="some text", target="src.py")
        result = run_pipeline(req, rule_set=self._make_rules())
        assert result.normalized.target == "src.py"
        assert result.normalized.content == "some text"

    def test_detection_field_populated(self) -> None:
        req = PipelineRequest(text="import os\ndef main(): pass")
        result = run_pipeline(req, rule_set=self._make_rules())
        assert result.detection.detected_language == "python"

    def test_text_finding_captured_for_keyword_match(self) -> None:
        req = PipelineRequest(text="my password is here")
        result = run_pipeline(req, rule_set=self._make_rules())
        assert result.text_matched_count >= 1
        assert any(f.rule_id == "kw_password" for f in result.text_findings)

    def test_no_match_gives_zero_text_score(self) -> None:
        req = PipelineRequest(text="nothing interesting here at all")
        result = run_pipeline(req, rule_set=self._make_rules())
        assert result.text_scan_score == 0.0
        assert result.text_matched_count == 0

    def test_json_data_input(self) -> None:
        req = PipelineRequest(json_data={"key": "value", "secret": "abc"})
        result = run_pipeline(req, rule_set=self._make_rules())
        assert result.normalized.input_kind == "json"

    def test_pipeline_request_requires_at_least_one_input(self) -> None:
        with pytest.raises(Exception):
            PipelineRequest(text=None, json_data=None)

    def test_saas_signals_populated(self) -> None:
        req = PipelineRequest(
            json_data={
                "source_app": "salesforce",
                "destination_app": "slack",
                "oauth": {"scopes": ["files.readwrite.all", "admin"]},
                "data_types": ["pii"],
            }
        )
        result = run_pipeline(req, rule_set=self._make_rules())
        assert result.saas_signals.oauth.total_scopes >= 1
        assert result.saas_signals.data_flow.cross_platform_risk is True

    def test_report_includes_oauth_analysis(self) -> None:
        req = PipelineRequest(
            json_data={
                "source_app": "hubspot",
                "destination_app": "notion",
                "oauth_scopes": "contacts.read contacts.write",
            }
        )
        result = run_pipeline(req, rule_set=self._make_rules())
        assert result.report is not None
        assert result.report.oauth_analysis is not None


class TestRunPipelineRaw:
    def _simple_rules(self) -> RuleSet:
        return RuleSet(
            rules=[],
            text_scan_rules=[
                TextScanRule(id="kw_secret", category="keyword", pattern="secret", severity=4, weight=25.0)
            ],
        )

    def test_str_input(self) -> None:
        result = run_pipeline_raw("the secret is here", rule_set=self._simple_rules())
        assert isinstance(result, PipelineResult)
        assert result.text_matched_count >= 1

    def test_bytes_input(self) -> None:
        result = run_pipeline_raw(b"no secrets here", rule_set=self._simple_rules())
        assert isinstance(result, PipelineResult)
        assert result.normalized.input_kind == "bytes"

    def test_dict_input(self) -> None:
        result = run_pipeline_raw({"info": "secret key present"}, rule_set=self._simple_rules())
        assert result.normalized.input_kind == "json"

    def test_target_propagated(self) -> None:
        result = run_pipeline_raw("hello", target="my-target", rule_set=self._simple_rules())
        assert result.normalized.target == "my-target"


# ── Integration – /scan/analyze endpoint ──────────────────────────────────────


class TestScanAnalyzeEndpoint:
    def test_text_input_returns_200(self, client: TestClient) -> None:
        response = client.post("/scan/analyze", json={"text": "hello world", "target": "test"})
        assert response.status_code == 200

    def test_response_has_all_sections(self, client: TestClient) -> None:
        response = client.post("/scan/analyze", json={"text": "test content"})
        assert response.status_code == 200
        data = response.json()
        assert "normalized" in data
        assert "detection" in data
        assert "matched_rules" in data
        assert "text_findings" in data
        assert "combined_score" in data
        assert "saas_signals" in data

    def test_saas_signals_in_response(self, client: TestClient) -> None:
        response = client.post(
            "/scan/analyze",
            json={
                "target": "test-integration",
                "json_data": {
                    "source_app": "salesforce",
                    "destination_app": "slack",
                    "oauth": {"scopes": ["files.readwrite.all", "offline_access"]},
                    "credentials": {
                        "access_token": "Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"
                    },
                    "data_types": ["pii", "customer_data"],
                },
                "metadata": {"token_rotation_enabled": False},
            },
        )
        assert response.status_code == 200
        data = response.json()
        signals = data["saas_signals"]
        assert signals["oauth"]["total_scopes"] >= 2
        assert signals["oauth"]["over_permissioned"] is True
        assert signals["data_flow"]["cross_platform_risk"] is True

    def test_keyword_finding_captured(self, client: TestClient) -> None:
        response = client.post(
            "/scan/analyze",
            json={"text": "the password is hunter2"},
        )
        data = response.json()
        assert data["text_matched_count"] >= 1
        rule_ids = [f["rule_id"] for f in data["text_findings"]]
        assert "saas_password_keyword" in rule_ids

    def test_missing_both_inputs_returns_422(self, client: TestClient) -> None:
        response = client.post("/scan/analyze", json={"target": "test"})
        assert response.status_code == 422

    def test_score_capped_at_100(self, client: TestClient) -> None:
        response = client.post(
            "/scan/analyze",
            json={
                "text": (
                    "password secret access_token 123-45-6789 "
                    "admin@example.com Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
                )
            },
        )
        data = response.json()
        assert data["text_scan_score"] <= 100.0
        assert data["context_score"] <= 100.0
        assert data["combined_score"] <= 100.0

    def test_clean_content_returns_zero_text_score(self, client: TestClient) -> None:
        response = client.post(
            "/scan/analyze",
            json={"text": "The quick brown fox jumps over the lazy dog"},
        )
        data = response.json()
        assert data["text_scan_score"] == 0.0
        assert data["text_matched_count"] == 0

    def test_removed_legacy_path_returns_404(self, client: TestClient) -> None:
        response = client.post("/saas/analyze", json={"text": "hello", "target": "legacy"})
        assert response.status_code == 404
