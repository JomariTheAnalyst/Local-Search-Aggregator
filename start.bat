@echo off
echo Starting AI Search Assistant...

echo Starting backend server...
start cmd /k "cd backend && python run.py"

echo Waiting for backend to initialize...
timeout /t 5

echo Starting frontend server...
start cmd /k "cd frontend && npm start"

echo.
echo AI Search Assistant is starting!
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Press any key to exit this window (servers will continue running)
pause > nul 