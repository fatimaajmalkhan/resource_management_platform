@echo off
rem Start both the backend and frontend in development mode.
cd /d "%~dp0"

echo [1/2] Starting backend on port 8000...
start "Backend Server" cmd /c "venv\Scripts\python.exe -m uvicorn app.server:app --port 8000 --reload || pause"

echo [2/2] Starting frontend on port 5173...
if not exist "frontend\node_modules" (
    echo node_modules not found in frontend. Running npm install...
    cd frontend && call npm install && cd ..
)
start "Frontend Dev Server" cmd /c "cd frontend && npm run dev || pause"

echo Setup complete! 
echo Frontend dev server running: http://localhost:5173
echo Backend API server running: http://localhost:8000
