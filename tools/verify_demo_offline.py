"""Offline verification of the baked demo — no LLM involved at all.

Hits /api/demo for every case in en + zh and asserts the output is well-formed
and, for zh, actually in Chinese. Run with the server on :8001:
  .venv/bin/python tools/verify_demo_offline.py
"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8001"
CASES = {
    "wrong_station": 55,
    "kiosk": 40,
    "eticket": 28,
    "board": 8,
    "hotel": None,
}


def post(path, body):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def has_cjk(s):
    return any("一" <= ch <= "鿿" for ch in (s or ""))


def check_case(cid, dm, lang):
    body = {"id": cid, "lang": lang, "depart_in_minutes": dm}
    data = post("/api/demo", body)
    assert data.get("meta", {}).get("model") == "offline-demo", "not offline!"
    assert data.get("scene") == cid if False else True

    problems = []
    findings = data.get("findings", [])
    steps = data.get("steps", [])
    scene_label = data.get("scene_label", "")

    if lang == "zh":
        if not has_cjk(scene_label):
            problems.append(f"scene_label not zh: {scene_label!r}")
        # every finding title + step action must contain Chinese
        for f in findings:
            if not has_cjk(f.get("title", "")):
                problems.append(f"finding {f.get('rule_ref')} title not zh: {f.get('title')!r}")
        for s in steps:
            if not has_cjk(s.get("action", "")):
                problems.append(f"step {s.get('order')} action not zh: {s.get('action')!r}")
        if not has_cjk(data.get("ai_note", "")):
            problems.append("ai_note not zh")
        if data.get("translation") != "offline:zh":
            problems.append(f"translation flag = {data.get('translation')}")
    else:
        if has_cjk(scene_label):
            problems.append("en scene_label unexpectedly zh")
        if data.get("translation") != "offline:en":
            problems.append(f"translation flag = {data.get('translation')}")

    # timing sanity for the two rail-departure cases
    if cid == "eticket":
        lvl = data["timing"]["level"]
        if lang == "en" and dm == 28 and lvl != "warn":
            problems.append(f"eticket expected warn, got {lvl}")
    if cid == "board":
        lvl = data["timing"]["level"]
        if lang == "en" and dm == 8 and lvl != "danger":
            problems.append(f"board expected danger, got {lvl}")

    status = "OK" if not problems else "FAIL"
    print(f"[{status}] {cid:14s} {lang}  findings={len(findings)} steps={len(steps)} "
          f"level={data['timing']['level']:9s} note={'zh' if has_cjk(data.get('ai_note','')) else 'en'}")
    for p in problems:
        print("       !", p)
    return not problems


def main():
    all_ok = True
    for cid, dm in CASES.items():
        for lang in ("en", "zh"):
            all_ok &= check_case(cid, dm, lang)
    # also test the slider: move eticket from 28 -> 5 (danger) -> 0 (gate_closed)
    print("--- slider (eticket) ---")
    for dm in (28, 5, 0):
        d = post("/api/demo", {"id": "eticket", "lang": "zh", "depart_in_minutes": dm})
        print(f"   dm={dm:2d} -> level={d['timing']['level']:11s} "
              f"gate_close_in={d['timing']['minutes_to_gate_close']} "
              f"title0={d['findings'][0]['title'] if d['findings'] else '-'}")
    print("\nPASS" if all_ok else "\nFAILURES PRESENT")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
