# SaaSShadow

## Discover, Inventory and Govern SaaS & AI Applications

SaaSShadow is an open-source SaaS Security Posture Management (SSPM) and AI application discovery platform that helps organizations identify cloud applications, Shadow IT, and emerging AI services across their environments.

---

## Why SaaSShadow?

Organizations often don't know:

- Which SaaS applications employees use
- Which AI applications are connected
- Which OAuth applications present risk
- Where sensitive data is exposed

SaaSShadow provides continuous visibility.

---

## Features

- SaaS Discovery
- AI Application Discovery
- OAuth Risk Analysis
- Cloud Inventory
- Security Risk Scoring
- REST API
- Docker Support
- Extensible Connectors

---

## Supported Integrations

- Google Workspace
- GitHub
- Microsoft 365
- Salesforce

Additional connectors are community-driven.

---

## Architecture

```
Cloud Connectors
        │
        ▼
Discovery Engine
        │
        ▼
Inventory Database
        │
        ├── Risk Analysis
        ├── OAuth Review
        └── Reporting
```

---

## Quick start (Docker)

```bash
# One-command launcher
./start.sh          # macOS / Linux
start.bat           # Windows (double-click, or from cmd/PowerShell)

# Or Compose directly
docker compose up --build
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API + interactive docs | http://localhost:8000/docs |

---

## Roadmap

- Slack
- Zoom
- Box
- Dropbox
- Atlassian
- Okta
- AWS
- Azure
- GCP

---

## Community Contributions

Connector contributions are encouraged.

See CONTRIBUTING.md.

---

## Enterprise Platform

The commercial edition includes:

- Continuous Monitoring
- Enterprise Dashboards
- Alerting
- Historical Trending
- RBAC
- Compliance Reporting
- Multi-tenancy

---

## License

Apache 2.0

---

## Learn More

https://valosecurity.ai
