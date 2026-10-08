"""Deterministic verification of the i18n fix (no live model call).

We monkeypatch app.llm.text_json so it returns a *Chinese* "model" translation
that keeps the exact same structure as the English source payload. Then we run
the real express() path and assert that findings/steps stay in Chinese (the
bug was that they got reverted to English).
"""
import asyncio
import sys

import app.llm as llm_mod
import app.i18n as i18n_mod


# --- Monkeypatched model: returns a faithful Chinese translation of the payload ---
def fake_text_json(system, user_prompt):
    # The real model is prompted to return minified JSON. We parse the input
    # payload out of the prompt and produce a Chinese mirror of it.
    marker = "Input JSON:\n"
    idx = user_prompt.find(marker)
    import json
    payload = json.loads(user_prompt[idx + len(marker):])

    def zh(s):
        return {
            "This machine cannot read a passport — go to the staffed counter":
                "这台机器无法读取护照——请前往人工窗口（staffed counter）办理",
            "Carry the passport in your hand and approach a staff member.":
                "请手持护照并走向工作人员。",
            "Go to the staffed counter (人工售票窗口), not the machine.":
                "请前往人工售票窗口（staffed counter），不要使用机器。",
            "Self-service kiosk cannot read foreign passports":
                "自助售票机无法读取外国护照",
        }.get(s, s)

    out = json.loads(json.dumps(payload, ensure_ascii=False))
    for f in out.get("findings", []):
        f["title"] = zh(f.get("title", ""))
        f["detail"] = zh(f.get("detail", ""))
    for s in out.get("steps", []):
        s["action"] = zh(s.get("action", ""))
        s["detail"] = zh(s.get("detail", ""))
    out["scene_label"] = "火车站自助售票机" if out.get("scene") == "rail_kiosk" else out.get("scene_label", "")
    out["ai_note"] = "这是一段中文解说，用于回答旅客的问题。"
    return out


llm_mod.text_json = fake_text_json


# --- Build an English source payload (mirrors the rule engine output) ---
payload = {
    "scene": "rail_kiosk",
    "scene_label": "Station self-service kiosk",
    "lang": "en",
    "timing": {"level": "ok"},
    "facts_used": ["machine_type: kiosk", "passport_present: yes"],
    "steps": [
        {"order": 1, "action": "Go to the staffed counter (人工售票窗口), not the machine.",
         "detail": "Carry the passport in your hand and approach a staff member.",
         "rule_ref": "RAIL-KIOSK-01", "source": "rule"},
    ],
    "findings": [
        {"rule_ref": "RAIL-KIOSK-01", "severity": "critical",
         "title": "Self-service kiosk cannot read foreign passports",
         "detail": "This machine cannot read a passport — go to the staffed counter",
         "why_translation_fails": "", "zh_phrase": "人工售票窗口", "zh_pinyin": "réngōng shòupiào chuāngkǒu",
         "source": "rule"},
    ],
    "missing": [],
    "vision": {"confidence": 0.9, "ocr_text": [], "visual_clues": [], "traveler_situation": "", "extracted": {}},
}


async def main():
    result = await i18n_mod.express(payload, "zh", "How do I buy a ticket?")
    print("translation:", result.get("translation"))
    print("scene_label:", result.get("scene_label"))
    print("ai_note:", result.get("ai_note"))
    print("--- findings ---")
    for f in result["findings"]:
        print(f"  [{f['severity']}] {f['rule_ref']} | {f['title']}")
        print(f"      detail: {f['detail']}")
        # identity must be preserved
        assert f["rule_ref"] == "RAIL-KIOSK-01", "rule_ref must be preserved"
        assert f["severity"] == "critical", "severity must be preserved"
        assert f["zh_phrase"] == "人工售票窗口", "zh_phrase must be preserved"
    print("--- steps ---")
    for s in result["steps"]:
        print(f"  {s['order']}. {s['action']}")
        print(f"      {s['detail']}")
        assert s["rule_ref"] == "RAIL-KIOSK-01", "step rule_ref preserved"
    # The core assertion: findings/steps are NOT reverted to English.
    assert "无法" in result["findings"][0]["title"], "findings title should be Chinese!"
    assert "人工售票窗口" in result["steps"][0]["action"], "step action should be Chinese!"
    assert result["translation"] == "model:zh"
    print("\nPASS: Chinese findings/steps preserved; no English revert.")


# --- Fallback path: model drops an item -> restore English source structure ---
def test_align_fallback():
    import copy
    src = {
        "findings": [
            {"rule_ref": "A", "severity": "info", "title": "English A", "detail": "dA", "source": "rule"},
            {"rule_ref": "B", "severity": "critical", "title": "English B", "detail": "dB", "source": "rule"},
        ],
        "steps": [
            {"order": 1, "action": "English step 1", "detail": "d1", "rule_ref": "A", "source": "rule"},
        ],
    }
    # Model dropped finding B and returned Chinese for A only.
    dst = {
        "findings": [
            {"rule_ref": "A", "severity": "info", "title": "中文 A", "detail": "中文dA", "source": "rule"},
        ],
        "steps": [
            {"order": 1, "action": "中文 step 1", "detail": "中文d1", "rule_ref": "A", "source": "rule"},
        ],
    }
    i18n_mod._align_lists(dst, src)
    # findings should be RESTORED to full English source (count mismatch)
    assert len(dst["findings"]) == 2, f"expected fallback restore, got {dst['findings']}"
    assert dst["findings"][1]["rule_ref"] == "B", "fallback must re-add dropped item"
    assert dst["findings"][1]["title"] == "English B", "fallback item should be English source"
    # steps count matched -> keep Chinese translation
    assert "中文" in dst["steps"][0]["action"], "steps with matched count should keep Chinese"
    print("PASS: dropped-item fallback restores source; matched-count list keeps translation.\n")


if __name__ == "__main__":
    test_align_fallback()
    asyncio.run(main())
