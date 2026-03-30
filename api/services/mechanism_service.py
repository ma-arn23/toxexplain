"""
mechanism_service.py — Local mechanism data lookup.

Loads curated mechanism records from api/data/mechanism_records.json
and filters them by SMILES match. In the real system, this could also
do substructure matching or fuzzy lookup.
"""

import json
from pathlib import Path
from api.models import MechanismRecord, EvidenceItem


# ---------------------------------------------------------------------------
# Load the mechanism records once at module import time
# ---------------------------------------------------------------------------

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "mechanism_records.json"


def _load_mechanism_data() -> list[dict]:
    """Read the JSON file and return raw records."""
    with open(_DATA_FILE, "r") as f:
        return json.load(f)


async def lookup_mechanisms(
    smiles: str,
) -> tuple[list[MechanismRecord], list[EvidenceItem]]:
    """
    Look up curated mechanism records that match the given SMILES string.

    Currently does exact SMILES match. In the future you could:
    - Use RDKit canonical SMILES for normalised comparison
    - Do substructure search with RDKit
    - Fall back to returning ALL records if no exact match (useful for demos)

    Returns:
        A tuple of (mechanism_records, evidence_items) extracted from the data.
    """
    raw_data = _load_mechanism_data()

    mechanism_records: list[MechanismRecord] = []
    evidence_items: list[EvidenceItem] = []

    for entry in raw_data:
        # --- Exact SMILES match ---
        # For development/demo: if no exact match is found, we fall back to
        # returning ALL records so there is always something to display.
        if entry.get("smiles") == smiles:
            # Extract evidence items (stored inline in the JSON)
            raw_evidence = entry.pop("evidence_items", [])

            mechanism_records.append(MechanismRecord(**entry))
            evidence_items.extend(
                EvidenceItem(**ev) for ev in raw_evidence
            )

    # --- Fallback: if no exact match, return all records for demo purposes ---
    if not mechanism_records:
        raw_data = _load_mechanism_data()  # reload because we popped above
        for entry in raw_data:
            raw_evidence = entry.pop("evidence_items", [])
            mechanism_records.append(MechanismRecord(**entry))
            evidence_items.extend(
                EvidenceItem(**ev) for ev in raw_evidence
            )

    return mechanism_records, evidence_items
