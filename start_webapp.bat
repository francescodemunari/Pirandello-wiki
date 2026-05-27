@echo off
cd /d "%~dp0webapp"
echo Installing dependencies...
call npm install >nul 2>&1
echo Starting Pirandello Webapp...
echo Open: http://localhost:5173
npm run dev
pause
