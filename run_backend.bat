@echo off
setlocal

call venv\Scripts\activate.bat
uvicorn backend.main:app --reload --port 8000

endlocal
