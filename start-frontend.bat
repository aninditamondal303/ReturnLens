@echo off
REM Starts the React frontend on http://127.0.0.1:5173
cd /d "%~dp0frontend"
if not exist "node_modules" (
    echo Frontend packages are not installed yet. Run setup.bat first.
    pause
    exit /b 1
)
if not exist ".env" copy ".env.example" ".env" >nul
echo Starting web app on http://127.0.0.1:5173  (press Ctrl+C to stop)
call npm run dev
pause
