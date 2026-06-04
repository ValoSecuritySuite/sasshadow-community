"""Tests for app/analysis/api_detector.py."""

from __future__ import annotations

from app.analysis.api_detector import detect


class TestRestDetection:
    def test_extracts_url_from_text(self) -> None:
        result = detect(text="See https://api.example.com/v1/users for users")
        assert result.has_rest is True
        assert any("api.example.com" in ep.url for ep in result.endpoints)
        assert "rest" in result.protocols

    def test_redacts_token_query_param(self) -> None:
        result = detect(text="https://example.com/x?access_token=abcdef12345")
        urls = [ep.url for ep in result.endpoints]
        assert urls
        assert "abcdef12345" not in urls[0]
        assert "***" in urls[0]


class TestWebhookDetection:
    def test_webhook_field_in_payload(self) -> None:
        payload = {"webhook_url": "https://hooks.example.com/incoming/abc"}
        result = detect(payload=payload)
        assert result.has_webhook is True
        assert "webhook" in result.protocols

    def test_webhook_url_pattern_in_text(self) -> None:
        result = detect(text="POST https://hooks.slack.com/services/T0/B0/abc")
        assert result.has_webhook is True


class TestGraphqlDetection:
    def test_url_with_graphql_path(self) -> None:
        result = detect(text="POST https://api.github.com/graphql")
        assert result.has_graphql is True

    def test_query_block_in_text(self) -> None:
        result = detect(text="query { user { id name } }")
        assert result.has_graphql is True


class TestOpenApiDetection:
    def test_openapi_key_in_payload(self) -> None:
        payload = {"openapi": "3.0.0", "paths": {}}
        result = detect(payload=payload)
        assert result.has_openapi is True
        assert result.has_rest is True

    def test_swagger_key_in_text(self) -> None:
        result = detect(text='swagger: "2.0"')
        assert result.has_openapi is True


class TestHarDetection:
    def test_har_log_entries(self) -> None:
        payload = {
            "log": {
                "entries": [
                    {"request": {"url": "https://api.example.com/v1/x", "method": "GET"}}
                ]
            }
        }
        result = detect(payload=payload)
        assert result.has_rest is True
        assert any(ep.evidence == "HAR entry" for ep in result.endpoints)


class TestPostmanDetection:
    def test_postman_collection(self) -> None:
        payload = {
            "info": {"_postman_id": "abc-123", "name": "Tests"},
            "item": [
                {
                    "name": "List users",
                    "request": {
                        "method": "GET",
                        "url": {"raw": "https://api.example.com/users"},
                    },
                }
            ],
        }
        result = detect(payload=payload)
        assert any(ep.evidence == "Postman item" for ep in result.endpoints)


class TestAuthInference:
    def test_bearer_header(self) -> None:
        result = detect(text='Authorization: Bearer abc123')
        assert "bearer" in result.auth_modes

    def test_basic_header(self) -> None:
        result = detect(text='Authorization: Basic Zm9vOmJhcg==')
        assert "basic" in result.auth_modes

    def test_api_key_field(self) -> None:
        payload = {"api_key": "secret_value"}
        result = detect(payload=payload)
        assert "api_key" in result.auth_modes

    def test_oauth2_marker(self) -> None:
        payload = {"oauth": {"scopes": ["read"]}}
        result = detect(payload=payload)
        assert "oauth2" in result.auth_modes

    def test_mtls_marker(self) -> None:
        payload = {"client_certificate": "-----BEGIN CERTIFICATE-----"}
        result = detect(payload=payload)
        assert "mtls" in result.auth_modes


class TestConfidenceScore:
    def test_no_signal_low_confidence(self) -> None:
        result = detect()
        assert result.confidence == 0

    def test_multiple_signals_higher(self) -> None:
        payload = {
            "openapi": "3.0.0",
            "webhook_url": "https://hooks.example.com/x",
            "api_key": "k",
        }
        result = detect(payload=payload, text="https://api.example.com/v1")
        assert result.confidence > 0.5
