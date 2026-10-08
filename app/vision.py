"""Stage 1 — multimodal scene & document understanding.

The model's ONLY job here is perception: read the picture, name the scene,
transcribe what it literally says. It must NOT decide what the traveller
should do — that is the rule engine's job (see rules.py).
"""
from __future__ import annotations

import logging
from typing import Any

from .llm import LLMError, vision_json

log = logging.getLogger("copilot.vision")

SCENE_TAXONOMY = {
    "rail_ticket": "A train ticket, e-ticket screenshot, booking confirmation or itinerary for a Chinese railway (CR) journey.",
    "rail_kiosk": "A self-service ticket machine / kiosk (自助售取票机) or its on-screen error message.",
    "rail_entrance": "Station entrance, plaza signage, real-name identity check point, security check entrance.",
    "rail_waiting_hall": "Waiting hall, departure board / big screen showing train numbers and check-in gates (检票口).",
    "rail_gate": "Ticket barrier / automated gate (检票闸机) or the queue in front of it.",
    "rail_platform": "Platform, train exterior, carriage number plate, seat number inside the train.",
    "hotel_checkin": "Hotel front desk, check-in counter, lobby signage or a hotel booking confirmation.",
    "unknown": "None of the above fits.",
}

SYSTEM_PROMPT = (
    "You are the perception module of an assistance app for foreign travellers in China. "
    "You look at one photo taken on site. You are careful, literal and never invent data. "
    "Reply with a single minified JSON object and nothing else."
)

USER_PROMPT_TEMPLATE = """Look at this photo taken by a traveller in China.

1. Choose exactly one scene id from this taxonomy:
{taxonomy}

2. Transcribe the visible text faithfully. Keep Chinese as Chinese, English as English.
   Do not translate. Do not paraphrase. If unreadable, use "".

3. Fill `extracted`. Use null for anything you cannot actually see or infer with
   high confidence. NEVER guess a value to make the JSON look complete —
   a missing value is handled by the rule engine, a wrong value is dangerous.

4. `visual_clues`: short factual observations about what is physically in the frame
   (e.g. "passport in hand", "machine shows red error", "queue at manual counter").

5. `confidence`: 0.0-1.0 that the scene id is right.

Traveller context (may be empty): {context}

Output JSON, exact keys:
{{
  "scene": "<scene id>",
  "scene_label_en": "<human readable, e.g. self-service ticket machine>",
  "confidence": 0.0,
  "ocr_text": ["<line 1>", "<line 2>"],
  "extracted": {{
    "train_no": "<e.g. G7, D2284, K1234; null if absent>",
    "from_station": "<as printed, e.g. 北京南; null>",
    "to_station": "<as printed; null>",
    "depart_date": "<YYYY-MM-DD; null>",
    "depart_time": "<HH:MM 24h; null>",
    "gate": "<检票口, e.g. B12; null>",
    "carriage": "<车厢号; null>",
    "seat": "<seat number; null>",
    "id_type_on_ticket": "<passport | chinese_id | other | null>",
    "station_name_on_site": "<station name physically visible on signage/building; null>",
    "entrance_name_on_site": "<e.g. 南进站口 / 东广场; null>",
    "is_departure_side": "<true|false|null — is this an entrance/INBOUND side rather than exit>",
    "hotel_name": "<null unless hotel scene>",
    "checkin_date": "<YYYY-MM-DD; null>",
    "machine_error": "<kiosk error text if any; null>"
  }},
  "visual_clues": ["<observation>"],
  "traveler_situation": "<one sentence: what the traveller appears to be doing right now>",
  "needs_human_counter": "<true|false|null — does the photo imply the machine/process refuses the traveller?>"
}}"""


def build_user_prompt(context: str = "") -> str:
    taxonomy = "\n".join(f'  - "{k}": {v}' for k, v in SCENE_TAXONOMY.items())
    return USER_PROMPT_TEMPLATE.format(
        taxonomy=taxonomy, context=context or "(none provided)"
    )


# What the rule engine needs, with safe defaults.
_EXTRACTED_KEYS = [
    "train_no", "from_station", "to_station", "depart_date", "depart_time",
    "gate", "carriage", "seat", "id_type_on_ticket", "station_name_on_site",
    "entrance_name_on_site", "is_departure_side", "hotel_name", "checkin_date",
    "machine_error",
]


def _normalise(raw: dict[str, Any]) -> dict[str, Any]:
    ext = raw.get("extracted") or {}
    if not isinstance(ext, dict):
        ext = {}
    clean: dict[str, Any] = {}
    for k in _EXTRACTED_KEYS:
        v = ext.get(k)
        if isinstance(v, str):
            v = v.strip()
            if v.lower() in {"", "null", "none", "n/a", "unknown"}:
                v = None
        clean[k] = v
    # model sometimes flips side detection to a string
    side = clean.get("is_departure_side")
    if isinstance(side, str):
        clean["is_departure_side"] = side.strip().lower() in {"true", "yes", "1"}
    try:
        conf = float(raw.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    return {
        "scene": raw.get("scene") or "unknown",
        "scene_label_en": raw.get("scene_label_en") or "unknown scene",
        "confidence": max(0.0, min(1.0, conf)),
        "ocr_text": [str(x) for x in (raw.get("ocr_text") or []) if str(x).strip()][:24],
        "extracted": clean,
        "visual_clues": [str(x) for x in (raw.get("visual_clues") or []) if str(x).strip()][:12],
        "traveler_situation": str(raw.get("traveler_situation") or "")[:300],
        "needs_human_counter": bool(raw.get("needs_human_counter")),
    }


async def understand_image(image_data_url: str, context: str = "") -> dict[str, Any]:
    """Run stage 1. Raises LLMError on hard failure."""
    raw = await vision_json(image_data_url, SYSTEM_PROMPT, build_user_prompt(context))
    if raw.get("scene") not in SCENE_TAXONOMY:
        log.warning("model returned unknown scene id: %r", raw.get("scene"))
        raw["scene"] = "unknown"
    return _normalise(raw)
