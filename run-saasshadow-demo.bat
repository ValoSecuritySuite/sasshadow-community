@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

title SaaSShadow Black Hat Demo Launcher
color 0D

echo.
echo  ===============================================================
echo   SaaSShadow - Black Hat Power Demo Launcher
echo   Discover. Inventory. Govern.
echo  ===============================================================
echo.

where docker >nul 2>nul
if errorlevel 1 goto :docker_missing

docker info >nul 2>nul
if errorlevel 1 goto :docker_not_running

docker compose version >nul 2>nul
if errorlevel 1 goto :compose_missing

if exist .env.example if not exist .env (
  copy /Y .env.example .env >nul
  echo  [OK] Created .env from .env.example
)

set SAASSHADOW_DEMO_MODE=true
set APP_EDITION=community
set APP_LOG_LEVEL=INFO
set API_URL=http://localhost:8000
set UI_URL=http://localhost:3000

echo  [1/4] Resetting previous containers...
docker compose down --remove-orphans >nul 2>nul

echo  [2/4] Building and launching SaaSShadow...
docker compose up --build -d
if errorlevel 1 goto :launch_failed

echo  [3/4] Waiting for the API...
set /a attempts=0
:wait_api
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri '%API_URL%/health' -TimeoutSec 3 ^| Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 goto :api_ready
set /a attempts+=1
if !attempts! GEQ 45 goto :health_failed
timeout /t 2 /nobreak >nul
goto :wait_api

:api_ready
echo  [OK] API is healthy.
echo  [4/4] Waiting for the dashboard...
set /a attempts=0
:wait_ui
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri '%UI_URL%/' -TimeoutSec 3 ^| Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
if not errorlevel 1 goto :ready
set /a attempts+=1
if !attempts! GEQ 45 goto :health_failed
timeout /t 2 /nobreak >nul
goto :wait_ui

:ready
echo.
echo  ===============================================================
echo   SaaSShadow is BLACK HAT DEMO-READY
 echo  ===============================================================
echo.
echo   Dashboard:  %UI_URL%
echo   API Docs:   %API_URL%/docs
echo   Health:     %API_URL%/health
echo.
echo   Presenter flow:
echo     1. Executive risk overview
 echo     2. SaaS and AI application discovery
 echo     3. OAuth permissions and risky access
 echo     4. Prioritized remediation
 echo     5. Governance, reporting, and design-partner value
 echo.
echo   Stop: docker compose down
 echo   Logs: docker compose logs -f
 echo.
start "SaaSShadow" "%UI_URL%"
pause
exit /b 0

:docker_missing
echo  ERROR: Docker was not found. Install Docker Desktop first.
goto :error

:docker_not_running
echo  ERROR: Docker Desktop is installed but not running.
goto :error

:compose_missing
echo  ERROR: Docker Compose v2 is required.
goto :error

:launch_failed
echo  ERROR: SaaSShadow failed to build or launch.
docker compose logs --tail=80
goto :error

:health_failed
echo  ERROR: The SaaSShadow services did not become healthy in time.
docker compose ps
docker compose logs --tail=80
goto :error

:error
echo.
pause
exit /b 1
