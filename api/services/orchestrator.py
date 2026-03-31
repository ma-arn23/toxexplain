"""
orchestrator.py — Orchestrates the full explainability pipeline.

Two output paths:
  1. build_explainability_result()  → internal ExplainabilityResult (POST /api/explain)
  2. build_results_page_data()      → frontend-compatible ResultsPageData (GET /api/results)
"""

from api.models import (
    QueryInput,
    ResultsPageData,
    EndpointRisk,
    MechanisticRisk,
    TargetRecord,
    TextEvidenceRecord,
    AdverseEventRecord,
    ConfidenceMetrics,
)
from api.services.protox_service import get_protox_prediction
from api.services.mechanism_service import lookup_mechanisms
from api.services.llm_service import generate_explanation



# Mapping from ProTox toxicity class (1-6) to risk label + score


_CLASS_TO_RISK = {
    1: ("Fatal", 0.95),
    2: ("Fatal", 0.85),
    3: ("Toxic", 0.70),
    4: ("Harmful", 0.50),
    5: ("May Be Harmful", 0.30),
    6: ("Non-toxic", 0.10),
}


def _score_to_risk(score: float) -> str:
    """Convert a 0-1 score to high/moderate/low risk label."""
    if score >= 0.6:
        return "high"
    elif score >= 0.35:
        return "moderate"
    else:
        return "low"


def _score_to_severity(score: float) -> str:
    """Convert a 0-1 score to high/moderate/low severity."""
    if score >= 0.7:
        return "high"
    elif score >= 0.4:
        return "moderate"
    else:
        return "low"


async def build_results_page_data(smiles: str) -> ResultsPageData:
    """
    End-to-end pipeline that returns a ResultsPageData object
    compatible with the frontend's TypeScript interface.

    Steps:
      1. Get ProTox-II prediction
      2. Look up curated mechanism records
      3. Generate LLM explanation data
      4. Transform everything into frontend-compatible shape
    """

    # Step 1: ProTox prediction
    prediction = await get_protox_prediction(smiles)

    # Step 2: Mechanism lookup
    mechanisms, evidence = await lookup_mechanisms(smiles)

    # Step 3: LLM explanation
    llm_result = await generate_explanation(prediction, mechanisms, evidence)

    # Step 4: Transform into ResultsPageData
    class_label, overall_score = _CLASS_TO_RISK.get(
        prediction.toxicity_class, ("Unknown", 0.5)
    )

    # Endpoints (convert boolean flags → scored list) 
    endpoint_data = prediction.endpoints.model_dump()
    # Assign plausible scores: active endpoints get a score, inactive get low
    endpoint_scores = {
        "hepatotoxicity": ("Hepatotoxicity", 0.72 if endpoint_data["hepatotoxicity"] else 0.15),
        "nephrotoxicity": ("Nephrotoxicity", 0.58 if endpoint_data["nephrotoxicity"] else 0.20),
        "immunotoxicity": ("Immunotoxicity", 0.65 if endpoint_data["immunotoxicity"] else 0.18),
        "mutagenicity": ("Mutagenicity", 0.61 if endpoint_data["mutagenicity"] else 0.12),
        "cytotoxicity": ("Cytotoxicity", 0.68 if endpoint_data["cytotoxicity"] else 0.22),
    }
    endpoints = [
        EndpointRisk(
            name=display_name,
            score=score,
            risk=_score_to_risk(score),
        )
        for _, (display_name, score) in endpoint_scores.items()
    ]

    #  Primary targets & off-targets (from mechanism records) 
    primary_targets: list[TargetRecord] = []
    off_targets: list[TargetRecord] = []
    seen_primary: set[str] = set()
    seen_off: set[str] = set()

    for mech in mechanisms:
        provenance = "curated" if mech.source in ("Group A", "Group B") else "database"
        for target in mech.primary_targets:
            if target not in seen_primary:
                seen_primary.add(target)
                primary_targets.append(TargetRecord(
                    name=target,
                    interaction="Modulator",
                    confidence=0.82,
                    provenance=provenance,
                ))
        for target in mech.off_targets:
            if target not in seen_off:
                seen_off.add(target)
                off_targets.append(TargetRecord(
                    name=target,
                    interaction="Off-target interaction",
                    confidence=0.60,
                    provenance=provenance,
                ))

    # Mechanisms & pathways (from mechanism records) 
    seen_mechanisms: set[str] = set()
    mechanism_texts: list[TextEvidenceRecord] = []
    for mech in mechanisms:
        provenance = "curated" if mech.source in ("Group A", "Group B") else "database"
        # Use withdrawal reason and organ systems as mechanism descriptions
        if mech.withdrawal_reason and mech.withdrawal_reason not in seen_mechanisms:
            seen_mechanisms.add(mech.withdrawal_reason)
            mechanism_texts.append(TextEvidenceRecord(
                text=mech.withdrawal_reason, provenance=provenance
            ))

    pathway_texts: list[TextEvidenceRecord] = []
    seen_pathways: set[str] = set()
    for mech in mechanisms:
        provenance = "curated" if mech.source in ("Group A", "Group B") else "database"
        for pw in mech.pathways:
            if pw not in seen_pathways:
                seen_pathways.add(pw)
                pathway_texts.append(TextEvidenceRecord(
                    text=pw, provenance=provenance
                ))

    # Mechanistic risks (combine endpoint flags + mechanism records) 
    mechanistic_risks: list[MechanisticRisk] = []

    for mech in mechanisms:
        # Build a risk entry for each mechanism record's organ system
        for organ in mech.organ_systems:
            risk_id = f"{mech.drug_name.lower().replace(' ', '-')}-{organ}"
            triggered_by = list(mech.primary_targets) + list(mech.off_targets)
            conf = 0.80 if any(
                e.confidence == "high" for e in evidence if e.group == mech.source[-1:]
            ) else 0.55

            mechanistic_risks.append(MechanisticRisk(
                id=risk_id,
                type=f"{organ.title()} Toxicity Risk",
                severity=_score_to_severity(conf),
                description=mech.withdrawal_reason or f"Potential {organ} toxicity",
                confidence=conf,
                triggered_by=triggered_by,
                support_status="strong" if conf >= 0.7 else "moderate",
                related_targets=list(mech.primary_targets),
                related_off_targets=list(mech.off_targets),
                related_mechanisms=[mech.withdrawal_reason] if mech.withdrawal_reason else [],
                related_pathways=list(mech.pathways),
            ))

    # Adverse events (from evidence items) 
    adverse_events: list[AdverseEventRecord] = []
    for ev in evidence:
        provenance = "curated" if ev.group in ("A", "B") else "database"
        adverse_events.append(AdverseEventRecord(
            event=ev.label,
            frequency="Reported",
            evidence=ev.confidence.title(),
            provenance=provenance,
        ))

    #  Confidence metrics (stub: derived from data completeness) 
    model_conf = 0.78  # Placeholder — would come from ProTox confidence
    mech_support = min(1.0, len(mechanisms) * 0.3) if mechanisms else 0.2
    ev_strength = min(1.0, len([e for e in evidence if e.confidence == "high"]) * 0.25) if evidence else 0.15

    confidence = ConfidenceMetrics(
        model_confidence=round(model_conf, 2),
        mechanistic_support=round(mech_support, 2),
        evidence_strength=round(ev_strength, 2),
    )

    return ResultsPageData(
        smiles=smiles,
        toxicity_class=f"{class_label} (Class {prediction.toxicity_class})",
        overall_score=round(overall_score, 2),
        endpoints=endpoints,
        mechanistic_risks=mechanistic_risks,
        primary_targets=primary_targets,
        off_targets=off_targets,
        mechanisms=mechanism_texts,
        pathways=pathway_texts,
        adverse_events=adverse_events,
        confidence=confidence,
    )
