"""API endpoint integration tests."""

from fastapi.testclient import TestClient


def test_rules_endpoint(client: TestClient) -> None:
    response = client.get("/rules")
    assert response.status_code == 200
    data = response.json()
    assert "rules" in data
    assert isinstance(data["rules"], list)
    assert "rules_info" in data
    info = data["rules_info"]
    assert "filename" in info
    assert "context_rule_count" in info
    assert "text_scan_rule_count" in info
    assert "total_rule_count" in info
    assert info["total_rule_count"] == info["context_rule_count"] + info["text_scan_rule_count"]


def test_docs_available(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data.get("info", {}).get("title") == "SaaSShadow Community Edition"


def test_pdf_report_endpoint_success(client: TestClient) -> None:
    response = client.post(
        "/scan/report/pdf",
        json={
            "target": "sample.py",
            "text": "login as admin",
            "metadata": {"severity": 4, "source": "unit-test"},
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 0


def test_scan_analyze_endpoint(client: TestClient) -> None:
    response = client.post(
        "/scan/analyze",
        json={
            "target": "salesforce_to_slack",
            "json_data": {
                "source_app": "salesforce",
                "destination_app": "slack",
                "oauth": {"scopes": ["files.readwrite.all", "admin"]},
                "data_types": ["pii"],
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "saas_signals" in data
    assert "combined_score" in data
    assert data["combined_score"] >= 0
    assert "risk_summary" in data
    summary = data["risk_summary"]
    assert "integration" in summary
    assert "risk_score" in summary
    assert "severity" in summary
    assert "findings" in summary
    assert "dimension_scores" in summary
    assert summary["risk_score"] == data["combined_score"]


def test_scan_json_report_endpoint(client: TestClient) -> None:
    response = client.post(
        "/scan/report/json",
        json={
            "target": "test-integration",
            "json_data": {
                "source_app": "hubspot",
                "destination_app": "notion",
                "oauth_scopes": "contacts.read",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "risk_score" in data
    assert "risk_level" in data
    assert "oauth_analysis" in data


def test_scan_dataset_endpoint(client: TestClient) -> None:
    response = client.post(
        "/scan/dataset",
        json={
            "dataset_name": "test",
            "items": [
                {
                    "integration_id": "test_1",
                    "json_data": {"source_app": "a", "destination_app": "b"},
                },
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["total_integrations"] == 1


def test_policies_oauth_endpoint(client: TestClient) -> None:
    response = client.get("/policies/oauth")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "high_risk_scopes" in data or "safe_scopes" in data or "wildcard_patterns" in data


def test_compliance_frameworks_endpoint(client: TestClient) -> None:
    response = client.get("/compliance/frameworks")
    assert response.status_code == 200
    data = response.json()
    assert "frameworks" in data
    assert isinstance(data["frameworks"], list)
    framework_ids = {f["framework"] for f in data["frameworks"]}
    assert "SOC2" in framework_ids
    assert "ISO27001" in framework_ids
    for fw in data["frameworks"]:
        assert "framework" in fw
        assert "controls" in fw
        for c in fw["controls"]:
            assert "control_reference" in c


def test_scan_history_list_and_persist(client: TestClient) -> None:
    """GET /scans returns list; POST /scan/analyze persists and list includes it."""
    list_resp = client.get("/scans", params={"limit": 200})
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert "scans" in data
    initial_count = len(data["scans"])

    scan_resp = client.post(
        "/scan/analyze",
        json={
            "target": "history_test_integration",
            "json_data": {"source_app": "a", "destination_app": "b"},
            "customer_id": "customer_123",
        },
    )
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    scan_id = (scan_data.get("report") or {}).get("scan_id")
    assert scan_id, "response should contain report.scan_id"

    list_resp2 = client.get("/scans", params={"limit": 200})
    assert list_resp2.status_code == 200
    scans = list_resp2.json()["scans"]
    assert len(scans) >= initial_count + 1
    found = next((s for s in scans if s["id"] == scan_id), None)
    assert found is not None
    assert found["target"] == "history_test_integration"
    assert found["customer_id"] == "customer_123"
    assert "score" in found
    assert "risk_level" in found
    assert "timestamp" in found
    assert "findings_count" in found


def test_scan_history_get_by_id(client: TestClient) -> None:
    """GET /scans/{id} returns scan detail with key_findings; invalid id returns 404."""
    # Create a scan first
    scan_resp = client.post(
        "/scan/report/json",
        json={
            "target": "detail_test_target",
            "json_data": {"source_app": "x", "destination_app": "y"},
        },
    )
    assert scan_resp.status_code == 200
    report = scan_resp.json()
    scan_id = report["scan_id"]

    get_resp = client.get(f"/scans/{scan_id}")
    assert get_resp.status_code == 200
    detail = get_resp.json()
    assert detail["id"] == scan_id
    assert detail["target"] == "detail_test_target"
    assert "key_findings" in detail
    assert "score" in detail
    assert "timestamp" in detail

    not_found = client.get("/scans/00000000-0000-0000-0000-000000000000")
    assert not_found.status_code == 404


def test_scan_history_filter_by_target(client: TestClient) -> None:
    """GET /scans?target=... returns only scans for that target."""
    client.post(
        "/scan/analyze",
        json={"target": "filter_target_a", "json_data": {"source_app": "a", "destination_app": "b"}},
    )
    client.post(
        "/scan/analyze",
        json={"target": "filter_target_b", "json_data": {"source_app": "b", "destination_app": "c"}},
    )
    resp = client.get("/scans?target=filter_target_a")
    assert resp.status_code == 200
    scans = resp.json()["scans"]
    assert all(s["target"] == "filter_target_a" for s in scans)


def test_connectors_list(client: TestClient) -> None:
    """GET /connectors returns list of available connectors."""
    response = client.get("/connectors")
    assert response.status_code == 200
    data = response.json()
    assert "connectors" in data
    ids = [c["id"] for c in data["connectors"]]
    assert "entra" in ids
    assert "slack" in ids
    for c in data["connectors"]:
        assert "id" in c and "name" in c and "description" in c


def test_connectors_entra_sync_invalid_credentials(client: TestClient) -> None:
    """POST /connectors/entra/sync with bad credentials returns synced=0 and errors."""
    response = client.post(
        "/connectors/entra/sync",
        json={
            "tenant_id": "00000000-0000-0000-0000-000000000000",
            "client_id": "invalid",
            "client_secret": "invalid",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["connector"] == "entra"
    assert data["synced"] == 0
    assert isinstance(data["errors"], list)
    assert len(data["errors"]) >= 1


def test_connectors_slack_sync_invalid_token(client: TestClient) -> None:
    """POST /connectors/slack/sync with invalid token returns synced=0 and errors."""
    response = client.post(
        "/connectors/slack/sync",
        json={"token": "xoxb-invalid-token-for-test"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["connector"] == "slack"
    assert data["synced"] == 0
    assert isinstance(data["errors"], list)
    assert len(data["errors"]) >= 1


def test_scans_compare_last_two(client: TestClient) -> None:
    """GET /scans/compare?target=X uses last two scans for that target."""
    target = "compare_test_target"
    client.post("/scan/report/json", json={"target": target, "json_data": {"source_app": "a", "destination_app": "b"}})
    client.post("/scan/report/json", json={"target": target, "json_data": {"source_app": "a", "destination_app": "b"}})
    resp = client.get(f"/scans/compare?target={target}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["target"] == target
    assert "before_scan_id" in data
    assert "after_scan_id" in data
    assert data["before_scan_id"] != data["after_scan_id"]
    assert "score_before" in data and "score_after" in data
    assert "score_delta" in data
    assert "new_findings" in data and "mitigated_findings" in data


def test_scans_compare_insufficient_returns_404(client: TestClient) -> None:
    """GET /scans/compare?target=nonexistent returns 404 when fewer than 2 scans."""
    resp = client.get("/scans/compare?target=nonexistent_target_xyz")
    assert resp.status_code == 404


def test_scans_export_csv(client: TestClient) -> None:
    """GET /scans/export returns CSV."""
    resp = client.get("/scans/export")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert "scans_export" in resp.headers.get("content-disposition", "")
    lines = resp.text.strip().split("\n")
    assert len(lines) >= 1
    assert "id,target,timestamp,score" in lines[0] or "id" in lines[0]


def test_scan_findings_export_csv(client: TestClient) -> None:
    """GET /scans/{id}/findings/export returns CSV."""
    scan_resp = client.post(
        "/scan/report/json",
        json={"target": "findings_export_test", "json_data": {"source_app": "x", "destination_app": "y"}},
    )
    assert scan_resp.status_code == 200
    scan_id = scan_resp.json()["scan_id"]
    resp = client.get(f"/scans/{scan_id}/findings/export")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert "findings_" in resp.headers.get("content-disposition", "")


def test_dataset_export_csv(client: TestClient) -> None:
    """POST /scan/dataset?format=csv returns CSV."""
    resp = client.post(
        "/scan/dataset",
        params={"format": "csv"},
        json={"dataset_name": "csv_export_test", "items": [{"integration_id": "i1", "json_data": {"source_app": "a", "destination_app": "b"}}]},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert "dataset_" in resp.headers.get("content-disposition", "")
    assert "integration_id" in resp.text or "risk_score" in resp.text


def test_removed_legacy_paths_return_404(client: TestClient) -> None:
    response = client.post(
        "/saas/analyze",
        json={"text": "hello world", "target": "legacy-test"},
    )
    assert response.status_code == 404


def test_rules_reload_endpoint(client: TestClient) -> None:
    """POST /rules/reload returns counts and re-reads the YAML file."""
    response = client.post("/rules/reload")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "reloaded"
    assert isinstance(body["context_rules"], int)
    assert isinstance(body["text_scan_rules"], int)
