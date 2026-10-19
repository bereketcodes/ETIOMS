@echo off
title ETIOMS Launcher
echo ====================================================================
echo   Starting ETIOMS (Ethiopian Tender Intelligence System)
echo ====================================================================
echo.
echo [1/2] Starting Backend (FastAPI on http://127.0.0.1:8000)...
start "ETIOMS Backend" cmd /k ".\venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000"

echo [2/2] Starting Frontend (Next.js on http://localhost:3000)...
start "ETIOMS Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ====================================================================
echo   Both services launched in separate windows!
echo   Open your browser at: http://localhost:3000
echo   API Documentation:   http://127.0.0.1:8000/docs
echo   Demo Login:          admin@afrotech.et / DemoPassword123!
echo ====================================================================
echo.
pause
