"""
orchestrator.py — Orchestrates the full explainability pipeline.

Pipeline:
  1. Get ProTox prediction (currently stubbed in protox_service.py)
  2. Look up curated mechanism records by SMILES (mechanism_service)
  3. Look up DrugBank text by SMILES (drugbank_service)
  4. If DrugBank text exists, call LLM to extract structured data FROM IT
     (the LLM never uses its own knowledge — it only structures the text).
  5. Merge curated + LLM per field. Curated wins; LLM fills gaps.
  6. Transform into ResultsPageData for the frontend.

If no DrugBank text exists for the SMILES, the LLM is skipped and the
explainability panel will show curated data only (or be empty).
"""

from api.models import (
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
from api.services.drugbank_service import lookup_drugbank_text
from api.services.llm_service import extract_from_drugbank_text, LLMExtraction


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
    if score >= 0.6:
        return "high"
    elif score >= 0.35:
        return "moderate"
    else:
        return "low"


def _score_to_severity(score: float) -> str:
    if score >= 0.7:
        return "high"
    elif score >= 0.4:
        return "moderate"
    else:
        return "low"


def _conf_str_to_float(conf: str) -> float:
    """Map 'high'/'medium'/'low' string confidences to numeric scores."""
    return {"high": 0.85, "medium": 0.6, "low": 0.4}.get((conf or "").lower(), 0.5)


# Field-level merge helpers
# Curated data wins; LLM fills gaps. Each output record carries a `provenance`
# tag so the UI can badge it correctly.


def _build_targets(
    mechanisms: list,
    llm: LLMExtraction,
) -> tuple[list[TargetRecord], list[TargetRecord]]:
    """Return (primary_targets, off_targets) merged from curated + LLM."""
    primary: list[TargetRecord] = []
    off: list[TargetRecord] = []
    seen_primary: set[str] = set()
    seen_off: set[str] = set()

    # 1. Curated first
    for mech in mechanisms:
        provenance = "curated" if mech.source in ("Group A", "Group B") else "database"
        for target_name in mech.primary_targets:
            if target_name and target_name not in seen_primary:
                seen_primary.add(target_name)
                primary.append(TargetRecord(
                    name=target_name,
                    interaction="primary target",
                    confidence=0.85,
                    provenance=provenance,
                ))
        for target_name in mech.off_targets:
            if target_name and target_name not in seen_off:
                seen_off.add(target_name)
                off.append(TargetRecord(
                    name=target_name,
                    interaction="off-target",
                    confidence=0.65,
                    provenance=provenance,
                ))

    # 2. LLM fills gaps
    for t in llm.targets:
        name = t.target_name
        if not name:
            continue
        record = TargetRecord(
            name=name,
            interaction=t.action if t.action != "unknown" else "interaction",
            confidence=_conf_str_to_float(t.confidence),
            provenance="llm",
        )
        if t.role == "primary" and name not in seen_primary:
            seen_primary.add(name)
            primary.append(record)
        elif t.role in ("off_target", "secondary") and name not in seen_off:
            seen_off.add(name)
            off.append(record)
        elif name not in seen_primary and name not in seen_off:
            # Role unknown — bucket as off-target by default
            seen_off.add(name)
            off.append(record)

    return primary, off


def _build_mechanisms(
    mechanisms: list,
    llm: LLMExtraction,
) -> list[TextEvidenceRecord]:
    """Build the list of toxicity mechanism descriptions."""
    out: list[TextEvidenceRecord] = []
    seen: set[str] = set()

    for mech in mechanisms:
        provenance = "curated" if mech.source in ("Group A", "Group B") else "database"
        if mech.withdrawal_reason and mech.withdrawal_reason not in seen:
            seen.add(mech.withdrawal_reason)
            out.append(TextEvidenceRecord(text=mech.withdrawal_reason, provenance=provenance))

    for m in llm.mechanisms:
        if m.mechanism_name and m.mechanism_name not in seen:
            seen.add(m.mechanism_name)
            out.append(TextEvidenceRecord(text=m.mechanism_name, provenance="llm"))

    return out


def _build_pathways(
    mechanisms: list,
    llm: LLMExtraction,
) -> list[TextEvidenceRecord]:
    out: list[TextEvidenceRecord] = []
    seen: set[str] = set()

    for mech in mechanisms:
        provenance = "curated" if mech.source in ("Group A", "Group B") else "database"
        for pw in mech.pathways:
            if pw and pw not in seen:
                seen.add(pw)
                out.append(TextEvidenceRecord(text=pw, provenance=provenance))

    for pw in llm.pathways:
        if pw and pw not in seen:
            seen.add(pw)
            out.append(TextEvidenceRecord(text=pw, provenance="llm"))

    return out


def _build_adverse_events(
    evidence: list,
    llm: LLMExtraction,
) -> list[AdverseEventRecord]:
    out: list[AdverseEventRecord] = []
    seen: set[str] = set()

    for ev in evidence:
        if ev.label and ev.label not in seen:
            seen.add(ev.label)
            provenance = "curated" if ev.group in ("A", "B") else "database"
            out.append(AdverseEventRecord(
                event=ev.label,
                frequency="Reported",
                evidence=ev.confidence.title() if ev.confidence else "Unknown",
                provenance=provenance,
            ))

    for ae in llm.adverse_events:
        if ae.name and ae.name not in seen:
            seen.add(ae.name)
            out.append(AdverseEventRecord(
                event=ae.name,
                frequency="Reported",
                evidence=ae.confidence.title() if ae.confidence else "Unknown",
                provenance="llm",
            ))

    return out


def _build_mechanistic_risks(
    mechanisms: list,
    llm: LLMExtraction,
) -> list[MechanisticRisk]:
    """Build the 'Why might this be toxic?' card entries."""
    risks: list[MechanisticRisk] = []

    # 1. From curated mechanism records — one risk per (drug, organ_system)
    for mech in mechanisms:
        for organ in mech.organ_systems:
            risk_id = f"curated-{mech.drug_name.lower().replace(' ', '-')}-{organ}"
            triggered_by = list(mech.primary_targets) + list(mech.off_targets)
            conf = 0.8
            risks.append(MechanisticRisk(
                id=risk_id,
                type=f"{organ.title()} Toxicity",
                severity=_score_to_severity(conf),
                description=mech.withdrawal_reason or f"Potential {organ} toxicity",
                confidence=conf,
                triggered_by=triggered_by or ["curated evidence"],
                support_status="strong",
                related_targets=list(mech.primary_targets),
                related_off_targets=list(mech.off_targets),
                related_mechanisms=[mech.withdrawal_reason] if mech.withdrawal_reason else [],
                related_pathways=list(mech.pathways),
            ))

    # 2. From LLM mechanisms — only for organs not covered by curated risks
    seen_organs = {r.type.lower().replace(" toxicity", "") for r in risks}
    for m in llm.mechanisms:
        organ = m.organ_system
        if organ in ("unknown", "other", "") or organ in seen_organs:
            continue
        seen_organs.add(organ)
        conf = _conf_str_to_float(m.confidence)
        related = [t.target_name for t in llm.targets if t.organ_system == organ]
        risks.append(MechanisticRisk(
            id=f"llm-{organ}-{m.mechanism_name[:20].lower().replace(' ', '-')}",
            type=f"{organ.title()} Toxicity",
            severity=_score_to_severity(conf),
            description=m.mechanism_name,
            confidence=conf,
            triggered_by=related or ["LLM-extracted from DrugBank text"],
            support_status="emerging",
            related_targets=[t.target_name for t in llm.targets if t.role == "primary"],
            related_off_targets=[
                t.target_name for t in llm.targets
                if t.role in ("off_target", "secondary")
            ],
            related_mechanisms=[m.mechanism_name],
            related_pathways=list(llm.pathways),
        ))

    return risks


# Main entry point


async def build_results_page_data(smiles: str) -> ResultsPageData:
    """End-to-end pipeline returning a ResultsPageData object for the frontend."""

    # Step 1: ProTox prediction
    prediction = await get_protox_prediction(smiles)

    # Step 2: Curated mechanism lookup
    mechanisms, evidence = await lookup_mechanisms(smiles)

    # Step 3: DrugBank text lookup (no LLM call yet)
    drugbank_record = lookup_drugbank_text(smiles)

    # Step 4: LLM extraction — ONLY if we have DrugBank text for this compound.
    # The LLM never sees just a SMILES; it always sees real DrugBank text and
    # is instructed to extract only what is explicitly stated.
    if drugbank_record and drugbank_record.get("drugbank_text"):
        llm = await extract_from_drugbank_text(
            drugbank_text=drugbank_record["drugbank_text"],
            cache_key=drugbank_record.get("drug_id", ""),
        )
    else:
        llm = LLMExtraction(
            extraction_notes="No DrugBank entry for this SMILES — LLM extraction skipped"
        )

    # Step 5: Build the response

    class_label, overall_score = _CLASS_TO_RISK.get(
        prediction.toxicity_class, ("Unknown", 0.5)
    )

    endpoint_data = prediction.endpoints.model_dump()
    endpoint_scores = {
        "hepatotoxicity": ("Hepatotoxicity", 0.72 if endpoint_data["hepatotoxicity"] else 0.15),
        "nephrotoxicity": ("Nephrotoxicity", 0.58 if endpoint_data["nephrotoxicity"] else 0.20),
        "immunotoxicity": ("Immunotoxicity", 0.65 if endpoint_data["immunotoxicity"] else 0.18),
        "mutagenicity": ("Mutagenicity", 0.61 if endpoint_data["mutagenicity"] else 0.12),
        "cytotoxicity": ("Cytotoxicity", 0.68 if endpoint_data["cytotoxicity"] else 0.22),
    }
    endpoints = [
        EndpointRisk(name=name, score=score, risk=_score_to_risk(score))
        for _, (name, score) in endpoint_scores.items()
    ]

    primary_targets, off_targets = _build_targets(mechanisms, llm)
    mechanism_texts = _build_mechanisms(mechanisms, llm)
    pathway_texts = _build_pathways(mechanisms, llm)
    adverse_events = _build_adverse_events(evidence, llm)
    mechanistic_risks = _build_mechanistic_risks(mechanisms, llm)

    # Confidence metrics
    model_conf = 0.78  # Placeholder until ProTox returns real confidence
    if mechanisms:
        mech_support = min(1.0, len(mechanisms) * 0.3)
    elif not llm.is_empty:
        mech_support = 0.5
    else:
        mech_support = 0.2

    high_conf_evidence = len([e for e in evidence if e.confidence == "high"])
    if high_conf_evidence:
        ev_strength = min(1.0, high_conf_evidence * 0.25)
    elif not llm.is_empty:
        ev_strength = 0.4
    else:
        ev_strength = 0.15

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
