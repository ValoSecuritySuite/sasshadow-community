"""Tests for enterprise SaaS risk visibility: integration mapping, AI detection,
risk graph, compliance mapping, and full pipeline output shape.
"""

import pytest

from app.analysis.integration_mapper import IntegrationLink, IntegrationMap, map_integrations
from app.analysis.risk_graph import build_risk_graph
from app.analyzers.ai_integrations import RISK_DATA_TO_AI, detect_ai_integrations
from app.compliance.framework_mapper import map_findings_to_frameworks
from app.models.scan_models import PipelineRequest, RuleSet, TextFinding
from app.services.pipeline import run_pipeline
from app.services.rules_loader import load_rules


# ── Integration relationship extraction ──────────────────────────────────────


class TestIntegrationMapper:
    """Integration mapping extracts source/target and link types from scan input."""

    def test_extracts_source_and_destination_from_payload(self) -> None:
        payload = {
            "source_app": "slack",
            "destination_app": "jira",
            "oauth": {"scopes": ["chat:write"]},
        }
        out = map_integrations(payload, integration_id="slack_to_jira")
        assert out.systems
        assert "slack" in out.systems
        assert "jira" in out.systems
        assert out.links
        link = out.links[0]
        assert link.source == "slack"
        assert link.target == "jira"
        assert link.link_type in ("oauth", "api", "unknown")

    def test_infers_from_integration_id_when_payload_has_no_explicit_apps(self) -> None:
        payload = {"oauth": {"scopes": ["read"]}}
        out = map_integrations(payload, integration_id="github_to_jira")
        assert "github" in out.systems
        assert "jira" in out.systems
        assert any(l.source == "github" and l.target == "jira" for l in out.links)

    def test_sets_has_oauth_when_scopes_present(self) -> None:
        payload = {
            "source_app": "salesforce",
            "destination_app": "slack",
            "oauth": {"scopes": ["files.readwrite.all"]},
        }
        out = map_integrations(payload, "salesforce_to_slack")
        assert out.has_oauth is True

    def test_includes_data_types_on_links(self) -> None:
        payload = {
            "source_app": "google drive",
            "destination_app": "openai",
            "data_types": ["pii", "customer_data"],
        }
        out = map_integrations(payload, "gdrive_to_openai")
        assert out.links
        assert "pii" in out.links[0].data_types
        assert "customer_data" in out.links[0].data_types

    def test_uses_existing_source_destination_from_data_flow(self) -> None:
        out = map_integrations(
            {},
            integration_id="x",
            existing_source="okta",
            existing_destination="aws",
        )
        assert "okta" in out.systems
        assert "aws" in out.systems


# ── AI integration detection ───────────────────────────────────────────────────


class TestAIIntegrationDetection:
    """AI governance detector flags Slack->OpenAI, Drive->AI, and shadow AI usage."""

    def test_detects_destination_openai_as_enterprise_data_to_ai(self) -> None:
        payload = {
            "source_app": "slack",
            "destination_app": "openai",
            "data_types": ["pii"],
        }
        result = detect_ai_integrations(
            payload,
            content="",
            integration_id="slack_to_openai",
            destination_app="openai",
        )
        assert result.enterprise_data_to_ai is True
        assert result.findings
        assert any(f.category == RISK_DATA_TO_AI for f in result.findings)
        assert result.ai_risk_score > 0

    def test_detects_ai_provider_in_payload_keys(self) -> None:
        payload = {
            "source_app": "notion",
            "destination_app": "slack",
            "api_provider": "openai",
            "model": "gpt-4",
        }
        result = detect_ai_integrations(payload, content="", integration_id="notion_slack")
        assert result.shadow_ai_detected or result.unapproved_ai_detected
        assert result.findings

    def test_detects_ai_reference_in_content(self) -> None:
        content = '{"provider": "anthropic", "endpoint": "https://api.anthropic.com"}'
        result = detect_ai_integrations({}, content=content, content_location="config.json")
        assert result.findings
        assert result.shadow_ai_detected or result.unapproved_ai_detected

    def test_slack_to_openai_integration_id_triggers_data_to_ai(self) -> None:
        result = detect_ai_integrations(
            {"source_app": "slack", "destination_app": "openai"},
            integration_id="slack_to_openai",
        )
        assert result.enterprise_data_to_ai is True
        assert result.ai_risk_score >= 50


# ── Risk graph generation ─────────────────────────────────────────────────────


class TestRiskGraphGeneration:
    """Risk graph produces nodes (SaaS/AI) and edges with score, type, severity."""

    def test_graph_has_nodes_from_integration_map_systems(self) -> None:

        imap = IntegrationMap(
            integration_id="slack_to_jira",
            systems=["slack", "jira"],
            links=[
                IntegrationLink(source="slack", target="jira", link_type="oauth", direction="outbound"),
            ],
        )
        graph = build_risk_graph(imap, risk_score=65.0, findings=[], max_severity=4)
        assert len(graph.nodes) >= 2
        ids = {n.id for n in graph.nodes}
        assert "slack" in ids
        assert "jira" in ids
        assert graph.edges
        assert graph.edges[0].risk_score == 65.0
        assert graph.edges[0].connection_type == "oauth"
        assert graph.edges[0].severity == 4

    def test_graph_marks_ai_nodes_by_name(self) -> None:

        imap = IntegrationMap(
            integration_id="drive_to_openai",
            systems=["google drive", "openai"],
            links=[IntegrationLink(source="google drive", target="openai", link_type="api")],
        )
        graph = build_risk_graph(imap, risk_score=70.0)
        ai_nodes = [n for n in graph.nodes if n.node_type == "ai"]
        assert any("openai" in n.id for n in ai_nodes)
        assert graph.edges[0].findings_summary is not None  # list, may be empty

    def test_graph_includes_finding_summary_on_edges(self) -> None:

        imap = IntegrationMap(
            integration_id="a_to_b",
            systems=["a", "b"],
            links=[IntegrationLink(source="a", target="b", link_type="oauth")],
        )
        findings = [
            TextFinding(rule_id="credential_aws_access_key", category="regex", severity=5, weight=20.0, evidence="AKIA..."),
        ]
        graph = build_risk_graph(imap, risk_score=80.0, findings=findings, max_severity=5)
        assert graph.max_severity == 5
        assert graph.edges[0].findings_count == 1
        assert "credential" in (graph.edges[0].findings_summary or [""])[0] or ""


# ── Compliance framework mapping ───────────────────────────────────────────────


class TestComplianceFrameworkMapping:
    """Findings map to SOC 2, ISO 27001, NIST AI RMF with control ref and remediation."""

    def test_oauth_finding_maps_to_soc2_and_iso(self) -> None:
        findings = [
            TextFinding(rule_id="oauth_over_permission", category="context", severity=4, weight=15.0, evidence="scopes"),
        ]
        out = map_findings_to_frameworks(findings)
        assert out.mappings
        frameworks = {m.framework for m in out.mappings}
        assert "SOC2" in frameworks or "ISO27001" in frameworks
        for m in out.mappings:
            assert m.control_reference
            assert m.recommended_remediation

    def test_credential_finding_maps_to_soc2_cc6_6(self) -> None:
        findings = [
            TextFinding(rule_id="credential_client_secret", category="regex", severity=5, weight=20.0, evidence="client_secret=..."),
        ]
        out = map_findings_to_frameworks(findings)
        assert any(m.framework == "SOC2" and "CC6" in m.control_reference for m in out.mappings)
        assert any(len(m.recommended_remediation) > 20 for m in out.mappings)

    def test_ai_finding_maps_to_nist_ai_rmf(self) -> None:
        findings = [
            TextFinding(rule_id="ai_enterprise_data_to_ai", category="ai_governance", severity=5, weight=20.0, evidence="destination=openai"),
        ]
        out = map_findings_to_frameworks(findings, include_ai_context=True)
        assert any(m.framework == "NIST_AI_RMF" for m in out.mappings)
        assert "GOVERN" in str([m.control_reference for m in out.mappings]) or "MAP" in str([m.control_reference for m in out.mappings])

    def test_empty_findings_returns_empty_mappings(self) -> None:
        out = map_findings_to_frameworks([])
        assert out.mappings == []
        assert out.frameworks_covered == []

    def test_severity_and_rationale_present(self) -> None:
        findings = [
            TextFinding(rule_id="token_rotation_disabled", category="context", severity=4, weight=15.0, evidence="metadata"),
        ]
        out = map_findings_to_frameworks(findings)
        assert out.mappings
        for m in out.mappings:
            assert m.severity >= 1
            assert m.finding_type
            assert m.framework in ("SOC2", "ISO27001", "NIST_AI_RMF")


# ── Full pipeline output shape ────────────────────────────────────────────────


class TestPipelineOutputShape:
    """Full pipeline produces report with all enterprise and governance fields."""

    @pytest.fixture
    def rules(self) -> RuleSet:
        return load_rules(use_cache=False)

    def test_report_has_executive_summary(self, rules: RuleSet) -> None:
        req = PipelineRequest(
            target="slack_to_openai",
            json_data={"source_app": "slack", "destination_app": "openai", "oauth": {"scopes": ["chat:write"]}, "data_types": ["pii"]},
        )
        result = run_pipeline(req, rule_set=rules)
        assert result.report is not None
        assert result.report.executive_summary is not None
        assert "narrative" in result.report.executive_summary
        assert "metrics" in result.report.executive_summary

    def test_report_has_integration_visibility_summary(self, rules: RuleSet) -> None:
        req = PipelineRequest(
            target="github_to_jira",
            json_data={"source_app": "github", "destination_app": "jira", "oauth": {"scopes": ["repo"]}},
        )
        result = run_pipeline(req, rule_set=rules)
        assert result.report is not None
        assert result.report.integration_visibility_summary is not None
        assert "systems" in result.report.integration_visibility_summary
        assert "links" in result.report.integration_visibility_summary or "links_count" in result.report.integration_visibility_summary

    def test_report_has_top_risky_connections(self, rules: RuleSet) -> None:
        req = PipelineRequest(
            target="okta_to_aws",
            json_data={"source_app": "okta", "destination_app": "aws", "data_types": ["credentials"]},
        )
        result = run_pipeline(req, rule_set=rules)
        assert result.report is not None
        assert isinstance(result.report.top_risky_connections, list)

    def test_report_has_ai_data_flow_risks_when_ai_detected(self, rules: RuleSet) -> None:
        req = PipelineRequest(
            target="slack_to_openai",
            json_data={"source_app": "slack", "destination_app": "openai", "data_types": ["pii"]},
        )
        result = run_pipeline(req, rule_set=rules)
        assert result.report is not None
        assert result.report.ai_data_flow_risks is not None
        assert "ai_risk_detected" in result.report.ai_data_flow_risks
        assert result.report.ai_data_flow_risks.get("enterprise_data_to_ai") is True

    def test_report_has_compliance_mapping_structure(self, rules: RuleSet) -> None:
        req = PipelineRequest(
            target="salesforce_to_slack",
            json_data={
                "source_app": "salesforce",
                "destination_app": "slack",
                "oauth": {"scopes": ["files.readwrite.all", "users.readwrite.all"], "client_secret": "exposed-secret"},
                "credentials": {"access_token": "Bearer eyJhbGciOiJIUzI1NiJ9.xxx"},
                "data_types": ["pii"],
            },
        )
        result = run_pipeline(req, rule_set=rules)
        assert result.report is not None
        assert isinstance(result.report.compliance_mapping, list)
        for m in result.report.compliance_mapping or []:
            assert "framework" in m
            assert "control_reference" in m
            assert "recommended_remediation" in m

    def test_report_has_remediation_recommendations(self, rules: RuleSet) -> None:
        req = PipelineRequest(
            target="high_risk_integration",
            json_data={
                "source_app": "slack",
                "destination_app": "openai",
                "oauth": {"scopes": ["files:read", "users:read.email"]},
                "credentials": {"client_secret": "plaintext-secret"},
                "data_types": ["pii"],
            },
        )
        result = run_pipeline(req, rule_set=rules)
        assert result.report is not None
        assert isinstance(result.report.remediation_recommendations, list)
        for r in result.report.remediation_recommendations or []:
            assert "body" in r or "title" in r

    def test_report_has_risk_graph_with_nodes_and_edges(self, rules: RuleSet) -> None:
        req = PipelineRequest(
            target="slack_to_jira",
            json_data={"source_app": "slack", "destination_app": "jira", "oauth": {"scopes": ["chat:write"]}},
        )
        result = run_pipeline(req, rule_set=rules)
        assert result.report is not None
        assert result.report.risk_graph is not None
        assert "nodes" in result.report.risk_graph
        assert "edges" in result.report.risk_graph
        assert isinstance(result.report.risk_graph["nodes"], list)
        assert isinstance(result.report.risk_graph["edges"], list)
        if result.report.risk_graph["nodes"]:
            assert "id" in result.report.risk_graph["nodes"][0]
            assert "label" in result.report.risk_graph["nodes"][0]
        if result.report.risk_graph["edges"]:
            e = result.report.risk_graph["edges"][0]
            assert "source" in e and "target" in e
            assert "risk_score" in e and "connection_type" in e
