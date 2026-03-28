@echo off
chcp 65001 >nul
title NeoAntigen Studio Launcher v0.1.0
color 0A

:: Relative path
cd /d "%~dp0"

echo.
echo  ======================================================
echo        NeoAntigen Studio v0.1.0        
echo        Launcher LIGHT (API Only)       
echo  ======================================================
echo.
echo [WARNING] This script only starts the local API. For full pipelines use start_neoantigen_studio_full.bat or Docker.
echo.

:: 1. Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.11+.
    echo Download from https://python.org
    pause
    exit /b 1
)

:: 2. Create/Verify venv
if not exist "venv\Scripts\python.exe" (
    echo [INFO] Creating venv...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
)

:: 3. Install dependencies (idempotent)
call venv\Scripts\activate.bat
echo [INFO] Installing/updating dependencies...
pip install --upgrade pip
pip install -e . --quiet
if errorlevel 1 (
    echo [ERROR] Installation failed. Check pyproject.toml / requirements.
    pause
    exit /b 1
)

:: 4. Check port 8000
netstat -an ^| find "8000" >nul
if not errorlevel 1 (
    echo [WARNING] Port 8000 occupied. Trying 8001...
    set PORT=8001
) else (
    set PORT=8000
)

:: 5. Start server with logs
echo [OK] Starting at http://localhost:%PORT% ...
echo [OK] Log saved to neoantigen_server.log
echo [OK] Press CTRL+C to gracefully stop.
echo.

start /B cmd /C "uvicorn services.api.main:app --host 0.0.0.0 --port %PORT% --reload --log-level info > neoantigen_server.log 2>&1"

:: 6. Graceful Monitor
:monitor
timeout /t 2 /nobreak >nul
tasklist /FI "IMAGENAME eq python.exe" /FO CSV ^| find /I "uvicorn" >nul
if errorlevel 1 (
    echo [INFO] Server stopped.
    goto :end
)
goto :monitor

:end
echo.
echo [INFO] Server terminated. Log: neoantigen_server.log (%PORT%)
pause