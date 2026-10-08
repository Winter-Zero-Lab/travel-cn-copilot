"""Baked demo cases — the offline showcase for the deployed app.

Each entry is what the multimodal model *would* perceive (the `vision` dict) plus
the traveller's trip profile and a pre-written answer note in both languages. The
rule engine (app.rules.evaluate) still runs for real — only the model's
perception + free-text generation are replaced by these baked values, so the
deployed demo works with **no LLM API key**.

To add a case: drop a photo in web/samples/, append an entry here, and it shows up
in the UI automatically (the front-end renders whatever ids it finds).
"""
from __future__ import annotations

from typing import Any

# vision = the structured perception a model would return for the sample image.
# trip   = the traveller's profile (as filled in the trip panel).
# ai_note_en / ai_note_zh = the short answer the expression layer would write.
DEMO_CASES: dict[str, dict[str, Any]] = {
    "wrong_station": {
        "scene": "rail_entrance",
        "trip": {
            "city": "北京", "planned_station": "北京南站", "train_no": "G7",
            "booked_with": "passport", "documents": ["passport"],
        },
        "vision": {
            "scene": "rail_entrance",
            "scene_label_en": "Station entrance / ID check",
            "confidence": 0.96,
            "ocr_text": [
                "北京站", "Beijing Railway Station", "进站口 Entrance",
                "凭购票时所用证件原件进站", "实名制验证  安全检查",
            ],
            "visual_clues": ["Blue station signage", "Right-pointing entrance arrow"],
            "traveler_situation": (
                "A tourist stands at a station entrance sign reading 北京站, "
                "holding a phone with a booking for G7."
            ),
            "needs_human_counter": False,
            "extracted": {
                "station_name_on_site": "北京站",
                "entrance_name_on_site": "进站口",
                "is_departure_side": True,
            },
        },
        "ai_note_en": (
            "You're at 北京站, but your G7 to 上海虹桥 leaves from 北京南站 — a "
            "different station about 40 minutes away by metro. Head to 北京南站 "
            "now; you don't need to buy anything here."
        ),
        "ai_note_zh": (
            "你此刻在北京站，但你的 G7（开往上海虹桥）是从北京南站发车——那是另一个站，"
            "坐地铁大约要 40 分钟。现在就去北京南站；在这里不用买任何东西。"
        ),
    },

    "kiosk": {
        "scene": "rail_kiosk",
        "trip": {
            "city": "北京", "planned_station": "北京南站", "train_no": "G7",
            "booked_with": "passport", "documents": ["passport"],
        },
        "vision": {
            "scene": "rail_kiosk",
            "scene_label_en": "Self-service ticket machine",
            "confidence": 0.93,
            "ocr_text": [
                "自助售取票机", "请使用二代身份证",
                "Please insert your 2nd-gen ID card",
                "持护照购票的旅客请到人工售票窗口办理",
            ],
            "visual_clues": ["Red error box on screen", "Touch-screen kiosk"],
            "traveler_situation": (
                "A tourist at a self-service ticket machine; the screen shows a red "
                "error and a message about a 2nd-gen ID card."
            ),
            "needs_human_counter": True,
            "extracted": {"machine_error": "请使用二代身份证"},
        },
        "ai_note_en": (
            "This machine can't read your passport — it only accepts Chinese ID "
            "cards. Walk to the 人工售票窗口 (staffed counter) with your passport. "
            "Chances are you don't need paper at all: your passport is your e-ticket."
        ),
        "ai_note_zh": (
            "这台机器读不了你的护照——它只认二代身份证。拿护照去人工售票窗口办理即可。"
            "而且你多半根本不需要纸质票：护照就是你的电子客票。"
        ),
    },

    "eticket": {
        "scene": "rail_ticket",
        "trip": {
            "city": "北京", "planned_station": "北京南站", "train_no": "G7",
            "booked_with": "passport", "documents": ["passport"],
        },
        "vision": {
            "scene": "rail_ticket",
            "scene_label_en": "Train ticket / booking",
            "confidence": 0.98,
            "ocr_text": [
                "行程信息提示", "G7", "北京南", "上海虹桥", "09:00 开",
                "检票口 B12", "05车 12A", "购票证件 护照 P1234567",
                "实行电子客票，凭购票时所用证件原件进站乘车",
            ],
            "visual_clues": ["Phone screenshot of e-ticket", "Blue header bar"],
            "traveler_situation": (
                "A tourist looking at their e-ticket on a phone; G7, 北京南→上海虹桥, "
                "gate B12, seat 05车12A, booked with passport."
            ),
            "needs_human_counter": False,
            "extracted": {
                "train_no": "G7", "from_station": "北京南", "to_station": "上海虹桥",
                "depart_date": "2026-10-08", "depart_time": "09:00",
                "gate": "B12", "carriage": "05", "seat": "12A",
                "id_type_on_ticket": "passport",
            },
        },
        "ai_note_en": (
            "Your G7 to 上海虹桥 leaves from 北京南站, gate B12, seat 05车12A, booked "
            "with your passport. Go: entrance → real-name check (staffed lane) → "
            "security → gate B12 → platform. Your passport is your ticket — no paper "
            "needed unless you want a reimbursement invoice."
        ),
        "ai_note_zh": (
            "你的 G7（开往上海虹桥）从北京南站 B12 检票口发车，座位 05车12A，用护照购买。"
            "流程是：进站口 → 实名验证（走人工通道）→ 安检 → B12 检票 → 站台。"
            "护照就是车票——除非要报销凭证，否则不用取纸质票。"
        ),
    },

    "board": {
        "scene": "rail_waiting_hall",
        "trip": {
            "city": "北京", "planned_station": "北京南站", "train_no": "G7",
            "booked_with": "passport", "documents": ["passport"],
        },
        "vision": {
            "scene": "rail_waiting_hall",
            "scene_label_en": "Waiting hall / departure board",
            "confidence": 0.95,
            "ocr_text": [
                "列车时刻表 Departures", "G7", "上海虹桥", "09:00", "B12",
                "正在检票", "停止检票时间为开车前5分钟",
            ],
            "visual_clues": ["Yellow departure board", "Multiple rows of trains"],
            "traveler_situation": (
                "A tourist at the departure board; G7 to 上海虹桥 shows status "
                "正在检票 at gate B12."
            ),
            "needs_human_counter": False,
            "extracted": {
                "train_no": "G7", "to_station": "上海虹桥", "depart_time": "09:00",
                "gate": "B12", "status": "正在检票",
            },
        },
        "ai_note_en": (
            "G7 to 上海虹桥 is now boarding at gate B12. Use the wide/staffed lane and "
            "show your passport — don't try the ID-only gates. Follow the colour "
            "marker on the platform for car 05."
        ),
        "ai_note_zh": (
            "开往上海虹桥的 G7 正在 B12 检票口检票。走宽通道/人工通道，出示护照——"
            "别去只认身份证的闸机。到站台后按颜色地标找到 05 车。"
        ),
    },

    "hotel": {
        "scene": "hotel_checkin",
        "trip": {
            "city": "上海", "planned_station": "", "train_no": "",
            "booked_with": "passport", "documents": ["passport"],
        },
        "vision": {
            "scene": "hotel_checkin",
            "scene_label_en": "Hotel check-in",
            "confidence": 0.90,
            "ocr_text": [
                "办理入住登记 Check-in Registration", "请出示护照原件",
                "Original passport required — no photocopies",
                "入住时间 14:00 以后  退房时间 12:00 以前",
                "押金可使用现金或银行卡预授权", "前台 Front Desk",
            ],
            "visual_clues": ["Hotel front-desk sign", "Reception counter"],
            "traveler_situation": (
                "A tourist at a hotel front desk; the sign asks for the original "
                "passport and mentions a deposit."
            ),
            "needs_human_counter": True,
            "extracted": {},
        },
        "ai_note_en": (
            "Hand over your original passport at the front desk — it's a legal "
            "requirement and takes about 3 minutes. They'll also take a deposit "
            "(card pre-auth or cash). Keep the receipt."
        ),
        "ai_note_zh": (
            "在前台交验护照原件——这是法律要求，大约需要 3 分钟。酒店还会收押金"
            "（银行卡预授权或现金），记得保留收据。"
        ),
    },
}


def get_case(case_id: str) -> dict | None:
    return DEMO_CASES.get(case_id)


def case_ids() -> list[str]:
    return list(DEMO_CASES.keys())
