#!/bin/bash
# Start FastAPI in background
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000 &

# Start React
cd frontend && npm start