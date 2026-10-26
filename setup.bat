@echo off
REM ============================================================
REM  ShopSphere Return Intelligence Lab - one-time setup (Windows)
REM  Double-click this file, or run it from a terminal.
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo [1/6] Checking Python and Node.js ...
where python >nul 2>nul || (echo   Python was not found. Install Python 3.12 from python.org and tick "Add python.exe to PATH". & goto :fail)
where npm >nul 2>nul || (echo   Node.js was not found. Install Node.js 20 or 22 LTS from nodejs.org. & goto :fail)
python -c "import sys; v=sys.version_info[:2]; print('  Python', '.'.join(map(str, v))); sys.exit(0 if v >= (3, 11) else 1)" || (echo   Python 3.11 or newer is required. & goto :fail)
for /f "delims=" %%v in ('node --version') do echo   Node.js %%v

echo.
echo [2/6] Creating the Python virtual environment (backend\.venv) ...
if not exist "backend\.venv\Scripts\python.exe" (
    python -m venv backend\.venv || goto :fail
) else (
    echo   Already exists - reusing it.
)

echo.
echo [3/6] Installing backend packages ...
backend\.venv\Scripts\python.exe -m pip install --upgrade pip || goto :fail
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt || goto :fail

echo.
echo [4/6] Preparing frontend settings ...
if not exist "frontend\.env" (
    copy "frontend\.env.example" "frontend\.env" >nul
    echo   Created frontend\.env
) else (
    echo   frontend\.env already exists - left unchanged.
)

echo.
echo [5/6] Installing frontend packages (this can take a few minutes) ...
pushd frontend
call npm install
if errorlevel 1 (popd & goto :fail)
popd

echo.
echo [6/6] Checking the dataset ...
if not exist "data\orders.csv" (
    backend\.venv\Scripts\python.exe scripts\generate_data.py || goto :fail
) else (
    echo   data\*.csv present.
)

echo.
echo ============================================================
echo  Setup complete. Next: double-click start-all.bat
echo ============================================================
pause
exit /b 0

:fail
echo.
echo ************************************************************
echo  Setup stopped because of the error above.
echo  See README.md, section "Troubleshooting".
echo ************************************************************
pause
exit /b 1
