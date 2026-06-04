"""Tests for the plugin system: loader, PII Watchlist, Usage, and Docs plugins."""


from app.plugins.plugin_loader import (
    get_loaded_plugins,
    load_plugins,
    _REQUIRED_KEYS,
)


def test_plugin_loader_required_keys():
    """Required contract keys are defined."""
    assert "name" in _REQUIRED_KEYS
    assert "version" in _REQUIRED_KEYS
    assert "description" in _REQUIRED_KEYS
    assert "author" in _REQUIRED_KEYS
    assert "hooks" in _REQUIRED_KEYS


def test_load_plugins_returns_registry():
    """load_plugins() returns a dict keyed by plugin name."""
    registry = load_plugins()
    assert isinstance(registry, dict)
    for name, info in registry.items():
        assert isinstance(name, str)
        assert isinstance(info, dict)


def test_loaded_plugins_satisfy_contract():
    """Every loaded plugin has required keys and hooks is a dict of callables."""
    registry = load_plugins()
    for name, info in registry.items():
        for key in _REQUIRED_KEYS:
            assert key in info, f"Plugin {name!r} missing key {key!r}"
        assert isinstance(info["hooks"], dict), f"Plugin {name!r} hooks must be dict"
        for hook_name, call in info["hooks"].items():
            assert callable(call), f"Plugin {name!r} hook {hook_name!r} must be callable"


def test_get_loaded_plugins_returns_same_registry():
    """get_loaded_plugins() returns the same registry as load_plugins()."""
    load_plugins()
    registry = get_loaded_plugins()
    assert isinstance(registry, dict)
    assert registry is not None


# ---------------------------------------------------------------------------
# PII Watchlist plugin
# ---------------------------------------------------------------------------

def test_pii_watchlist_plugin_loaded():
    """PII Watchlist plugin is discovered and loaded."""
    registry = load_plugins()
    assert "PII Watchlist" in registry
    info = registry["PII Watchlist"]
    assert info["version"]
    assert "scan_text" in info["hooks"]
    assert "get_watchlist_info" in info["hooks"]
    assert "summarise" in info["hooks"]


def test_pii_watchlist_scan_text_returns_hits():
    """PII Watchlist scan_text hook finds patterns and returns hit dicts."""
    registry = load_plugins()
    assert "PII Watchlist" in registry
    scan_text = registry["PII Watchlist"]["hooks"]["scan_text"]
    text = "Contact me at user@example.com and my SSN is 123-45-6789."
    hits = scan_text(text)
    assert isinstance(hits, list)
    assert len(hits) >= 2  # email + ssn
    for h in hits:
        assert "category" in h
        assert "keyword" in h
        assert "severity" in h
        assert "match" in h
        assert "start" in h
        assert "end" in h


def test_pii_watchlist_get_watchlist_info_serialisable():
    """get_watchlist_info returns list of dicts without regex/callables."""
    registry = load_plugins()
    info_list = registry["PII Watchlist"]["hooks"]["get_watchlist_info"]()
    assert isinstance(info_list, list)
    for entry in info_list:
        assert "category" in entry
        assert "label" in entry
        assert "severity" in entry
        assert len(entry) == 3


def test_pii_watchlist_summarise():
    """summarise hook returns hit_count, max_severity, categories."""
    registry = load_plugins()
    summarise = registry["PII Watchlist"]["hooks"]["summarise"]
    out = summarise("Email: test@domain.com")
    assert "hits" in out
    assert "hit_count" in out
    assert "max_severity" in out
    assert "categories" in out
    assert out["hit_count"] >= 1
    assert out["max_severity"] >= 1


# ---------------------------------------------------------------------------
# Usage plugin
# ---------------------------------------------------------------------------

def test_usage_plugin_loaded():
    """Usage plugin is loaded and exposes usage hooks."""
    registry = load_plugins()
    assert "Usage" in registry
    info = registry["Usage"]
    assert "record_scan" in info["hooks"]
    assert "record_endpoint" in info["hooks"]
    assert "get_usage_stats" in info["hooks"]
    assert "get_usage_summary" in info["hooks"]


def test_usage_plugin_record_and_stats():
    """Recording scans and endpoints updates usage stats."""
    registry = load_plugins()
    record_scan = registry["Usage"]["hooks"]["record_scan"]
    record_endpoint = registry["Usage"]["hooks"]["record_endpoint"]
    get_usage_stats = registry["Usage"]["hooks"]["get_usage_stats"]
    record_scan("target_a", 72.5)
    record_scan("target_b", 90.0)
    record_endpoint("/scan/analyze", "POST")
    record_endpoint("/health", "GET")
    stats = get_usage_stats()
    assert "scans" in stats
    assert "endpoints" in stats
    assert stats["scans"]["total"] >= 2
    assert stats["scans"]["by_target"].get("target_a") is not None
    assert any(e.get("path") == "/scan/analyze" for e in stats["endpoints"]["calls"])


def test_usage_plugin_get_usage_summary():
    """get_usage_summary returns a non-empty string."""
    registry = load_plugins()
    get_usage_summary = registry["Usage"]["hooks"]["get_usage_summary"]
    summary = get_usage_summary()
    assert isinstance(summary, str)
    assert len(summary) > 0


# ---------------------------------------------------------------------------
# Docs plugin
# ---------------------------------------------------------------------------

def test_docs_plugin_loaded():
    """Docs plugin is loaded and exposes doc hooks."""
    registry = load_plugins()
    assert "Docs" in registry
    info = registry["Docs"]
    assert "get_doc_sections" in info["hooks"]
    assert "update_docs_from_usage" in info["hooks"]


def test_docs_plugin_get_doc_sections():
    """get_doc_sections returns a list of section dicts with title and content."""
    registry = load_plugins()
    get_doc_sections = registry["Docs"]["hooks"]["get_doc_sections"]
    sections = get_doc_sections()
    assert isinstance(sections, list)
    for sec in sections:
        assert "title" in sec
        assert "content" in sec


def test_docs_plugin_update_docs_from_usage():
    """update_docs_from_usage accepts usage stats and returns doc content."""
    registry = load_plugins()
    get_usage_stats = registry["Usage"]["hooks"]["get_usage_stats"]
    update_docs_from_usage = registry["Docs"]["hooks"]["update_docs_from_usage"]
    usage = get_usage_stats()
    doc_result = update_docs_from_usage(usage)
    assert isinstance(doc_result, dict)
    assert "sections" in doc_result or "markdown" in doc_result or "content" in doc_result
