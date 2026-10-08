"""End-to-end regression — fires all 5 built-in sample images against /api/analyze.

Run while the dev server is up:
    .venv/bin/python tools/regression.py
"""
import base64, json, sys, time
from datetime import datetime, timedelta
import httpx

URL = "http://127.0.0.1:8000"
SAMPLES = json.load(open("web/samples/samples.json", encoding="utf-8"))


def compute_depart_in_minutes(mins: int) -> str:
    depart = datetime.now() + timedelta(minutes=mins)
    return depart.strftime("%Y-%m-%d %H:%M")


ok = True
for s in SAMPLES:
    img = open(f"web/samples/{s['file']}", "rb").read()
    b64 = base64.b64encode(img).decode()
    trip = dict(s["trip"])
    dim = s.get("depart_in_minutes")
    if dim is not None:
        trip["depart_time"] = compute_depart_in_minutes(dim)
    body = {
        "image": f"data:image/jpeg;base64,{b64}",
        "lang": "en",
        "question": s.get("question", ""),
        **trip,
    }
    t0 = time.time()
    try:
        r = httpx.post(f"{URL}/api/analyze", json=body, timeout=120)
    except Exception as exc:
        print(f"\n!!! {s['id']}: HTTP error {exc}")
        ok = False
        continue
    dt = time.time() - t0
    if r.status_code != 200:
        print(f"\n!!! {s['id']}: http {r.status_code} {r.text[:120]}")
        ok = False
        continue
    j = r.json()
    print(f"\n== {s['id']} ({dt:.1f}s) scene={j['scene']} ({j['scene_label']})")
    if j.get("meta", {}).get("degraded"):
        print("   DEGRADED — model unreachable")
        ok = False
        continue
    t = j['timing']
    print(f"   timing: {t['level']}  depart {t['depart_time']}{' (tomorrow)' if t.get('is_tomorrow') else ''}  "
          f"gate in {t.get('minutes_to_gate_close')} min")
    if not j["findings"]:
        print("   (no findings)")
    for f in j["findings"]:
        print(f"   {f['severity']:8} {f['rule_ref']:18} {f['title']}")
    if j["missing"]:
        for m in j["missing"]:
            print(f"   MISSING  - {m['item']}")
    if j.get("ai_note"):
        print(f"   AI note: {j['ai_note'][:120]}...")
print()
print("ALL OK" if ok else "SOME FAILURES")
sys.exit(0 if ok else 1)