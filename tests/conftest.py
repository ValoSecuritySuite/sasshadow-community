"""Shared pytest fixtures."""

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Use a temp DB for scan history so tests don't touch real data
os.environ.setdefault(
    "APP_SCAN_HISTORY_DB",
    str(Path(tempfile.gettempdir()) / "saasshadow_test_scans.db"),
)

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    """FastAPI test client fixture."""
    return TestClient(app)
