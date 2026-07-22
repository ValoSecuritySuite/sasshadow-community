#!/usr/bin/env bash
# Black Hat-ready launcher for SaaSShadow Community Edition.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

API_URL="${SAASSHADOW_API_URL:-http://localhost:8000}"
UI_URL="${SAASSHADOW_UI_URL:-http://localhost:3000}"
DEMO_MODE="${SAASSHADOW_DEMO_MODE:-true}"
OPEN_BROWSER="${SAASSHADOW_OPEN_BROWSER:-true}"
WAIT_SECONDS="${SAASSHADOW_WAIT_SECONDS:-90}"

PURPLE='\033[0;35m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

banner() {
  printf "\n${PURPLE}${BOLD}"
  cat <<'EOF'
   _____             _____  _____ _               _
  / ____|           / ____|/ ____| |             | |
 | (___   __ _  __ _| (___ | (___ | |__   __ _  __| | _____      __
  \___ \ / _` |/ _` |\___ \ \___ \| '_ \ / _` |/ _` |/ _ \ \ /\ / /
  ____) | (_| | (_| |____) |____) | | | | (_| | (_| | (_) \ V  V /
 |_____/ \__,_|\__,_|_____/|_____/|_| |_|\__,_|\__,_|\___/ \_/\_/
EOF
  printf "${RESET}${CYAN}Black Hat Power Demo Launcher — Discover. Inventory. Govern.${RESET}\n\n"
}

fail() {
  printf "${RED}${BOLD}ERROR:${RESET} %s\n" "$1" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command '$1' was not found."
}

open_url() {
  local url="$1"
  if [[ "$OPEN_BROWSER" != "true" ]]; then
    return 0
  fi
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$url" >/dev/null 2>&1 || true
  elif command -v cmd.exe >/dev/null 2>&1; then
    cmd.exe /c start "" "$url" >/dev/null 2>&1 || true
  fi
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local deadline=$((SECONDS + WAIT_SECONDS))
  printf "${YELLOW}Waiting for %s...${RESET}\n" "$name"
  until curl -fsS "$url" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      printf "${RED}%s did not become ready at %s within %ss.${RESET}\n" "$name" "$url" "$WAIT_SECONDS"
      docker compose ps || true
      docker compose logs --tail=80 || true
      exit 1
    fi
    sleep 2
  done
  printf "${GREEN}✓ %s ready${RESET}\n" "$name"
}

preflight() {
  require_cmd docker
  require_cmd curl

  docker info >/dev/null 2>&1 || fail "Docker is installed but not running. Start Docker Desktop and try again."
  docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required."

  if [[ -f .env.example && ! -f .env ]]; then
    cp .env.example .env
    printf "${GREEN}✓ Created .env from .env.example${RESET}\n"
  fi

  if [[ "$DEMO_MODE" == "true" ]]; then
    export APP_EDITION="community"
    export APP_LOG_LEVEL="INFO"
    export SAASSHADOW_DEMO_MODE="true"
  fi
}

launch() {
  printf "${CYAN}Resetting any previous demo containers...${RESET}\n"
  docker compose down --remove-orphans >/dev/null 2>&1 || true

  printf "${CYAN}Building and launching SaaSShadow...${RESET}\n"
  docker compose up --build -d

  wait_for_url "API health" "${API_URL}/health"
  wait_for_url "Dashboard" "${UI_URL}/"
}

status_card() {
  printf "\n${GREEN}${BOLD}SaaSShadow is Black Hat demo-ready.${RESET}\n\n"
  printf "  ${BOLD}Dashboard:${RESET}      %s\n" "$UI_URL"
  printf "  ${BOLD}API Docs:${RESET}       %s/docs\n" "$API_URL"
  printf "  ${BOLD}Health:${RESET}         %s/health\n" "$API_URL"
  printf "  ${BOLD}Demo mode:${RESET}      %s\n" "$DEMO_MODE"
  printf "\n${PURPLE}${BOLD}Suggested presenter flow${RESET}\n"
  printf "  1. Show the executive risk overview\n"
  printf "  2. Reveal discovered SaaS and AI applications\n"
  printf "  3. Drill into OAuth permissions and risky access\n"
  printf "  4. Demonstrate prioritized remediation\n"
  printf "  5. Close on governance, reporting, and design-partner value\n"
  printf "\n${CYAN}Useful commands${RESET}\n"
  printf "  Logs:   docker compose logs -f\n"
  printf "  Status: docker compose ps\n"
  printf "  Stop:   docker compose down\n"
  printf "  Reset:  ./run-saasshadow-demo.sh\n\n"
}

banner
preflight
launch
status_card
open_url "$UI_URL"
