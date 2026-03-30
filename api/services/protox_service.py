"""
protox_service.py — ProTox-II toxicity prediction service.

This module handles communication with the ProTox-II web server.
Currently returns STUB data so the API is runnable without external
dependencies. Replace the stub logic with real HTTP calls when ready.
"""

from api.models import ProToxPrediction, Endpoints


# ---------------------------------------------------------------------------
# GHS toxicity class labels (for converting class number → human label)
# ---------------------------------------------------------------------------

_CLASS_LABELS = {
    1: "Fatal",
    2: "Fatal",
    3: "Toxic",
    4: "Harmful",
    5: "May be harmful",
    6: "Non-toxic",
}


async def get_protox_prediction(smiles: str) -> ProToxPrediction:
    """
    Get toxicity prediction for a SMILES string from ProTox-II.

    TODO: Replace this stub with a real HTTP call to ProTox-II.
    The real implementation would look something like:

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://tox-new.charite.de/protox_II/api/predict",
                json={"smiles": smiles},
            )
            data = response.json()
            return ProToxPrediction(**data)
    """

    # --- STUB: Hardcoded prediction for development/testing ---
    # Returns plausible values so downstream services have data to work with.
    return ProToxPrediction(
        smiles=smiles,
        ld50=200,
        toxicity_class=3,
        toxicity_class_label=_CLASS_LABELS[3],
        endpoints=Endpoints(
            hepatotoxicity=True,
            nephrotoxicity=False,
            immunotoxicity=False,
            mutagenicity=False,
            cytotoxicity=True,
        ),
    )
