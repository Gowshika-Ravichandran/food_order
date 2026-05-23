# Start FastAPI Backend in a new window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "venv\Scripts\activate; uvicorn backend.main:app --reload --port 8000"

# Start React Frontend in the current window
cd frontend
npm start