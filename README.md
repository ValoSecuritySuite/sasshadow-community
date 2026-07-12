# SaaSShadow Community Edition

Open-source, self-hostable monitoring for SaaS-to-SaaS integrations. Find
over-permissioned OAuth scopes, risky API tokens, exposed credentials, and
sensitive data flowing between apps. Get clear risk scores and shareable
JSON and PDF reports.

SaaSShadow Enterprise adds multi-tenant operations, automated response,
deeper posture analytics, extra connectors, and managed deployment options.

## Quick start

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API + interactive docs | http://localhost:8000/docs |

Try a scan from the **Single Scan** page in the dashboard, or:

```bash
curl -s -X POST http://localhost:8000/scan/analyze \
  -H 'Content-Type: application/json' \
  -d "{\"target\": \"quickstart\", \"json_data\": $(cat demo/sample_integration.json)}"
```

Sample payloads: [`demo/README.md`](demo/README.md).

## What you get

- Integration risk scans with a 0-100 composite score
- JSON and executive PDF reports
- Scan history, comparison, and exports
- Microsoft Entra and Slack connectors (sync into scan history)
- Read-only ISPM provider catalog for classifying SaaS apps
- Dashboard with risk overview, trends, and critical findings
- Editable YAML detection rules
- Next.js dashboard and Docker Compose deployment

## Enterprise

The commercial SaaSShadow product adds tenant-wide mapping, automated
remediation and playbooks, correlation across security tools, scheduled
reporting packs, learning-loop tuning, extended ISPM posture views, custom
report branding, and additional connectors (Google Workspace, Okta, GitHub,
Atlassian). Those capabilities are not included in this repository.

Contact your Valo representative or visit valosecurity.ai for Enterprise licensing.

## Local development

Backend:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend && npm install && npm run dev
```

Production Compose:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

## Tests

```bash
pytest tests/test_edition_community.py tests/test_api.py -v
python scripts/community_smoke.py
```

## Documentation

- Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Connectors (Entra, Slack): [`docs/CONNECTORS.md`](docs/CONNECTORS.md)
- ISPM catalog: [`docs/ISPM.md`](docs/ISPM.md)
- Plugins: [`docs/PLUGINS.md`](docs/PLUGINS.md)
- Platform export how-to: [`docs/INTEGRATION_GUIDE.md`](docs/INTEGRATION_GUIDE.md)
- Frontend setup: [`frontend/README.md`](frontend/README.md)

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
