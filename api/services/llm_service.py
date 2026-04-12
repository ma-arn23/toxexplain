"""
llm_service.py — LLM-powered toxicity data extraction.

Calls the Gemini API to extract structured toxicity data FROM DRUGBANK TEXT.
The LLM never uses its own knowledge — it only structures information that
is explicitly present in the DrugBank text passed to it.

If no DrugBank text is available for a compound, this service returns an
empty extraction without calling the LLM at all.

Requires the GEMINI_API_KEY environment variable to be set.
On Render: Service Settings → Environment → add GEMINI_API_KEY.
"""

import json
import os
from typing import Optional

from pydantic import BaseModel, Field

# In-memory cache: maps (drug_id) -> LLMExtraction so repeated queries within
# a single server process don't burn through Gemini's daily quota.
_CACHE: dict[str, "LLMExtraction"] = {}


# Structured output models (consumed by the orchestrator)


class LLMTarget(BaseModel):
    target_name: str
    role: str = "unknown"           # primary | off_target | secondary | unknown
    action: str = "unknown"         # inhibits | activates | blocks | binds | etc.
    organ_system: str = "unknown"
    confidence: str = "low"         # high | medium | low


class LLMMechanism(BaseModel):
    mechanism_name: str
    mechanism_category: str = "unknown"
    organ_system: str = "unknown"
    confidence: str = "low"


class LLMAdverseEvent(BaseModel):
    name: str
    organ_system: str = "unknown"
    severity: str = "unknown"       # mild | moderate | severe | fatal | unknown
    confidence: str = "low"


class LLMExtraction(BaseModel):
    """Structured toxicity extraction returned by the LLM."""
    targets: list[LLMTarget] = Field(default_factory=list)
    mechanisms: list[LLMMechanism] = Field(default_factory=list)
    adverse_events: list[LLMAdverseEvent] = Field(default_factory=list)
    pathways: list[str] = Field(default_factory=list)
    extraction_notes: str = ""

    @property
    def is_empty(self) -> bool:
        return not (
            self.targets or self.mechanisms or self.adverse_events or self.pathways
        )


# Prompt — adapted from drugbank_llm_pipeline.py (the offline pipeline).
# CRITICAL: extracts only from the input text, never from the LLM's own knowledge.


_SYSTEM_PROMPT = """You are a pharmacology and toxicology data extraction assistant.

Given DrugBank text about a drug, extract structured data into JSON format.
You must extract ONLY information that is explicitly stated in the input text.
Do NOT use any of your own knowledge about the drug. Do NOT supplement,
guess, or fabricate. If something is not in the input, leave the field as
"unknown" or omit the entry entirely.

## CONTROLLED VOCABULARY — use ONLY these values

role: primary | off_target | secondary | unknown
action: inhibits | activates | blocks | binds | modulates | induces | disrupts | causes | upregulates | downregulates | antagonist | intercalates | unknown
organ_system: cardiac | hepatic | renal | neurologic | gastrointestinal | hematologic | dermatologic | respiratory | reproductive | other | unknown
mechanism_category: electrophysiology | mitochondrial | immune | metabolic | oxidative_stress | transporters | dna_damage | cholestasis | other | unknown
severity: mild | moderate | severe | fatal | unknown
confidence: high | medium | low

## MAPPING RULES

- DrugBank "targets" with known_action=yes → role=primary
- DrugBank "targets" with known_action=no/unknown → role=off_target or secondary
- DrugBank "enzymes" → include as targets with role=secondary or off_target
- Map DrugBank action verbs to controlled vocabulary:
    "inhibitor" → "inhibits"
    "antagonist" → "antagonist"
    "blocker" → "blocks"
    "agonist" → "activates"
- If toxicity info is sparse in the text, say so in extraction_notes — do NOT fabricate

## OUTPUT FORMAT

Return ONLY valid JSON, no markdown fences, no preamble:

{
  "targets": [
    {"target_name": "", "role": "", "action": "", "organ_system": "", "confidence": ""}
  ],
  "mechanisms": [
    {"mechanism_name": "", "mechanism_category": "", "organ_system": "", "confidence": ""}
  ],
  "adverse_events": [
    {"name": "", "organ_system": "", "severity": "", "confidence": ""}
  ],
  "pathways": ["pathway 1", "pathway 2"],
  "extraction_notes": "Note any gaps or uncertainty"
}

## CRITICAL RULES

1. Extract ONLY from the provided text. NEVER use your own knowledge.
2. If the text does not mention something, do NOT include it.
3. Use "unknown" rather than guessing individual fields.
4. Be conservative with confidence — default to "low" or "medium" unless
   the text is explicit.
5. Distinguish therapeutic targets (role=primary) from toxicity-relevant
   targets (role=off_target).
6. Pathways must be biological pathway names mentioned in the text
   (e.g. "oxidative stress"), not free text or summaries.
"""


def _clean_json(raw: str) -> str:
    """Strip markdown fences and stray text from LLM output."""
    clean = raw.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    elif clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()
    if not clean.startswith("{"):
        start = clean.find("{")
        if start != -1:
            clean = clean[start:]
    if not clean.endswith("}"):
        end = clean.rfind("}")
        if end != -1:
            clean = clean[: end + 1]
    return clean


def _coerce_to_extraction(parsed: dict) -> LLMExtraction:
    """Build an LLMExtraction from raw parsed JSON, tolerating missing fields."""
    targets = [
        LLMTarget(**t) for t in parsed.get("targets", []) if t.get("target_name")
    ]
    mechanisms = [
        LLMMechanism(**m) for m in parsed.get("mechanisms", []) if m.get("mechanism_name")
    ]
    adverse_events = [
        LLMAdverseEvent(**ae) for ae in parsed.get("adverse_events", []) if ae.get("name")
    ]
    pathways = [p for p in parsed.get("pathways", []) if isinstance(p, str) and p.strip()]
    return LLMExtraction(
        targets=targets,
        mechanisms=mechanisms,
        adverse_events=adverse_events,
        pathways=pathways,
        extraction_notes=parsed.get("extraction_notes", "") or "",
    )


async def extract_from_drugbank_text(
    drugbank_text: str,
    cache_key: str = "",
) -> LLMExtraction:
    """
    Call Gemini to extract structured toxicity data from DrugBank text.

    Args:
        drugbank_text: The full DrugBank text block for a compound. If empty
            or None, returns an empty extraction without calling the LLM.
        cache_key: A stable identifier (e.g. drug_id) used as the cache key.
            If empty, falls back to using the text itself as the key.

    Returns an empty LLMExtraction on any failure (missing API key, network
    error, parse error) so the orchestrator can fall back gracefully.
    """

    # No text → don't call the LLM at all
    if not drugbank_text or not drugbank_text.strip():
        return LLMExtraction(extraction_notes="No DrugBank text available for this compound")

    key = cache_key or drugbank_text[:200]
    if key in _CACHE:
        return _CACHE[key]

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[llm_service] GEMINI_API_KEY not set — returning empty extraction")
        empty = LLMExtraction(extraction_notes="GEMINI_API_KEY not configured on server")
        _CACHE[key] = empty
        return empty

    try:
        # Lazy import so the rest of the app still works if google-genai
        # isn't installed during local testing.
        from google import genai

        client = genai.Client(api_key=api_key)

        user_prompt = (
            "Extract structured toxicity data from the following DrugBank text.\n\n"
            f"{drugbank_text}\n\n"
            "Return ONLY valid JSON with keys: targets, mechanisms, "
            "adverse_events, pathways, extraction_notes.\n"
            "Use ONLY the controlled vocabulary. Extract ONLY what is explicitly\n"
            "stated in the text above. Do NOT use your own knowledge of the drug."
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=user_prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                max_output_tokens=4096,
                response_mime_type="application/json",
            ),
        )

        raw = response.text or ""
        clean = _clean_json(raw)
        parsed = json.loads(clean)
        extraction = _coerce_to_extraction(parsed)

    except Exception as e:
        print(f"[llm_service] Extraction failed for cache_key={key}: {e}")
        extraction = LLMExtraction(extraction_notes=f"LLM call failed: {e}")

    _CACHE[key] = extraction
    return extraction
