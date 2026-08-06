@echo off
rem Start the backend server using the repository virtual environment.
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo Virtual environment Python not found in venv\Scripts\python.exe
    exit /b 1
)
"venv\Scripts\python.exe" -m uvicorn app.server:app --port 8000 --reload
