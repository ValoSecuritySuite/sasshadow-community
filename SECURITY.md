# Security policy

## Supported versions

| Version | Supported |
|---------|-----------|
| `v0.1.x` | Yes |

## Reporting a vulnerability

Report security vulnerabilities via **Security -> Report a vulnerability** on the
GitHub repository, or through the contact channel listed in the repository profile.

Please do not disclose exploitable issues in public issues before a fix is available.

Include:

- Affected component (API, web UI, connectors, policies)
- Steps to reproduce
- Impact assessment

Maintainers aim to acknowledge reports within five business days.

## Secure deployment

- Restrict CORS in production. The default API allows all origins for local
  development; set an explicit allow-list before exposing the API publicly.
- Connector sync endpoints (`/connectors/entra/sync`, `/connectors/slack/sync`)
  accept provider credentials in the request body. Run the API over TLS and
  treat those payloads as sensitive.
- Do not commit `.env` files, API keys, or production data under `data/` to
  version control.
