# Data class schemas

This is the agreed contract for all data classes in ToxExplain.
**Do not change these without telling the whole team first.**

---

## QueryInput

```json
{
  "smiles": "CC(=O)Oc1ccccc1C(=O)O"
}
```

---

## ProToxPrediction

```json
{
  "smiles": "CC(=O)Oc1ccccc1C(=O)O",
  "ld50": 200,
  "toxicity_class": 3,
  "toxicity_class_label": "Toxic",
  "endpoints": {
    "hepatotoxicity": true,
    "nephrotoxicity": false,
    "immunotoxicity": false,
    "mutagenicity": false,
    "cytotoxicity": true
  }
}
```

---

## MechanismRecord

Provided by Groups A and B.

```json
{
  "drug_name": "Troglitazone",
  "smiles": "...",
  "primary_targets": ["PPAR-gamma", "CYP2C8"],
  "off_targets": ["mitochondrial complex I"],
  "pathways": ["oxidative stress", "hepatocyte apoptosis"],
  "organ_systems": ["liver"],
  "withdrawal_reason": "Severe hepatotoxicity",
  "source": "Group A",
  "references": ["PMID:12345678"]
}
```

---

## EvidenceItem

```json
{
  "label": "Mitochondrial dysfunction observed in hepatocytes",
  "source": "PMID:12345678",
  "origin": "in vitro study",
  "group": "A",
  "confidence": "high"
}
```

Confidence values: `"high"` | `"medium"` | `"low"`

---

## InterpretabilityRule

```json
{
  "rule_id": "rule_001",
  "description": "Compounds with reactive quinone metabolites are associated with hepatocyte GSH depletion.",
  "structural_feature": "quinone moiety",
  "toxicity_outcome": "hepatotoxicity",
  "generated_by": "llm",
  "model_version": "claude-sonnet-4-20250514"
}
```

---

## MechanisticFlag

```json
{
  "organ": "liver",
  "risk_level": "high",
  "mechanism": "reactive metabolite formation",
  "supporting_evidence_ids": ["rule_001", "PMID:12345678"]
}
```

---

## ExplainabilityResult

The top-level object combining everything. This is what the frontend Pinia store holds.

```json
{
  "query": { },
  "prediction": { },
  "mechanism_records": [],
  "evidence_items": [],
  "interpretability_rules": [],
  "mechanistic_flags": [],
  "summary": "This compound shows high predicted hepatotoxicity (ProTox class 3) consistent with curated evidence from structurally similar withdrawn drugs. The quinone metabolite pattern matches rule_001, with strong mechanistic support for mitochondrial dysfunction in hepatocytes."
}
```
