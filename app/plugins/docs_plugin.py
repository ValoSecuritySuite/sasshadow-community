"""Docs plugin: provide doc sections and generate/update docs from usage stats.

Hooks:
    get_doc_sections()              – return static doc sections (title + content)
    update_docs_from_usage(usage)   – generate doc content from usage stats
"""

from __future__ import annotations

from typing import Any

PLUGIN_NAME = "Docs"
PLUGIN_VERSION = "1.0.0"
PLUGIN_DESCRIPTION = (
    "Provides structured doc sections and can update documentation content "
    "based on usage statistics (e.g. most-used endpoints, scan counts)."
)
PLUGIN_AUTHOR = "Core Platform Team"
PLUGIN_TAGS = ["docs", "documentation", "usage"]


def _get_doc_sections() -> list[dict[str, str]]:
    """Return a list of doc sections with title and content (static)."""
    return [
        {
            "title": "Plugin system",
            "content": (
                "SaaSShadow supports a dynamic plugin system. Plugins live in "
                "`app/plugins/`, expose a `register()` function, and are loaded at "
                "startup. See docs/PLUGINS.md for the full contract and available plugins."
            ),
        },
        {
            "title": "Risk dimensions",
            "content": (
                "Analysis covers four dimensions: OAuth scope over-permission, "
                "token misuse, credential exposure, and cross-platform data flow risk. "
                "A composite 0–100 score is computed with optional severity ceilings."
            ),
        },
        {
            "title": "Reports",
            "content": (
                "Reports are available as JSON (full structure) and PDF (executive summary, "
                "findings, compliance mapping, remediation). Use the pipeline or "
                "`/scan/analyze` to generate a report."
            ),
        },
    ]


def _update_docs_from_usage(usage_stats: dict[str, Any]) -> dict[str, Any]:
    """Generate documentation content from usage statistics.

    Returns a dict with at least one of: sections, markdown, content.
    """
    sections: list[dict[str, str]] = []
    scans = usage_stats.get("scans", {})
    endpoints = usage_stats.get("endpoints", {})

    total_scans = scans.get("total", 0)
    by_target = scans.get("by_target", {})
    by_route = endpoints.get("by_route", {})

    sections.append({
        "title": "Usage summary (from Usage plugin)",
        "content": (
            f"Total scans run: **{total_scans}**. "
            f"Unique targets scanned: **{len(by_target)}**. "
            "Use the Usage plugin's `get_usage_summary()` for a live summary."
        ),
    })

    if by_route:
        top_routes = sorted(
            by_route.items(),
            key=lambda x: -x[1],
        )[:10]
        lines = ["| Route | Calls |", "|-------|-------|"]
        for route, count in top_routes:
            lines.append(f"| {route} | {count} |")
        sections.append({
            "title": "Most used endpoints (from usage)",
            "content": "\n".join(lines),
        })

    markdown_parts = []
    for sec in sections:
        markdown_parts.append(f"## {sec['title']}\n\n{sec['content']}\n")
    full_markdown = "\n".join(markdown_parts)

    return {
        "sections": sections,
        "markdown": full_markdown,
        "content": full_markdown,
    }


def register() -> dict[str, Any]:
    """Plugin entry point."""
    return {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "author": PLUGIN_AUTHOR,
        "tags": PLUGIN_TAGS,
        "enabled": True,
        "hooks": {
            "get_doc_sections": _get_doc_sections,
            "update_docs_from_usage": _update_docs_from_usage,
        },
    }
