@echo off
chcp 65001 >nul
title NeoAntigen Studio FULL Launcher
color 0B

:: Relative path
cd /d "%~dp0"

echo.
echo  ======================================================
echo        NeoAntigen Studio - Launcher FULL (Docker)      
echo  ======================================================
echo.

:: 1. Check Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed or not in PATH.
    echo To start the full mode ^(DB, Redis, API, Worker^) you must install Docker Desktop.
    echo Download from: https://www.docker.com/products/docker-desktop/
    echo.
    echo If you just want to test the API in light mode, run: start_neoantigen_studio_light.bat
    pause
    exit /b 1
)

:: 2. Check Docker Compose
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose not found. Make sure it is installed alongside Docker.
    pause
    exit /b 1
)

echo [INFO] Docker and Docker Compose successfully detected.
echo [INFO] Starting background services...
echo.

:: 3. Start stack
docker-compose up -d

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start containers. Check that the Docker daemon is running.
    pause
    exit /b 1
)

echo.
echo [OK] Services started successfully:
echo  - API: http://localhost:8000
echo  - Swagger UI: http://localhost:8000/docs
echo.
echo You can stop the stack at any time by opening a terminal here and typing:
echo docker-compose down
echo.
pause
