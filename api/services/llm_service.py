"""
llm_service.py — LLM-powered explanation generation.

This module calls an LLM to produce a plain-English explanation
of why a compound might be toxic based on prediction + mechanism data.

Currently returns STUB data. Replace with a real LLM API call when ready.
"""

from api.models import ProToxPrediction, MechanismRecord, EvidenceItem


async def generate_explanation(
    prediction: ProToxPrediction,
    mechanisms: list[MechanismRecord],
    evidence: list[EvidenceItem],
) -> str:
    """
    Generate an LLM-powered explanation from the prediction and mechanism data.

    TODO: Replace this stub with a real LLM API call. The real implementation
    would look something like:

        prompt = _build_prompt(prediction, mechanisms, evidence)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], ...},
                json={
                    "model": "claude-sonnet-4-20250514",
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        return response.json()["content"][0]["text"]

    Returns:
        A plain-English summary string explaining the toxicity prediction.
    """

    # --- STUB: Build a template summary from the data ---
    endpoint_data = prediction.endpoints.model_dump()
    active_endpoints = [k for k, v in endpoint_data.items() if v]
    mechanism_names = [m.drug_name for m in mechanisms]

    summary = (
        f"This compound (SMILES: {prediction.smiles}) has a predicted LD50 of "
        f"{prediction.ld50} mg/kg (GHS toxicity class {prediction.toxicity_class} — "
        f"{prediction.toxicity_class_label}). "
    )

    if active_endpoints:
        summary += f"Active toxicity endpoints: {', '.join(active_endpoints)}. "

    if mechanism_names:
        summary += (
            f"Curated evidence from structurally similar withdrawn drugs "
            f"({', '.join(mechanism_names)}) supports these findings. "
        )

    high_conf_count = len([e for e in evidence if e.confidence == "high"])
    if high_conf_count:
        summary += (
            f"{high_conf_count} high-confidence evidence item(s) provide "
            f"strong mechanistic support for the predicted toxicity."
        )

    return summary
