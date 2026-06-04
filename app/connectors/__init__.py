"""Connectors to sync OAuth/integration data from external platforms.

Each connector fetches app lists or config from the provider API,
normalizes to the pipeline json_data shape, runs the scan pipeline,
and persists results to scan history.
"""

from app.connectors.entra import sync_entra
from app.connectors.slack import sync_slack

__all__ = [
    "sync_entra",
    "sync_slack",
]
