"""Stage 3 — expression layer.

The rules already decided WHAT is true. This layer only decides HOW it is said:
  * translate the rule output into the traveller's language (en is the source of truth)
  * let the model add a short, question-specific explanation — but the model is
    explicitly forbidden from changing any fact, number, document or rule verdict.
"""
from __future__ import annotations

import logging

from .llm import LLMError, text_json
from .rules import RuleResult

log = logging.getLogger("copilot.i18n")

SYSTEM = (
    "You are the expression layer of a travel-assistance app. You receive a JSON object "
    "produced by a deterministic rule engine. Translate its natural-language strings into "
    "the requested language and return the SAME JSON structure. Never alter facts: keep "
    "every number, time, station name, train number, document name, severity value, "
    "rule_ref value and array length identical. Never add or remove findings or steps."
)

TEMPLATE = """Target language: {lang} ({lang_name})

Traveller's own question (may be empty): "{question}"

Rules for translation:
- Translate ONLY these string fields: title, detail, why_translation_fails, action,
  item, why, how_to_fix, scene_label.
- Leave every other key untouched, verbatim.
- Keep Chinese proper nouns (station names, 进站口, 人工通道, 改签, 报销凭证) and add a
  short gloss in the target language, e.g. "人工售票窗口 (staffed ticket counter)".
- Keep the tone: direct, imperative, written for someone standing in a queue.
- If why_translation_fails is an empty string, leave it empty.
- If the target language is "en", just return the input JSON unchanged (except ai_note).

Then add ONE extra top-level key:
  "ai_note": 2-3 sentences in the {lang_name} language answering the traveller's own
  question in plain words, based only on the facts in the payload. It must not
  contradict any rule finding. It must not invent times, documents or locations.

Return minified JSON only. Input JSON:
{payload}"""

LANG_NAMES = {"en": "English", "zh": "简体中文"}


def to_payload(result: RuleResult, vision: dict, lang: str) -> dict:
    return {
        "scene": result.scene,
        "scene_label": result.scene_label,
        "lang": lang,
        "timing": {
            "has_departure": result.timing.has_departure,
            "depart_time": result.timing.depart_time,
            "now": result.timing.now,
            "minutes_to_departure": result.timing.minutes_to_departure,
            "gate_close_time": result.timing.gate_close_time,
            "minutes_to_gate_close": result.timing.minutes_to_gate_close,
            "level": result.timing.level,
            "gate_close_rule": result.timing.gate_close_rule,
            "arrive_by": result.timing.arrive_by,
            "arrive_rule": result.timing.arrive_rule,
        },
        "facts_used": result.facts_used,
        "steps": [
            {"order": s.order, "action": s.action, "detail": s.detail,
             "rule_ref": s.rule_ref, "source": s.source}
            for s in result.steps
        ],
        "findings": [
            {"rule_ref": f.rule_ref, "severity": f.severity, "title": f.title,
             "detail": f.detail, "why_translation_fails": f.why_translation_fails,
             "zh_phrase": f.zh_phrase, "zh_pinyin": f.zh_pinyin, "source": f.source}
            for f in result.findings
        ],
        "missing": result.missing,
        "vision": {
            "confidence": vision.get("confidence"),
            "ocr_text": vision.get("ocr_text", []),
            "visual_clues": vision.get("visual_clues", []),
            "traveler_situation": vision.get("traveler_situation", ""),
            "extracted": vision.get("extracted", {}),
        },
    }


def _deep_fill(dst: dict, src: dict) -> dict:
    """Keep src where dst is missing a key (defensive: model may drop fields)."""
    for k, v in src.items():
        if k not in dst:
            dst[k] = v
        elif isinstance(v, dict) and isinstance(dst[k], dict):
            _deep_fill(dst[k], v)
        elif isinstance(v, list) and isinstance(dst[k], list) and len(v) == len(dst[k]):
            for a, b in zip(dst[k], v):
                if isinstance(a, dict) and isinstance(b, dict):
                    _deep_fill(a, b)
    return dst


def _align_lists(dst: dict, src: dict) -> None:
    """Keep the model's translated list unless it broke the structure.

    The model is told to keep array lengths and item identity identical. If it
    dropped/added items or silently reordered them, fall back to the English
    source (``src``) so the UI never shows a misaligned verdict. Otherwise we
    trust the model's translated ``dst`` — this is exactly what preserves the
    Chinese (or other) translation of findings/steps instead of reverting it.
    """
    for key in ("steps", "findings", "missing", "facts_used"):
        if key not in src:
            continue
        dst_list = dst.get(key)
        src_list = src.get(key)
        if not isinstance(dst_list, list) or not isinstance(src_list, list):
            # Model returned a non-list — trust the deterministic source.
            dst[key] = src_list
            continue
        if len(dst_list) != len(src_list):
            # Model added/removed items — restore the source to keep structure.
            dst[key] = src_list
            continue
        # Length matches. Guard against silent reordering using identity fields.
        if key in ("steps", "findings"):
            id_field = "order" if key == "steps" else "rule_ref"
            misaligned = any(
                not isinstance(d, dict)
                or not isinstance(s, dict)
                or d.get(id_field) != s.get(id_field)
                for d, s in zip(dst_list, src_list)
            )
            if misaligned:
                dst[key] = src_list


async def express(payload: dict, lang: str, question: str, with_ai_note: bool = True) -> dict:
    """Return payload, translated + (optionally) ai_note. Never raises."""
    payload = dict(payload)
    lang = (lang or "en").lower()
    note = ""

    if with_ai_note:
        try:
            out = await text_json(
                SYSTEM,
                TEMPLATE.format(lang=lang, lang_name=LANG_NAMES.get(lang, "English"),
                                question=question or "", payload=_dump(payload)),
            )
            note = str(out.get("ai_note", "")).strip()
        except LLMError as exc:
            log.warning("ai_note failed: %s", exc)

    if lang == "en":
        payload["ai_note"] = note if with_ai_note else ""
        payload["ai_note_source"] = "model" if (with_ai_note and note) else ""
        return payload

    try:
        out = await text_json(
            SYSTEM,
            TEMPLATE.format(lang=lang, lang_name=LANG_NAMES.get(lang, lang),
                            question=question or "", payload=_dump(payload)),
        )
    except LLMError as exc:
        log.warning("translation failed (%s): %s", lang, exc)
        payload["ai_note"] = note if with_ai_note else ""
        payload["translation"] = "fallback:en"
        return payload

    out.pop("ai_note", None)
    _deep_fill(out, payload)
    _align_lists(out, payload)
    out["scene"] = payload["scene"]
    out["timing"] = payload["timing"]
    out["ai_note"] = note if with_ai_note else ""
    out["translation"] = f"model:{lang}"
    return out


def _dump(payload: dict) -> str:
    import json
    return json.dumps(payload, ensure_ascii=False)
