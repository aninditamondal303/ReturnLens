@echo off
REM Runs every automated check: backend pytest, frontend unit tests, type-check and production build.
setlocal
cd /d "%~dp0"
set FAILED=

echo.
echo === Backend tests (pytest) ===
pushd backend
if not exist ".venv\Scripts\python.exe" (echo Run setup.bat first. & popd & pause & exit /b 1)
.venv\Scripts\python.exe -m pytest
if errorlevel 1 set FAILED=%FAILED% backend-tests
popd

echo.
echo === Frontend unit tests (Vitest) ===
pushd frontend
call npm test
if errorlevel 1 set FAILED=%FAILED% frontend-tests

echo.
echo === TypeScript type-check and production build ===
call npm run build
if errorlevel 1 set FAILED=%FAILED% frontend-build
popd

echo.
if defined FAILED (
    echo RESULT: FAILED -%FAILED%
    echo Copy the error output above when asking for help.
) else (
    echo RESULT: ALL CHECKS PASSED
)
pause
