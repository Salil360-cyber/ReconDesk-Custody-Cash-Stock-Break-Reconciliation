"""
Optional AI layer: rewrites break explanations and next actions in context.

Design choices
--------------
* Matching and classification never use AI. They are rules, so they stay fast,
  repeatable and auditable.
* AI only touches the free-text "explanation" and "next_action" columns, which
  are judgement calls where an LLM adds value.
* ONE batched API call for all breaks (v1 made one call per break with a
  13-second sleep between calls).
* If there is no API key, the package is missing, or the response cannot be
  parsed, the rule-based playbook text stays in place and the report says so.
"""

import json
import os

import config


def _client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None, "no GEMINI_API_KEY set"
    try:
        from google import genai  # google-genai package
    except ImportError:
        return None, "google-genai package not installed"
    return genai.Client(api_key=key), None


def enrich_breaks(breaks, use_ai=True):
    """Mutates break rows in place. Returns a short string describing the mode used."""
    if not use_ai:
        return "rules only (AI disabled with --no-ai)"
    if not breaks:
        return "rules only (no breaks)"
    if len(breaks) > config.MAX_BREAKS_FOR_AI:
        return f"rules only (more than {config.MAX_BREAKS_FOR_AI} breaks)"

    client, reason = _client()
    if client is None:
        return f"rules only ({reason})"

    payload = [
        {"id": i, "recon_type": b["recon_type"], "item": b["item"], "status": b["status"],
         "currency": b["currency"], "books": b["books_value"], "custodian": b["custodian_value"],
         "difference": b["difference"], "age_days": b["age_days"],
         "rule_based_cause": b["probable_cause"]}
        for i, b in enumerate(breaks)
    ]
    prompt = (
        "You are a custody operations analyst reviewing daily reconciliation breaks "
        "between internal books and the custodian.\n"
        "For each break, return a JSON list of objects with keys "
        '"id", "explanation" (one sentence, likely root cause) and '
        '"next_action" (one sentence, what the analyst should do today).\n'
        "Keep the rule_based_cause unless the data clearly contradicts it. "
        "Return JSON only, no markdown.\n\n" + json.dumps(payload)
    )
    model = os.getenv("GEMINI_MODEL", config.DEFAULT_GEMINI_MODEL)
    try:
        resp = client.models.generate_content(model=model, contents=prompt)
        text = resp.text.strip()
        if text.startswith("```"):
            text = text.strip("`").split("\n", 1)[1]
        items = json.loads(text)
        by_id = {int(x["id"]): x for x in items}
    except Exception as e:  # noqa: BLE001 - any failure falls back to rules
        return f"rules only (AI call failed: {type(e).__name__})"

    updated = 0
    for i, b in enumerate(breaks):
        x = by_id.get(i)
        if x and x.get("explanation") and x.get("next_action"):
            b["explanation"] = str(x["explanation"]).strip()
            b["next_action"] = str(x["next_action"]).strip()
            updated += 1
    return f"Gemini ({model}), {updated}/{len(breaks)} breaks explained"
