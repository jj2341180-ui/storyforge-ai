@echo off
REM Start StoryForge AI on Windows: builds the frontend, then serves API + UI on http://localhost:8000
setlocal
cd /d "%~dp0"

if not exist backend\.venv (
  py -m venv backend\.venv
)
call backend\.venv\Scripts\activate.bat
python -m pip install -q -r backend\requirements.txt

if not exist frontend\node_modules (
  cd frontend && call npm install && cd ..
)
cd frontend && call npm run build && cd ..

cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
endlocal
