# SaaSShadow Black Hat Power Demo

SaaSShadow already exposes the dashboard at `http://localhost:3000` and the API at `http://localhost:8000`. This launcher adds a presentation-ready startup experience with preflight checks, clean resets, health validation, browser launch, and a concise presenter flow.

## Launch on Windows

Double-click:

```text
run-saasshadow-demo.bat
```

Or run from Command Prompt or PowerShell:

```powershell
.\run-saasshadow-demo.bat
```

## Launch on macOS, Linux, Git Bash, or WSL

```bash
chmod +x run-saasshadow-demo.sh
./run-saasshadow-demo.sh
```

## What the launcher does

1. Confirms Docker and Docker Compose are available.
2. Confirms Docker is running.
3. Creates `.env` from `.env.example` when needed.
4. Stops stale containers and removes orphans.
5. Rebuilds and launches the API and frontend.
6. Waits for API and dashboard readiness.
7. Opens the dashboard automatically.
8. Prints a Black Hat presenter flow and recovery commands.

## Presenter flow

1. **Executive risk overview** — establish the scale of unmanaged SaaS and AI usage.
2. **Application discovery** — reveal SaaS, AI services, ownership, and usage context.
3. **OAuth risk analysis** — show dangerous scopes, privileged access, and exposed data paths.
4. **Prioritized remediation** — demonstrate how teams identify what to address first.
5. **Governance close** — connect findings to continuous monitoring, reporting, and design-partner value.

## Demo resilience

The launcher performs a clean restart on every run. When a service does not become healthy, it prints container status and recent logs instead of leaving the presenter with a blank browser.

Useful commands:

```bash
docker compose ps
docker compose logs -f
docker compose down
```

## Optional environment settings

```bash
SAASSHADOW_API_URL=http://localhost:8000
SAASSHADOW_UI_URL=http://localhost:3000
SAASSHADOW_DEMO_MODE=true
SAASSHADOW_OPEN_BROWSER=true
SAASSHADOW_WAIT_SECONDS=90
```

Set `SAASSHADOW_OPEN_BROWSER=false` when launching in a headless or remote environment.
