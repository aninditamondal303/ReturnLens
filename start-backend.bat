@echo off
REM Starts the FastAPI backend on http://127.0.0.1:8000 (API docs: /docs)
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
    echo The backend is not set up yet. Run setup.bat first.
    pause
    exit /b 1
)
echo Starting API on http://127.0.0.1:8000  (press Ctrl+C to stop)
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause
