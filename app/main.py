"""FastAPI app: serves the demo UI and the /api/analyze pipeline."""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from datetime import datetime

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import i18n, rules as rules_mod, vision as vision_mod
from .config import CN_TZ, PORT, SAMPLES_DIR, SUPPORTED_LANGS, WEB_DIR
from .llm import LLMError
from .rules import TripContext, evaluate

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("copilot")

app = FastAPI(title="Travel-China Copilot", version="0.1.0", docs_url="/docs")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


_NO_CACHE_EXTS = (".css", ".js", ".html", ".svg", ".json")


@app.middleware("http")
async def no_cache_for_assets(request, call_next):
    """Force browsers to revalidate every CSS/JS/HTML request.

    Prevents the "stuck-on-old-CSS" layout break that happens when a deploy ships
    new styles but the user still has the old ones in cache. ETag/304 still applies,
    so this does NOT cause re-downloads — just re-checks.
    """
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/samples/"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    elif path.endswith(_NO_CACHE_EXTS):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


# ---------------------------------------------------------------------------
# request / response models
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    image: str = ""                      # data URL (base64)
    question: str = ""
    lang: str = "en"
    scene_hint: str = ""                 # fallback scene if the model is unreachable
    city: str | None = None
    planned_station: str | None = None
    train_no: str | None = None
    depart_time: str | None = None       # "HH:MM" or "YYYY-MM-DD HH:MM"
    booked_with: str = "passport"        # passport | chinese_id | other | unknown
    documents: list[str] = Field(default_factory=lambda: ["passport"])
    hotel: str | None = None
    now_override: str | None = None      # demo dial: pretend it is this time
    sample_id: str = ""


SAMPLES: list[dict] = []


def load_samples() -> None:
    global SAMPLES
    path = os.path.join(SAMPLES_DIR, "samples.json")
    if not os.path.exists(path):
        SAMPLES = []
        return
    try:
        with open(path, encoding="utf-8") as f:
            SAMPLES = json.load(f)
    except Exception as exc:  # pragma: no cover
        log.warning("cannot read samples.json: %s", exc)
        SAMPLES = []


# ---------------------------------------------------------------------------
# pipeline
# ---------------------------------------------------------------------------


def _now(now_override: str | None) -> datetime:
    if now_override:
        try:
            return datetime.fromisoformat(now_override.replace("Z", ""))
        except ValueError:
            pass
    return datetime.now(CN_TZ).replace(tzinfo=None)


def _as_data_url(raw: str) -> str:
    if raw.startswith("data:"):
        return raw
    return f"data:image/jpeg;base64,{raw}"


async def run_pipeline(req: AnalyzeRequest) -> dict:
    started = time.time()
    lang = req.lang if req.lang in SUPPORTED_LANGS else "en"
    now = _now(req.now_override)

    trip = TripContext(
        city=req.city, planned_station=req.planned_station, train_no=req.train_no,
        depart_time=req.depart_time, booked_with=req.booked_with or "passport",
        documents=req.documents or [], hotel=req.hotel, now_override=req.now_override,
    )

    stage1_ok = True
    stage1_error = ""
    if req.image:
        context_bits = [b for b in [req.city, req.planned_station, req.train_no] if b]
        try:
            vis = await vision_mod.understand_image(_as_data_url(req.image),
                                                    ", ".join(context_bits))
        except LLMError as exc:
            log.error("stage1 failed: %s", exc)
            stage1_ok = False
            stage1_error = str(exc)[:200]
            vis = {
                "scene": req.scene_hint or "unknown",
                "scene_label_en": "",
                "confidence": 0.0,
                "ocr_text": [],
                "extracted": {},
                "visual_clues": [],
                "traveler_situation": "",
                "needs_human_counter": False,
            }
    else:
        vis = {
            "scene": req.scene_hint or "unknown",
            "scene_label_en": "",
            "confidence": 0.0,
            "ocr_text": [],
            "extracted": {},
            "visual_clues": [],
            "traveler_situation": "",
            "needs_human_counter": False,
        }

    # Stage 2 — rules decide. Always runs, with or without the model.
    result = evaluate(vis, trip, now)
    payload = i18n.to_payload(result, vis, lang)

    # Stage 3 — expression (translation + short answer to the traveller's question)
    try:
        payload = await i18n.express(payload, lang, req.question)
    except Exception as exc:  # defensive: expression must never break the demo
        log.error("stage3 failed: %s", exc)
        payload["ai_note"] = ""

    payload["meta"] = {
        "stage1_model": stage1_ok,
        "stage1_error": stage1_error,
        "degraded": not stage1_ok,
        "model": os.getenv("LLM_MODEL", "glm-5.3-flash"),
        "elapsed_ms": int((time.time() - started) * 1000),
        "scene_from": "model" if stage1_ok else ("hint" if req.scene_hint else "none"),
        "server_time": now.strftime("%Y-%m-%d %H:%M"),
    }
    return payload


class RecomputeRequest(BaseModel):
    vision: dict
    question: str = ""
    lang: str = "en"
    city: str | None = None
    planned_station: str | None = None
    train_no: str | None = None
    depart_time: str | None = None
    booked_with: str = "passport"
    documents: list[str] = Field(default_factory=lambda: ["passport"])
    hotel: str | None = None
    now_override: str | None = None
    previous_note: str = ""
    previous_translation: str = ""


@app.post("/api/recompute")
async def recompute(req: RecomputeRequest) -> JSONResponse:
    """Stage-2-only re-evaluation.  No model call — used by the demo time slider."""
    started = time.time()
    lang = req.lang if req.lang in SUPPORTED_LANGS else "en"
    now = _now(req.now_override)
    trip = TripContext(
        city=req.city, planned_station=req.planned_station, train_no=req.train_no,
        depart_time=req.depart_time, booked_with=req.booked_with or "passport",
        documents=req.documents or [], hotel=req.hotel, now_override=req.now_override,
    )
    vision = req.vision or {
        "scene": "unknown", "scene_label_en": "", "confidence": 0,
        "ocr_text": [], "extracted": {}, "visual_clues": [],
        "traveler_situation": "", "needs_human_counter": False,
    }
    result = evaluate(vision, trip, now)
    payload = i18n.to_payload(result, vision, lang)
    # translate rule output to traveller language, no LLM generated note
    try:
        payload = await i18n.express(payload, lang, req.question, with_ai_note=False)
    except Exception as exc:
        log.error("recompute express failed: %s", exc)
    payload["ai_note"] = req.previous_note
    if req.previous_translation:
        payload["translation"] = req.previous_translation
    payload["meta"] = {
        "stage1_model": False, "stage1_error": "",
        "degraded": False, "model": "rule-only",
        "elapsed_ms": int((time.time() - started) * 1000),
        "scene_from": "cache",
        "server_time": now.strftime("%Y-%m-%d %H:%M"),
    }
    return JSONResponse(payload)


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest) -> JSONResponse:
    try:
        return JSONResponse(await run_pipeline(req))
    except Exception as exc:  # pragma: no cover
        log.exception("analyze failed")
        raise HTTPException(status_code=500, detail=str(exc)[:300]) from exc


@app.post("/api/analyze/upload")
async def analyze_upload(
    image: UploadFile = File(...),
    question: str = Form(""),
    lang: str = Form("en"),
    scene_hint: str = Form(""),
    city: str | None = Form(None),
    planned_station: str | None = Form(None),
    train_no: str | None = Form(None),
    depart_time: str | None = Form(None),
    booked_with: str = Form("passport"),
    documents: str = Form("passport"),
    hotel: str | None = Form(None),
    now_override: str | None = Form(None),
    sample_id: str = Form(""),
) -> JSONResponse:
    raw = await image.read()
    b64 = base64.b64encode(raw).decode()
    req = AnalyzeRequest(
        image=b64, question=question, lang=lang, scene_hint=scene_hint, city=city,
        planned_station=planned_station, train_no=train_no, depart_time=depart_time,
        booked_with=booked_with,
        documents=[d.strip() for d in documents.split(",") if d.strip()],
        hotel=hotel, now_override=now_override, sample_id=sample_id,
    )
    return JSONResponse(await run_pipeline(req))


@app.get("/api/samples")
async def samples() -> JSONResponse:
    return JSONResponse({"samples": SAMPLES})


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "time": datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")}


# ---------------------------------------------------------------------------
# static UI
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


@app.on_event("startup")
async def on_startup() -> None:
    load_samples()
    log.info("server time: %s", datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M:%S %Z"))


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
