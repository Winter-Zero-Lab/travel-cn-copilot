"""Configuration for Travel-China Copilot (team 钉子头).

Secrets are NEVER committed. The API key comes from the environment
(local `.env` file, or the Render dashboard for deployment).
"""
from __future__ import annotations

import os
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_dotenv(path: str | None = None) -> None:
    """Minimal .env loader (no extra dependency) — existing env vars win."""
    path = path or os.path.join(BASE_DIR, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()

# ---------------------------------------------------------------------------
# Multimodal LLM (glm-5.3-flash via micuapi.ai, OpenAI-compatible)
# ---------------------------------------------------------------------------
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://www.micuapi.ai/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "glm-5.3-flash")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))

# ---------------------------------------------------------------------------
# Locale / timezone
# ---------------------------------------------------------------------------
CN_TZ = ZoneInfo("Asia/Shanghai")
PORT = int(os.getenv("PORT", "8000"))

WEB_DIR = os.path.join(BASE_DIR, "web")
SAMPLES_DIR = os.path.join(WEB_DIR, "samples")

# ---------------------------------------------------------------------------
# Rule constants — these are the deterministic thresholds the judges can audit.
# Every number here is referenced by a rule id in rules.py, never by the model.
# ---------------------------------------------------------------------------
RULES = {
    # Boarding gates close BEFORE departure. Large hub stations close earlier.
    "gate_close_minutes_default": 3,
    "gate_close_minutes_hub": 5,
    "hub_stations": {
        "北京南", "北京西", "北京北", "上海虹桥", "上海南", "广州南",
        "深圳北", "杭州东", "南京南", "武汉", "西安北", "成都东", "重庆北",
    },
    # Recommended arrival buffer: security + real-name check + walking.
    "arrive_buffer_minutes": 45,
    "arrive_buffer_minutes_hub": 60,
    # Risk ladder (minutes remaining until gate close).
    "risk_warn_minutes": 25,
    "risk_danger_minutes": 12,
    # Real-name verification channel opens 24h/7 but manual counters have queues.
    "manual_counter_queue_minutes": 15,
}

# Stations that inbound travellers most often confuse inside the same city.
CONFUSABLE_STATIONS = {
    "北京": ["北京站", "北京南站", "北京西站", "北京北站", "北京朝阳站", "清河站"],
    "上海": ["上海站", "上海南站", "上海虹桥站", "上海西站"],
    "广州": ["广州站", "广州南站", "广州东站", "广州北站"],
    "西安": ["西安站", "西安北站", "西安南站"],
    "成都": ["成都站", "成都东站", "成都南站", "成都西站"],
    "杭州": ["杭州站", "杭州东站", "杭州西站", "杭州南站"],
    "深圳": ["深圳站", "深圳北站", "深圳东站", "福田站"],
    "南京": ["南京站", "南京南站"],
    "武汉": ["武昌站", "汉口站", "武汉站"],
}

SUPPORTED_LANGS = ["en", "zh", "ja", "ko", "es", "fr", "de"]
