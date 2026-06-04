# SaaSShadow Plugin System

## Overview

SaaSShadow supports a **dynamic plugin system**. Plugins are Python modules under `app/plugins/` that expose a `register()` function. They are discovered and loaded once at application startup. The application (or other plugins) can then look up plugins by name and call their hooks without knowing implementation details.

---

## Plugin contract

Every plugin module **must**:

1. Live under `app/plugins/` (e.g. `app/plugins/my_plugin.py`).
2. Define a **`register()`** function that returns a dict with these **required** keys:

| Key           | Type   | Description                          |
|---------------|--------|--------------------------------------|
| `name`        | str    | Human-readable plugin name (unique)  |
| `version`     | str    | Semantic version, e.g. `"1.0.0"`     |
| `description` | str    | Short description                    |
| `author`      | str    | Author or team name                  |
| `hooks`       | dict   | Map of hook name → callable          |

**Optional** keys: `tags` (list[str]), `enabled` (bool, default True).

The loader skips:

- Modules that do not define `register()`.
- Modules named `plugin_loader`.
- Any module that raises when `register()` is called or returns a dict missing required keys.

---

## Lifecycle

- **Startup:** `load_plugins()` is called from the FastAPI lifespan. It imports every submodule of `app.plugins`, calls `register()` on each that has it, and stores the result in a global registry keyed by **plugin name**.
- **Runtime:** Use `get_loaded_plugins()` to obtain the registry and call hooks by name, e.g. `get_loaded_plugins()["PII Watchlist"]["hooks"]["scan_text"](text)`.

---

## Available plugins

### 1. PII Watchlist

- **Name:** `PII Watchlist`
- **Purpose:** Scans text for PII and sensitive patterns (SSN, email, credentials, etc.) using a categorised watchlist.

**Hooks:**

| Hook                 | Signature                    | Description |
|----------------------|------------------------------|-------------|
| `scan_text`          | `(text: str) -> list[dict]`  | Scan text; return list of hits (category, keyword, severity, match, start, end). |
| `get_watchlist_info` | `() -> list[dict]`           | Return serialisable watchlist catalogue (category, label, severity). |
| `summarise`          | `(text: str) -> dict`        | Return `{hits, hit_count, max_severity, categories}`. |

**Example:**

```python
from app.plugins.plugin_loader import get_loaded_plugins

plugins = get_loaded_plugins()
if "PII Watchlist" in plugins:
    scan_fn = plugins["PII Watchlist"]["hooks"]["scan_text"]
    hits = scan_fn("Email: user@example.com, SSN 123-45-6789")
    # hits -> [{"category": "pii", "keyword": "email", ...}, ...]
```

---

### 2. Usage

- **Name:** `Usage`
- **Purpose:** Tracks scan and API usage in memory and exposes stats plus a short summary (for dashboards or docs).

**Hooks:**

| Hook               | Signature                          | Description |
|--------------------|------------------------------------|-------------|
| `record_scan`      | `(target: str, score: float) -> None` | Record a scan for `target` with risk `score`. |
| `record_endpoint`  | `(path: str, method: str) -> None` | Record an API call (e.g. path, method). |
| `get_usage_stats`  | `() -> dict`                      | Full stats: `scans` (total, by_target, recent), `endpoints` (total_calls, calls, by_route). |
| `get_usage_summary`| `() -> str`                       | Short human-readable summary string. |

**Example:**

```python
from app.plugins.plugin_loader import get_loaded_plugins

plugins = get_loaded_plugins()
if "Usage" in plugins:
    hooks = plugins["Usage"]["hooks"]
    hooks["record_scan"]("github_to_jira", 85.0)
    hooks["record_endpoint"]("/scan/analyze", "POST")
    stats = hooks["get_usage_stats"]()
    summary = hooks["get_usage_summary"]()
```

**Note:** Storage is in-memory and process-local. For multi-process or persistent usage, integrate with Redis or a database and call these hooks from your storage layer.

---

### 3. Docs

- **Name:** `Docs`
- **Purpose:** Provides static doc sections and **updates documentation content from usage stats** (e.g. most-used endpoints, scan counts).

**Hooks:**

| Hook                   | Signature                              | Description |
|------------------------|----------------------------------------|-------------|
| `get_doc_sections`     | `() -> list[dict]`                    | Static sections: each `{title, content}`. |
| `update_docs_from_usage` | `(usage_stats: dict) -> dict`      | Build doc content from Usage plugin stats. Returns `{sections, markdown, content}`. |

**Example:**

```python
from app.plugins.plugin_loader import get_loaded_plugins

plugins = get_loaded_plugins()
if "Docs" in plugins and "Usage" in plugins:
    usage_stats = plugins["Usage"]["hooks"]["get_usage_stats"]()
    doc_result = plugins["Docs"]["hooks"]["update_docs_from_usage"](usage_stats)
    # doc_result["markdown"] or doc_result["sections"] can be written to docs or API.
```

---

## Adding a new plugin

1. Create `app/plugins/<module_name>.py` (do not use `plugin_loader` as the module name).
2. Implement `register()` returning a dict with `name`, `version`, `description`, `author`, and `hooks`.
3. (Optional) Add `tags` and `enabled`.
4. Restart the app so `load_plugins()` runs again.
5. Update this document (and any API docs) with the new plugin’s name and hooks.

---

## Testing

Plugin discovery and hook behaviour are covered in `tests/test_plugins.py`:

- Loader contract and required keys.
- PII Watchlist: `scan_text`, `get_watchlist_info`, `summarise`.
- Usage: `record_scan`, `record_endpoint`, `get_usage_stats`, `get_usage_summary`.
- Docs: `get_doc_sections`, `update_docs_from_usage`.

Run:

```bash
pytest tests/test_plugins.py -v
```
