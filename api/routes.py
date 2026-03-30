"""
routes.py — API route definitions for ToxExplain.

Endpoints:
  GET  /api/health           — health check
  GET  /api/results?smiles=  — frontend-facing endpoint (returns ResultsPageData)
"""

from fastapi import APIRouter, HTTPException, Query
from api.models import QueryInput, ResultsPageData
from api.services.orchestrator import build_results_page_data


# Create a router with the /api prefix
router = APIRouter(prefix="/api", tags=["ToxExplain"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@router.get("/health")
async def health_check():
    """Simple health check so the frontend can verify the API is running."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Frontend-facing results endpoint
# ---------------------------------------------------------------------------

@router.get("/results", response_model=ResultsPageData)
async def get_results(
    smiles: str = Query(
        ...,
        description="SMILES string to analyze",
        examples=["CC(=O)Oc1ccccc1C(=O)O"],
    ),
):
    """
    Return a full explainability result for the given SMILES string.

    This endpoint matches the frontend's expected data shape (ResultsPageData).
    The frontend navigates to /results?smiles=<encoded_smiles> and fetches
    this endpoint to populate the results page.

    Response uses camelCase field names to match TypeScript conventions.
    """
    if not smiles.strip():
        raise HTTPException(status_code=400, detail="SMILES string cannot be empty")

    try:
        result = await build_results_page_data(smiles)
        # Serialize with camelCase aliases for the frontend
        return result.model_dump(by_alias=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
