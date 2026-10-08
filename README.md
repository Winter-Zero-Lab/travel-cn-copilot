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
* If the model is unreachable, the rules still run with a scene hint. The demo never
  blocks on the model.

## Demo

Live URL: _fill in after deploying to Render (see below)_.

Locally:

```bash
git clone <this repo>
cd travel-cn-copilot
uv venv .venv --python 3.12         # or python3 -m venv .venv
uv pip install -r requirements.txt   # or pip install -r requirements.txt
cp .env.example .env                 # then put your LLM_API_KEY in .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
# open http://127.0.0.1:8000
```

`uv pip install pillow` is only needed if you want to regenerate the built-in sample
photos (`tools/make_samples.py`).

## Built-in demo cases

The app ships with five rendered "scenes" — these are the cases translation tools
*literally* cannot solve:

| # | Scene | What breaks with a translator alone |
|---|---|---|
| 1 | Beijing Railway Station (sign) | OCR reads it perfectly. The rule engine knows your train leaves from Beijing *South*. |
| 2 | Self-service ticket machine | The screen is perfectly readable. The rule knows your passport can never work here. |
| 3 | E-ticket on your phone | Every word is translatable. The rule orders the 7 actual steps and warns at 22 min. |
| 4 | Departure board saying 正在检票 | 8 minutes to departure. The rule computes a real countdown. |
| 5 | Hotel reception sign | Translates "passport" but can't tell you they keep the original for 3 minutes. |

The five sample photos are in `web/samples/`; the metadata is `web/samples/samples.json`.

## Configuration

Copy `.env.example` to `.env` and fill in the key. On Render, set the same variables in
the dashboard. **The key is never committed** — `.env` is in `.gitignore` and
`render.yaml` marks `LLM_API_KEY` as `sync: false`.

| Key | Default | Notes |
|---|---|---|
| `LLM_API_KEY` | *(required)* | multimodal model; empty value degrades to rule-only mode |
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
  i18n.py          — translation + AI-answer layer
  main.py          — FastAPI: /api/analyze, /api/recompute, static UI
web/
  index.html, style.css, app.js
  samples/         — five built-in rendered scenes
tools/
  make_samples.py  — regenerate the built-in samples
  regression.py    — five-sample end-to-end check
render.yaml        — Render.com one-click deploy
```

## Deploy (Render Blueprint)

The repo ships `render.yaml`, so Render configures the service automatically:

1. Push to GitHub.
2. Render → **New** → **Blueprint** → connect this repo → Render reads `render.yaml`.
3. Render asks for the `sync: false` variable — paste `LLM_API_KEY` there.
4. Wait ~2 min for `pip install` + build. Health check hits `/api/health`.

> **Demo-day tip:** Render's free tier sleeps after ~15 min idle and the first request
> after sleeping takes 20-50 s to wake up. Open the URL once a few minutes before you
> present, and the demo will be instant. Each click costs one model call; the time
> slider uses `/api/recompute`, which skips the model entirely.

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