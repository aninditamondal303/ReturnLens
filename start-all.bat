@echo off
REM Opens the backend and frontend in two windows, then opens the browser.
cd /d "%~dp0"
start "ShopSphere API (port 8000)" cmd /k call "%~dp0start-backend.bat"
start "ShopSphere Web (port 5173)" cmd /k call "%~dp0start-frontend.bat"
echo Waiting for both servers to start ...
timeout /t 10 /nobreak >nul
start "" http://127.0.0.1:5173
echo The app should now be open in your browser.
echo Close the two server windows (or press Ctrl+C in them) to stop.
timeout /t 5 >nul
