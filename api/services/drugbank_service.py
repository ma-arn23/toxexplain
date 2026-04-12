"""
drugbank_service.py — runtime DrugBank text lookup.

Loads the small drugbank_texts.json file (built offline by
build_drugbank_texts.py) and looks up the DrugBank text for a given SMILES.

The runtime API NEVER touches drugbank.xml directly — only this small
pre-extracted JSON.

Lookup tries:
  1. Exact SMILES string match
  2. RDKit canonical SMILES match (if RDKit is installed)

Returns None if no match is found.
"""

import json
from pathlib import Path
from typing import Optional


_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "drugbank_texts.json"

# Cache: load the JSON once at module import time
_records: Optional[list[dict]] = None
_canonical_index: Optional[dict[str, dict]] = None


def _load_records() -> list[dict]:
    global _records
    if _records is None:
        if not _DATA_FILE.exists():
            print(f"[drugbank_service] WARNING: {_DATA_FILE} does not exist")
            _records = []
        else:
            with open(_DATA_FILE, "r") as f:
                _records = json.load(f)
            print(f"[drugbank_service] Loaded {len(_records)} DrugBank records")
    return _records


def _build_canonical_index() -> dict[str, dict]:
    """Build a {canonical_smiles: record} index using RDKit if available."""
    global _canonical_index
    if _canonical_index is not None:
        return _canonical_index

    _canonical_index = {}
    try:
        from rdkit import Chem
        from rdkit import RDLogger
        RDLogger.DisableLog("rdApp.*")  # silence RDKit warnings

        for rec in _load_records():
            smiles = rec.get("smiles", "")
            if not smiles:
                continue
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                canonical = Chem.MolToSmiles(mol)
                _canonical_index[canonical] = rec
    except ImportError:
        print("[drugbank_service] RDKit not installed — canonical SMILES matching disabled")

    return _canonical_index


def _canonicalise(smiles: str) -> Optional[str]:
    """Return RDKit canonical SMILES, or None if RDKit unavailable / parse fails."""
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        return Chem.MolToSmiles(mol)
    except ImportError:
        return None


def lookup_drugbank_text(smiles: str) -> Optional[dict]:
    """
    Look up DrugBank text + metadata for a SMILES string.

    Returns a dict {drug_id, drug_name, smiles, drugbank_text} on match,
    or None if the SMILES is not in the bundled DrugBank set.
    """
    records = _load_records()
    if not records:
        return None

    # 1. Exact match
    for rec in records:
        if rec.get("smiles") == smiles:
            return rec

    # 2. Canonical match via RDKit
    canonical = _canonicalise(smiles)
    if canonical:
        index = _build_canonical_index()
        if canonical in index:
            return index[canonical]

    return None
