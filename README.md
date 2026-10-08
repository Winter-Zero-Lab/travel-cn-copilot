# Travel-China Copilot · 钉子头

> An on-site procedure copilot for foreign travellers in China.
> Snap a ticket, a kiosk, a sign or a hotel desk; get the next action.

## What it solves

A foreign traveller standing in front of a Chinese ticket kiosk, a high-speed-rail gate,
a hotel front desk or a busy departure board almost never fails because of **vocabulary**.
They fail because of **procedure**: which lane works with a passport, how many minutes
before departure the gate closes, whether the train leaves from *this* station, whether
the front desk really needs the original passport.

|  | 普通翻译 / OCR App | Travel-China Copilot |
|---|---|---|
| Translates the words on screen | ✅ | ✅ (multimodal model) |
| Knows **which station** in the city you need | ❌ | ✅ rule engine (RAIL-PLACE-01) |
| Tells you the machine **cannot** work for you | ❌ | ✅ (RAIL-KIOSK-01) |
| Computes **real gate close** countdown | ❌ | ✅ (RAIL-TIME-01, configurable per hub) |
| Says whether you are at the **wrong entrance** | ❌ | ✅ (RAIL-PLACE-02) |
| Generates a Chinese sentence you can show staff | ❌ | ✅ (rule-attached, with pinyin) |

## Architecture

```
photo + trip context ──▶ multimodal model (glm-5.3-flash)
                              │
                              ▼  structured perception
                         rule engine (deterministic) ──→ critical/warn/info findings
                              │                       ordered procedure steps
                              │                       Chinese phrases
                              ▼
                     expression layer (LLM) ──────── translation + short AI note
                              │
                              ▼
                       JSON to the browser
```

* **Perception** is done by the multimodal model — it sees the picture, names the scene,
  transcribes what is literally written there. The model is forbidden from deciding what
  the traveller should do.
* **Decision** is done by a deterministic rule engine (`app/rules.py`). Every rule has
  a stable id (e.g. `RAIL-KIOSK-01`) that the judges can audit and the UI badges with
  `RULE` next to model-generated text with `MODEL`.
* If the model is unreachable — or simply **not configured** — the rules still run.
  The five built-in demo cases are **baked into code** (`app/demo_cases.py`) and served
  by `/api/demo`, which runs the rule engine + a static Chinese translation table with
  **zero LLM calls**. This is what powers the deployed demo with no API key at all.

## Demo

Live URL: _fill in after deploying to Render (see below)_.

**The demo needs no LLM API key.** The five built-in cases are baked into code and
served by `/api/demo`, which runs the deterministic rule engine plus a static Chinese
translation table — zero network calls to any model. You get the full experience
(verdicts, ordered steps, the "show this to staff" phrases, the countdown, and the
time-slider) entirely offline.

Locally:

```bash
git clone <this repo>
cd travel-cn-copilot
uv venv .venv --python 3.12         # or python3 -m venv .venv
uv pip install -r requirements.txt   # or pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
# open http://127.0.0.1:8000
```

Optional: copy `.env.example` to `.env` and add `LLM_API_KEY` only if you want the
live "upload your own photo" path to use the multimodal model. Without it, everything
still works via the baked cases.

`uv pip install pillow` is only needed if you want to regenerate the built-in sample
photos (`tools/make_samples.py`).

## Built-in demo cases

The app ships with five rendered "scenes" — these are the cases translation tools
*literally* cannot solve. Their perception output (what a model would "see") and a
pre-written answer note in both languages are baked into `app/demo_cases.py`, so the
deployed demo is fully self-contained:

| # | Scene | What breaks with a translator alone |
|---|---|---|
| 1 | Beijing Railway Station (sign) | OCR reads it perfectly. The rule engine knows your train leaves from Beijing *South*. |
| 2 | Self-service ticket machine | The screen is perfectly readable. The rule knows your passport can never work here. |
| 3 | E-ticket on your phone | Every word is translatable. The rule orders the 7 actual steps and warns at 22 min. |
| 4 | Departure board saying 正在检票 | 8 minutes to departure. The rule computes a real countdown. |
| 5 | Hotel reception sign | Translates "passport" but can't tell you they keep the original for 3 minutes. |

The five sample photos are in `web/samples/`; the metadata is `web/samples/samples.json`.
To add a case, drop a photo, add an entry to `app/demo_cases.py` — it appears in the UI
automatically.

## Configuration

**No configuration is required to run the demo** — the built-in cases are offline. If you
want the live "upload your own photo" path to call a multimodal model, copy
`.env.example` to `.env` and add `LLM_API_KEY`. On Render, the same variable is optional
in the dashboard. **The key is never committed** — `.env` is in `.gitignore` and
`render.yaml` marks `LLM_API_KEY` as `sync: false`. A placeholder or empty value is
treated as "offline mode".

| Key | Default | Notes |
|---|---|---|
| `LLM_API_KEY` | *(empty → offline demo)* | multimodal model; empty/placeholder → baked cases run with zero model calls |
| `LLM_BASE_URL` | `https://www.micuapi.ai/v1` | OpenAI-compatible |
| `LLM_MODEL` | `glm-5.3-flash` | any multimodal model that supports `image_url` content with `{"type":"text","text":...}` |
| `LLM_TIMEOUT` | `60` | seconds |

## Files

```
app/
  config.py        — env, hub list, gate-close thresholds, confusable stations
  llm.py           — OpenAI-compatible client + JSON extraction
  vision.py        — scene taxonomy + structured perception prompt
  rules.py         — deterministic rule engine (the trustworthy half)
  i18n.py          — translation + AI-answer layer (with offline ZH dictionary)
  demo_cases.py    — baked perception + answer notes for the 5 offline demo cases
  main.py          — FastAPI: /api/analyze, /api/demo, /api/recompute, static UI
web/
  index.html, style.css, app.js
  samples/         — five built-in rendered scenes
tools/
  make_samples.py  — regenerate the built-in samples
  regression.py    — five-sample end-to-end check
  verify_i18n.py    — regression for the zh-translation fix
  verify_demo_offline.py — asserts the demo is fully offline (no LLM calls)
render.yaml        — Render.com one-click deploy
```

## Deploy (Render Blueprint)

The repo ships `render.yaml`, so Render configures the service automatically:

1. Push to GitHub.
2. Render → **New** → **Blueprint** → connect this repo → Render reads `render.yaml`.
3. **No key needed.** Leave `LLM_API_KEY` unset and the demo runs fully offline from the
   baked cases. Optionally paste a key if you want live photo analysis.
4. Wait ~2 min for `pip install` + build. Health check hits `/api/health`.

> **Demo-day tip:** Render's free tier sleeps after ~15 min idle and the first request
> after sleeping takes 20-50 s to wake up. Open the URL once a few minutes before you
> present, and the demo will be instant. The built-in cases (and the time slider) make
> **zero** model calls; only a real uploaded photo uses the model, and only if a key is set.

## Why this design?

The judge's brief asks for three things:

1. **A focused vertical slice** instead of "every on-site flow". We chose the
   full high-speed-rail departure chain (entrance → kiosk → gate → platform) plus
   hotel check-in.
2. **Visible AI vs rule split**. Every panel in the UI carries either a `RULE` badge
   (deterministic, audit-kept) or a `MODEL` badge (multimodal perception / language
   polish). Rule findings are never overridden by the model.
3. **Cases translation apps literally cannot solve**. The five built-in scenes
   (plus the live photo capture) are framed this way: every finding shows a
   *"Why a normal translation app can't help here"* sentence.