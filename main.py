"""Triplan — Agentic AI Trip Planner.

Start the API server:
    python main.py

Or with uvicorn directly:
    uvicorn main:app --reload
"""

import uvicorn

from src.api.app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
