@echo off
setlocal EnableDelayedExpansion
title CPE-Forge Launcher

echo ============================================
echo   CPE-Forge - AIGC Talent Analytics Platform
echo ============================================
echo.

:: Project root = script directory
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

:: ============================================
:: 1. Python venv
:: ============================================
echo [1/6] Python venv...
if exist ".venv\Scripts\activate.bat" goto :venv_ok
echo       Creating venv...
python -m venv .venv
if errorlevel 1 (
    echo [ERROR] Failed to create venv. Install Python 3.10+
    pause
    exit /b 1
)
echo       venv created
goto :venv_activate
:venv_ok
echo       OK
:venv_activate
call .venv\Scripts\activate.bat

:: ============================================
:: 2. Python dependencies
:: ============================================
echo [2/6] Python dependencies...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERROR] pip install failed
    pause
    exit /b 1
)
echo       OK

:: ============================================
:: 3. Model config init
:: ============================================
echo [3/6] Model config init...
python -c "from pipeline.llm_config import init_default_configs; init_default_configs()"
echo       OK

:: ============================================
:: 4. Frontend dependencies
:: ============================================
echo [4/6] Frontend dependencies...
set "SKIP_FRONTEND=0"
where npm >nul 2>nul
if errorlevel 1 goto :no_npm
if exist "web\frontend\node_modules" goto :npm_ok
echo       Running npm install...
cd web\frontend
call npm install
if errorlevel 1 (
    echo [ERROR] npm install failed
    pause
    exit /b 1
)
cd ..\..
echo       OK
goto :npm_done
:no_npm
echo.
echo [WARN] Node.js / npm not found! Frontend will not start.
echo        Download Node.js 18+ from: https://nodejs.org/
echo        Backend-only mode will be used.
echo.
set "SKIP_FRONTEND=1"
goto :npm_done
:npm_ok
echo       OK
:npm_done

:: Create required directories
if not exist "attachments" mkdir attachments
if not exist "output" mkdir output

:: ============================================
:: 5. Data pipeline
:: ============================================
echo [5/6] Data pipeline...
if exist "output\cleaning_report.json" goto :pipeline_skip
if exist "emails" goto :pipeline_eml
if exist "attachments" goto :pipeline_att
echo       No emails/ or attachments/ found, skipping
goto :pipeline_done
:pipeline_eml
echo       Running pipeline with EML extraction...
.venv\Scripts\python.exe scripts/run_pipeline.py --input attachments --output output --report --emails emails
goto :pipeline_done
:pipeline_att
echo       Running pipeline...
.venv\Scripts\python.exe scripts/run_pipeline.py --input attachments --output output --report
goto :pipeline_done
:pipeline_skip
echo       Cleaning report exists, skipping
:pipeline_done
echo       OK

:: ============================================
:: 6. Start services
:: ============================================
echo [6/6] Starting services...

:: Start Flask backend in background
echo       Starting backend (Flask :5000)...
start "CPE-Forge Backend" cmd /c "cd /d %PROJECT_DIR% && .venv\Scripts\python.exe -m web.app"

:: Wait for backend to be ready
echo       Waiting for backend (first start may take a few minutes)...
set "BACKEND_READY=0"
for /L %%i in (1,1,60) do (
    if "!BACKEND_READY!"=="0" (
        timeout /t 5 /nobreak >nul
        .venv\Scripts\python.exe -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/employees')" >nul 2>nul
        if not errorlevel 1 (
            set "BACKEND_READY=1"
        )
    )
)
if "!BACKEND_READY!"=="1" (
    echo       Backend is ready!
) else (
    echo       [WARN] Backend not ready after 5 min, continuing anyway...
)

:: Start frontend
if "!SKIP_FRONTEND!"=="1" goto :no_frontend
echo       Starting frontend (Vite :5173)...
start "CPE-Forge Frontend" cmd /c "cd /d %PROJECT_DIR%\web\frontend && npm run dev"
timeout /t 3 /nobreak >nul
echo.
echo ============================================
echo   All services started!
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:5000
echo ============================================
start http://localhost:5173
goto :show_tips
:no_frontend
echo.
echo ============================================
echo   Backend started! (No frontend - Node.js missing)
echo   Backend: http://localhost:5000/api/employees
echo   Install Node.js 18+ and re-run to enable Web UI
echo ============================================

:show_tips
echo.
echo   Getting started:
echo   1. Put weekly report EML files in emails/ folder
echo   2. Or put Excel files directly in attachments/ folder
echo   3. Set API Key on the Settings page
echo ============================================

echo.
echo Press any key to close this window (services keep running)
pause >nul
