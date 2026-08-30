from __future__ import annotations

import json
import logging
import os
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError

logger = logging.getLogger("swasthyanet.ai_client")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_TIMEOUT_SECONDS = 6
_GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"


def is_gemini_configured() -> bool:
    return bool(GEMINI_API_KEY)


def _call_gemini(prompt: str, json_mode: bool = True) -> dict | str | None:
    """Low-level call to the Gemini REST API. Returns parsed JSON (if json_mode),
    raw text, or None on any failure. Never raises -- callers must have a
    non-AI fallback ready."""
    if not is_gemini_configured():
        logger.info("GEMINI_API_KEY is not set; skipping AI call and using fallback.")
        return None

    url = _GEMINI_URL_TEMPLATE.format(model=GEMINI_MODEL, key=GEMINI_API_KEY)
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 700,
            **({"responseMimeType": "application/json"} if json_mode else {}),
        },
    }
    try:
        req = urlrequest.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlrequest.urlopen(req, timeout=GEMINI_TIMEOUT_SECONDS) as resp:
            if resp.status != 200:
                logger.warning("Gemini API returned HTTP %s", resp.status)
                return None
            payload = json.loads(resp.read().decode("utf-8"))
    except (URLError, HTTPError, TimeoutError, OSError) as exc:
        logger.warning("Gemini API request failed: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001 - never let AI failures break the API
        logger.warning("Unexpected error calling Gemini: %s", exc)
        return None

    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        logger.warning("Unexpected Gemini response shape: %s", payload)
        return None

    if not json_mode:
        return text.strip()

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        logger.warning("Failed to parse Gemini JSON output: %s", text[:200])
        return None


def gemini_forecast_explanation(phc_name: str, medicine_name: str, history: list[float], quantity: int, predicted_daily_use: float, days_until_stockout: float) -> dict | None:
    """Ask Gemini to explain a stockout forecast in clinical, human-readable terms."""
    prompt = (
        "You are a public health supply chain analyst. Given this recent daily "
        f"consumption history (units/day) for {medicine_name} at {phc_name}: {history[-14:]}, "
        f"current stock: {quantity} units, a statistical model predicts "
        f"{predicted_daily_use} units/day usage and {days_until_stockout} days until stockout. "
        "Respond ONLY with a JSON object with exactly these keys: "
        '"explanation" (one or two sentences on the consumption pattern, plain language, '
        'no jargon), "risk_level" (one of "low", "moderate", "high", "critical").'
    )
    result = _call_gemini(prompt, json_mode=True)
    if not isinstance(result, dict) or "explanation" not in result:
        return None
    risk = result.get("risk_level")
    if risk not in {"low", "moderate", "high", "critical"}:
        risk = "moderate"
    return {"explanation": str(result.get("explanation", ""))[:400], "risk_level": risk}


def gemini_redistribution_reasoning(source_name: str, destination_name: str, medicine_name: str, quantity: int, distance_km: float, days_until_stockout: float) -> str | None:
    """Ask Gemini to generate a clinical justification for a redistribution recommendation."""
    prompt = (
        f"A public health redistribution system recommends transferring {quantity} units of "
        f"{medicine_name} from {source_name} to {destination_name} ({distance_km} km away), "
        f"because {destination_name} is projected to stock out in {days_until_stockout} days. "
        "Write ONE short sentence (max 30 words) justifying this transfer for a district health "
        "officer, in plain operational language. Respond with plain text only, no formatting."
    )
    result = _call_gemini(prompt, json_mode=False)
    if not result:
        return None
    return str(result)[:300]


def gemini_district_briefing(phc_name: str, district: str, occupancy_pct: float, active_alerts: int, critical_medicines: list[str], lang: str = "en") -> dict | None:
    """Generate a short multilingual executive briefing for a PHC."""
    lang_names = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
    language = lang_names.get(lang, "English")
    prompt = (
        f"You are briefing a District Health Officer about {phc_name} in {district} district. "
        f"Bed occupancy is {occupancy_pct}%. There are {active_alerts} active alerts. "
        f"Medicines at risk of stockout: {', '.join(critical_medicines) if critical_medicines else 'none'}. "
        f"Write a brief (3-4 sentences) executive summary IN {language.upper()} for a health "
        "administrator. Be direct and actionable, no filler. "
        'Respond ONLY with a JSON object with exactly one key: "briefing" (the summary text).'
    )
    result = _call_gemini(prompt, json_mode=True)
    if not isinstance(result, dict) or "briefing" not in result:
        return None
    return {"briefing": str(result.get("briefing", ""))[:800], "language": lang}
