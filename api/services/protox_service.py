"""
protox_service.py — ProTox toxicity prediction service.

This module:
1. Sends a SMILES string to ProTox
2. Parses the response into the internal ProToxPrediction model
3. Falls back to stub mode if enabled
"""

from __future__ import annotations

import csv
import io
import os
import json
from typing import Any

import httpx

from api.models import ProToxPrediction, Endpoints


_CLASS_LABELS = {
    1: "Fatal",
    2: "Fatal",
    3: "Toxic",
    4: "Harmful",
    5: "May Be Harmful",
    6: "Non-toxic",
}

PROTOX_BASE_URL = os.getenv("PROTOX_BASE_URL", "https://tox.charite.de")
PROTOX_PREDICT_PATH = os.getenv("PROTOX_PREDICT_PATH", "/protox3/api/predict")
PROTOX_TIMEOUT_SECONDS = float(os.getenv("PROTOX_TIMEOUT_SECONDS", "60"))
PROTOX_USE_STUB = os.getenv("PROTOX_USE_STUB", "false").lower() == "true"


def _build_stub(smiles: str) -> ProToxPrediction:
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


def _first_present(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {
            "true",
            "1",
            "yes",
            "y",
            "positive",
            "active",
            "toxic",
        }
    return False


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _extract_endpoint(data: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        if key in data:
            return _to_bool(data[key])

    nested = data.get("endpoints")
    if isinstance(nested, dict):
        for key in keys:
            if key in nested:
                return _to_bool(nested[key])

    return False


def _parse_json_response(smiles: str, data: dict[str, Any]) -> ProToxPrediction:
    toxicity_class = _safe_int(
        _first_present(data, "toxicity_class", "class", "tox_class"),
        default=6,
    )
    ld50 = _safe_int(
        _first_present(data, "ld50", "LD50", "predicted_ld50", "oral_ld50"),
        default=0,
    )

    return ProToxPrediction(
        smiles=smiles,
        ld50=ld50,
        toxicity_class=toxicity_class,
        toxicity_class_label=_CLASS_LABELS.get(toxicity_class, "Unknown"),
        endpoints=Endpoints(
            hepatotoxicity=_extract_endpoint(data, "hepatotoxicity", "hepatotox"),
            nephrotoxicity=_extract_endpoint(data, "nephrotoxicity", "nephrotox"),
            immunotoxicity=_extract_endpoint(data, "immunotoxicity", "immunotox"),
            mutagenicity=_extract_endpoint(data, "mutagenicity", "ames_mutagenicity"),
            cytotoxicity=_extract_endpoint(data, "cytotoxicity", "cytotox"),
        ),
    )


def _parse_csv_response(smiles: str, raw_csv: str) -> ProToxPrediction:
    reader = csv.DictReader(io.StringIO(raw_csv))
    rows = list(reader)

    if not rows:
        raise ValueError("CSV response from ProTox was empty")

    row = rows[0]

    toxicity_class = _safe_int(
        _first_present(row, "toxicity_class", "class", "tox_class"),
        default=6,
    )
    ld50 = _safe_int(
        _first_present(row, "ld50", "LD50", "predicted_ld50", "oral_ld50"),
        default=0,
    )

    return ProToxPrediction(
        smiles=smiles,
        ld50=ld50,
        toxicity_class=toxicity_class,
        toxicity_class_label=_CLASS_LABELS.get(toxicity_class, "Unknown"),
        endpoints=Endpoints(
            hepatotoxicity=_extract_endpoint(row, "hepatotoxicity", "hepatotox"),
            nephrotoxicity=_extract_endpoint(row, "nephrotoxicity", "nephrotox"),
            immunotoxicity=_extract_endpoint(row, "immunotoxicity", "immunotox"),
            mutagenicity=_extract_endpoint(row, "mutagenicity", "ames_mutagenicity"),
            cytotoxicity=_extract_endpoint(row, "cytotoxicity", "cytotox"),
        ),
    )


def _build_payload(smiles: str) -> dict[str, Any]:
    """
    Update this if the real ProTox request body differs.
    """
    return {
        "smiles": smiles,
        "models": "ALL_MODELS",
    }


async def _fetch_protox_raw(smiles: str) -> tuple[str, str]:
    url = f"{PROTOX_BASE_URL.rstrip('/')}/{PROTOX_PREDICT_PATH.lstrip('/')}"
    payload = _build_payload(smiles)

    headers = {
        "Accept": "application/json, text/csv, */*",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(
        timeout=PROTOX_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.headers.get("content-type", "").lower(), response.text


async def get_protox_prediction(smiles: str) -> ProToxPrediction:
    if PROTOX_USE_STUB:
        return _build_stub(smiles)

    try:
        content_type, raw_text = await _fetch_protox_raw(smiles)

        if "json" in content_type:
            data = httpx.Response(200, text=raw_text).json()
            return _parse_json_response(smiles, data)

        if "csv" in content_type:
            return _parse_csv_response(smiles, raw_text)

        # Fallback: try JSON first, then CSV
        try:
            data = httpx.Response(200, text=raw_text).json()
            return _parse_json_response(smiles, data)
        except json.JSONDecodeError:
            return _parse_csv_response(smiles, raw_text)

    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"ProTox returned HTTP {e.response.status_code}") from e
    except httpx.RequestError as e:
        raise RuntimeError("Could not reach ProTox service") from e
    except Exception as e:
        raise RuntimeError(f"Failed to process ProTox response: {e}") from e