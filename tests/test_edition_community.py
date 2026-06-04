"""Tests for Community Edition capability boundaries."""

from fastapi.testclient import TestClient

# Internal guard list: routes that must not exist in Community Edition.
_ABSENT_ROUTE_SAMPLES = (
    "/correlations/findings",
    "/playbooks",
    "/remediation/actions",
    "/saas-map/graph",
    "/reports",
    "/dashboard/posture",
    "/ispm/posture",
)

_ABSENT_CONNECTOR_SYNC = (
    "/connectors/google_workspace/sync",
    "/connectors/okta/sync",
    "/connectors/github/sync",
    "/connectors/atlassian/sync",
)


def test_meta_edition(client: TestClient) -> None:
    resp = client.get("/meta/edition")
    assert resp.status_code == 200
    body = resp.json()
    assert body["edition"] == "community"
    assert set(body["connectors"]) == {"entra", "slack"}
    assert "features" not in body


def test_extended_routes_are_absent(client: TestClient) -> None:
    for path in _ABSENT_ROUTE_SAMPLES:
        resp = client.get(path)
        assert resp.status_code == 404, f"{path} should be absent, got {resp.status_code}"


def test_extended_connectors_are_absent(client: TestClient) -> None:
    for path in _ABSENT_CONNECTOR_SYNC:
        resp = client.post(path, json={})
        assert resp.status_code == 404, f"{path} should be absent, got {resp.status_code}"


def test_community_scan_works(client: TestClient) -> None:
    resp = client.post(
        "/scan/analyze",
        json={
            "target": "community-test",
            "json_data": {
                "source_app": "salesforce",
                "destination_app": "slack",
                "oauth": {"scopes": ["files.readwrite.all", "admin"]},
                "data_types": ["pii"],
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "combined_score" in body
    assert "risk_summary" in body


def test_community_scan_history_works(client: TestClient) -> None:
    resp = client.get("/scans")
    assert resp.status_code == 200
    assert "scans" in resp.json()


def test_community_connectors_list(client: TestClient) -> None:
    resp = client.get("/connectors")
    assert resp.status_code == 200
    ids = {c["id"] for c in resp.json()["connectors"]}
    assert ids == {"entra", "slack"}


def test_community_dashboard_basic(client: TestClient) -> None:
    client.post(
        "/scan/analyze",
        json={"target": "dash-test", "text": "client_secret=abc123"},
    )
    resp = client.get("/dashboard/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert "scans_total" in body
    assert "posture_critical" not in body
    assert "open_proposals" not in body


def test_community_ispm_catalog_read_only(client: TestClient) -> None:
    cats = client.get("/ispm/categories")
    assert cats.status_code == 200
    assert "config" in cats.json()
    assert client.put("/ispm/categories", json={}).status_code == 405
