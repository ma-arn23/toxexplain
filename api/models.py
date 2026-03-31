"""
models.py — Pydantic v2 data models for ToxExplain.

Two sets of models:
  1. Internal models (used by the pipeline services)
  2. Response models (camelCase JSON matching the frontend's ResultsPageData interface)
"""

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from typing import Literal, Optional



# INTERNAL MODELS — used inside the pipeline, not returned to frontend


class QueryInput(BaseModel):
    """The SMILES string submitted by the user via the frontend."""
    smiles: str = Field(
        ...,
        description="A valid SMILES string representing the query compound",
        examples=["CC(=O)Oc1ccccc1C(=O)O"],
    )


class Endpoints(BaseModel):
    """Binary flags for each toxicity endpoint returned by ProTox-II."""
    hepatotoxicity: bool = False
    nephrotoxicity: bool = False
    immunotoxicity: bool = False
    mutagenicity: bool = False
    cytotoxicity: bool = False


class ProToxPrediction(BaseModel):
    """Toxicity prediction from the ProTox-II web server."""
    smiles: str
    ld50: int = Field(..., description="Predicted LD50 in mg/kg")
    toxicity_class: int = Field(..., ge=1, le=6)
    toxicity_class_label: str
    endpoints: Endpoints = Field(default_factory=Endpoints)


class MechanismRecord(BaseModel):
    """One curated mechanism record from withdrawn-drug data."""
    drug_name: str
    smiles: str
    primary_targets: list[str] = Field(default_factory=list)
    off_targets: list[str] = Field(default_factory=list)
    pathways: list[str] = Field(default_factory=list)
    organ_systems: list[str] = Field(default_factory=list)
    withdrawal_reason: str = ""
    source: str = ""
    references: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    """A single piece of supporting evidence."""
    label: str
    source: str
    origin: str
    group: str
    confidence: str


# RESPONSE MODELS — camelCase JSON matching frontend's ResultsPageData

# These mirror src/app/types/explainability.ts in the frontend repo exactly.

class _CamelModel(BaseModel):
    """Base model that serializes field names to camelCase."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class EndpointRisk(_CamelModel):
    """One toxicity endpoint with a 0–1 score and risk level."""
    name: str
    score: float = Field(..., ge=0, le=1)
    risk: Literal["high", "moderate", "low"]


class MechanisticRisk(_CamelModel):
    """Rich risk factor shown in the 'Why might this be toxic?' card."""
    id: str
    type: str
    severity: Literal["high", "moderate", "low"]
    description: str
    confidence: float = Field(..., ge=0, le=1)
    triggered_by: list[str]
    support_status: Literal["strong", "moderate", "emerging"]
    related_targets: list[str] = Field(default_factory=list)
    related_off_targets: list[str] = Field(default_factory=list)
    related_mechanisms: list[str] = Field(default_factory=list)
    related_pathways: list[str] = Field(default_factory=list)


class TargetRecord(_CamelModel):
    """A molecular target (primary or off-target)."""
    name: str
    interaction: str
    confidence: float = Field(..., ge=0, le=1)
    provenance: Literal["curated", "database", "llm"]


class TextEvidenceRecord(_CamelModel):
    """A mechanism or pathway entry with provenance."""
    text: str
    provenance: Literal["curated", "database", "llm"]


class AdverseEventRecord(_CamelModel):
    """A known adverse event from clinical/literature data."""
    event: str
    frequency: str
    evidence: str
    provenance: Literal["curated", "database", "llm"]


class ConfidenceMetrics(_CamelModel):
    """Overall confidence scores for the prediction."""
    model_confidence: float = Field(..., ge=0, le=1)
    mechanistic_support: float = Field(..., ge=0, le=1)
    evidence_strength: float = Field(..., ge=0, le=1)


class ResultsPageData(_CamelModel):
    """
    Top-level response object matching the frontend's ResultsPageData interface.
    This is what GET /api/results returns.
    """
    smiles: str
    toxicity_class: str
    overall_score: float = Field(..., ge=0, le=1)
    endpoints: list[EndpointRisk]
    mechanistic_risks: list[MechanisticRisk]
    primary_targets: list[TargetRecord]
    off_targets: list[TargetRecord]
    mechanisms: list[TextEvidenceRecord]
    pathways: list[TextEvidenceRecord]
    adverse_events: list[AdverseEventRecord]
    confidence: ConfidenceMetrics
