"""
main.py — FastAPI application entrypoint for ToxExplain.

Run with:
    uvicorn api.main:app --reload --port 8000

Then visit:
    http://localhost:8000/docs   — interactive Swagger UI
    http://localhost:8000/redoc  — alternative API docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router


# Create the FastAPI application


app = FastAPI(
    title="ToxExplain API",
    description=(
        "Computational toxicity explainability API. Accepts a SMILES string, "
        "retrieves ProTox-II predictions, curated mechanism data, and "
        "LLM-generated explanations, then returns a combined result."
    ),
    version="0.1.0",
)


# CORS configuration — allows the Vue frontend to call this API

# In production, replace the wildcard with the actual frontend origin,
# e.g. ["http://localhost:5173", "https://toxexplain.example.com"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Accept requests from any origin (dev mode)
    allow_credentials=True,
    allow_methods=["*"],          # Allow all HTTP methods
    allow_headers=["*"],          # Allow all headers
)



# Include the API routes


app.include_router(router)
