# Architecture (Community Edition)

SaaSShadow Community Edition is two services: a FastAPI backend and a Next.js
dashboard. The backend runs a deterministic scan pipeline and stores scan
history in SQLite.

## Request flow

```
client or connector
        |
        v
  POST /scan/analyze --> pipeline (normalize, detect, analyze, rules, score)
        |
        v
  ScanReport --> scan history (SQLite) --> dashboard and exports
```

PDF reports are generated from the same scan result via ReportLab.

## Main modules

| Layer | Location | Role |
|-------|----------|------|
| API | `app/api/` | Health, rules, scan, history, connectors, ISPM, dashboard |
| Pipeline | `app/services/pipeline.py` | End-to-end scan orchestration |
| Analyzers | `app/services/`, `app/analyzers/`, `app/analysis/` | OAuth, tokens, credentials, data flow, API detection |
| Rules | `app/services/rule_engine.py` | YAML context and text-scan rules |
| Persistence | `app/db/scan_history.py` | SQLite scan history |
| Frontend | `frontend/src/` | Dashboard UI |

## Data

- Scan history: SQLite file (default `data/scans.db`, override with
  `APP_SCAN_HISTORY_DB`).
- Rules and ISPM catalog: YAML on disk, reloadable without restart.

## Edition

This repository builds **Community Edition** only (`APP_EDITION=community`).
`GET /meta/edition` returns the edition name and which connectors are enabled.
