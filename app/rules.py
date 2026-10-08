"""Stage 2 — deterministic rule engine.  ★ The trustworthy half of the system. ★

Design contract (what we show the judges):
  * The MODEL does perception: which scene is this, what does the sign/ticket say.
  * The RULES do decisions: which document is mandatory, how late is too late,
    what is the correct order of actions, is the traveller at the wrong place.
  * A rule output is never overridden by the model. If the model and a rule
    disagree, the rule wins and we say so in the UI (`source: "rule"`).

Every rule carries:
  rule_ref      - stable id, e.g. RAIL-KIOSK-01
  severity      - critical | warn | info
  why_translation_fails - the sentence that differentiates us from OCR/translate apps
  zh_phrase     - ready-to-show Chinese for the staff member in front of the traveller
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .config import CONFUSABLE_STATIONS, RULES

# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class TripContext:
    city: str | None = None
    planned_station: str | None = None
    train_no: str | None = None
    depart_time: str | None = None
    booked_with: str = "passport"          # passport | chinese_id | other | unknown
    documents: list[str] = field(default_factory=list)
    hotel: str | None = None
    now_override: str | None = None


@dataclass
class Finding:
    rule_ref: str
    severity: str
    title: str
    detail: str
    why_translation_fails: str
    zh_phrase: str = ""
    zh_pinyin: str = ""
    source: str = "rule"


@dataclass
class Step:
    order: int
    action: str
    detail: str
    rule_ref: str
    source: str = "rule"


@dataclass
class Timing:
    has_departure: bool
    depart_time: str | None
    now: str
    minutes_to_departure: int | None
    gate_close_time: str | None
    minutes_to_gate_close: int | None
    level: str                     # ok | warn | danger | gate_closed | departed
    gate_close_rule: str | None
    arrive_by: str | None
    arrive_rule: str | None
    depart_date: str | None = None    # YYYY-MM-DD for clarity
    is_tomorrow: bool = False


@dataclass
class RuleResult:
    scene: str
    scene_label: str
    timing: Timing
    steps: list[Step]
    findings: list[Finding]
    missing: list[dict[str, str]]
    facts_used: list[dict[str, str]]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_HUBS = RULES["hub_stations"]


def _norm_station(name: str | None) -> str:
    """Strip suffixes that aren't part of the real station name.
    We do NOT strip the single-character suffix "站" — 北京站 IS the name.
    """
    if not name:
        return ""
    s = str(name).strip()
    s = re.sub(r"\s+", "", s)
    for suffix in ("火车站", "高铁站", "动车所"):
        s = s.replace(suffix, "")
    en = {
        "BeijingSouth": "北京南站", "BeijingWest": "北京西站", "BeijingNorth": "北京北站",
        "ShanghaiHongqiao": "上海虹桥站", "ShanghaiSouth": "上海南站",
        "GuangzhouSouth": "广州南站", "Xi'anNorth": "西安北站", "XianNorth": "西安北站",
        "ChengduEast": "成都东站", "HangzhouEast": "杭州东站", "NanjingSouth": "南京南站",
        "ShenzhenNorth": "深圳北站", "ChongqingNorth": "重庆北站",
    }
    return en.get(s, s)


def _aliases(name: str | None) -> list[str]:
    """Both forms — with and without the trailing 站 — for membership checks."""
    n = _norm_station(name)
    out = [n]
    if n.endswith("站") and len(n) > 2:
        out.append(n[:-1])
    elif len(n) >= 2 and not n.endswith("站"):
        out.append(n + "站")
    return out


def _is_hub(station: str | None, train_no: str | None = None) -> bool:
    for a in _aliases(station):
        if a in _HUBS:
            return True
    return False


def _parse_dt(value: str | None, now: datetime) -> datetime | None:
    if not value:
        return None
    v = str(value).strip().replace("/", "-")
    v = v.replace("T", " ")
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})[\s]+(\d{1,2}):(\d{2})", v)
    if m:
        try:
            return datetime(*[int(x) for x in m.groups()])
        except ValueError:
            return None
    m = re.search(r"^(\d{1,2}):(\d{2})$", v)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        cand = now.replace(hour=h, minute=mi, second=0, microsecond=0)
        # if that moment is far in the past, assume the next day
        if cand < now - timedelta(hours=6):
            cand += timedelta(days=1)
        return cand
    return None


def _fmt(dt: datetime | None) -> str | None:
    return dt.strftime("%H:%M") if dt else None


def _same_city(a: str, b: str) -> bool:
    for station in (a, b):
        if not station:
            return False
    a_aliases, b_aliases = set(_aliases(a)), set(_aliases(b))
    if a_aliases & b_aliases:
        return False
    for city, stations in CONFUSABLE_STATIONS.items():
        na = set()
        for s in stations:
            na.update(_aliases(s))
        if a_aliases & na and b_aliases & na:
            return True
    return False


# ---------------------------------------------------------------------------
# timing rules (RAIL-TIME-*)
# ---------------------------------------------------------------------------


def build_timing(depart: datetime | None, now: datetime, station: str | None) -> Timing:
    if not depart:
        return Timing(
            has_departure=False, depart_time=None, now=_fmt(now),
            minutes_to_departure=None, gate_close_time=None,
            minutes_to_gate_close=None, level="ok",
            gate_close_rule=None, arrive_by=None, arrive_rule=None,
        )
    hub = _is_hub(station)
    close_min = RULES["gate_close_minutes_hub"] if hub else RULES["gate_close_minutes_default"]
    buffer = RULES["arrive_buffer_minutes_hub"] if hub else RULES["arrive_buffer_minutes"]
    gate_close = depart - timedelta(minutes=close_min)
    mins_dep = int((depart - now).total_seconds() // 60)
    mins_close = int((gate_close - now).total_seconds() // 60)
    if mins_dep < 0:
        level = "departed"
    elif mins_close <= 0:
        level = "gate_closed"
    elif mins_close <= RULES["risk_danger_minutes"]:
        level = "danger"
    elif mins_close <= RULES["risk_warn_minutes"]:
        level = "warn"
    else:
        level = "ok"
    arrive_by = depart - timedelta(minutes=buffer)
    is_tomorrow = depart.date() > now.date()
    return Timing(
        has_departure=True,
        depart_time=_fmt(depart),
        now=_fmt(now),
        minutes_to_departure=mins_dep,
        gate_close_time=_fmt(gate_close),
        minutes_to_gate_close=mins_close,
        level=level,
        gate_close_rule=f"RAIL-TIME-01: gates close {close_min} min before departure"
                        + (" (hub station)" if hub else ""),
        arrive_by=_fmt(arrive_by),
        arrive_rule=f"RAIL-TIME-02: arrive by {_fmt(arrive_by)} "
                    f"({buffer} min buffer for security + ID check)",
        depart_date=depart.strftime("%Y-%m-%d"),
        is_tomorrow=is_tomorrow,
    )


# ---------------------------------------------------------------------------
# document rules (DOC-*)
# ---------------------------------------------------------------------------

DOC_LABEL = {
    "passport": "passport (original)",
    "chinese_id": "Chinese ID card",
    "visa": "visa / entry stamp page",
    "booking_qr": "booking QR code",
    "cash": "cash",
    "card": "bank card",
}


def document_findings(trip: TripContext, extracted: dict[str, Any]) -> list[Finding]:
    out: list[Finding] = []
    booked = trip.booked_with or "unknown"
    id_on_ticket = extracted.get("id_type_on_ticket")
    docs = {d.lower() for d in (trip.documents or [])}

    if booked == "passport" or id_on_ticket == "passport":
        if "passport" not in docs:
            out.append(Finding(
                rule_ref="DOC-01",
                severity="critical",
                title="You need the ORIGINAL passport — not a photo or photocopy",
                detail=("Your ticket was booked with a passport. Chinese railway and hotel "
                        "systems read the passport chip / number at the counter; a photo, "
                        "screenshot or photocopy will be refused."),
                why_translation_fails=("A translation app will happily translate the word "
                                       "\"证件\" as \"ID\" — it cannot know that YOUR booking "
                                       "was made with a passport and that only the physical "
                                       "document is accepted here."),
                zh_phrase="我用护照买的票，这是我的护照原件。",
                zh_pinyin="Wǒ yòng hùzhào mǎi de piào, zhè shì wǒ de hùzhào yuánjiàn.",
            ))
        else:
            out.append(Finding(
                rule_ref="DOC-01",
                severity="info",
                title="Carry the passport in your hand, not in your suitcase",
                detail=("You will present it at: security/real-name check, the manual counter "
                        "if needed, the ticket gate, and possibly onboard. Keep it reachable."),
                why_translation_fails="",
                zh_phrase="这是我的护照。",
                zh_pinyin="Zhè shì wǒ de hùzhào.",
            ))

    if booked == "chinese_id" and "chinese_id" not in docs:
        out.append(Finding(
            rule_ref="DOC-02",
            severity="critical",
            title="Ticket was booked with a Chinese ID — you must present that same ID",
            detail="Chinese railway requires the document used at purchase to match the traveler.",
            why_translation_fails=("The ticket text never lists which document you used; "
                                   "the rule engine compares it with your trip profile."),
            zh_phrase="这张票是用身份证买的。",
            zh_pinyin="Zhè zhāng piào shì yòng shēnfènzhèng mǎi de.",
        ))
    return out


# ---------------------------------------------------------------------------
# per-scene rules
# ---------------------------------------------------------------------------

EXIT_WORDS = ("出站", "出口", "到达", "Exit", "Arrivals", "接站")


def scene_findings(scene: str, extracted: dict[str, Any], trip: TripContext,
                   timing: Timing) -> list[Finding]:
    out: list[Finding] = []
    planned = _norm_station(trip.planned_station) or _norm_station(extracted.get("from_station"))
    on_site = _norm_station(extracted.get("station_name_on_site"))

    # --- RAIL-PLACE-01: wrong station in the same city -----------------------
    if on_site and planned and on_site != planned and _same_city(on_site, planned):
        out.append(Finding(
            rule_ref="RAIL-PLACE-01",
            severity="critical",
            title=f"You are at the WRONG station: this is {on_site}, your train leaves from {planned}",
            detail=(f"Both stations are in the same city and both are common. {on_site} and "
                    f"{planned} can be 30-60 minutes apart by metro. Leave now and check the "
                    f"transport mode before you move."),
            why_translation_fails=("A translation app reads \"北京站\" correctly as \"Beijing "
                                   "Railway Station\" — and that is exactly the trap. Without "
                                   "your itinerary, nothing tells you that your train does not "
                                   "depart from here."),
            zh_phrase=f"我要去{planned}，请问怎么走最快？",
            zh_pinyin=f"Wǒ yào qù {planned}, qǐngwèn zěnme zǒu zuì kuài?",
        ))

    # --- RAIL-PLACE-02: standing on the arrivals/exit side -------------------
    text_blob = " ".join([
        str(extracted.get("entrance_name_on_site") or ""),
        " ".join(extracted.get("_ocr", []) or []),
    ]) if isinstance(extracted.get("_ocr"), list) else str(extracted.get("entrance_name_on_site") or "")
    if any(w in text_blob for w in EXIT_WORDS) and extracted.get("is_departure_side") is False:
        out.append(Finding(
            rule_ref="RAIL-PLACE-02",
            severity="warn",
            title="This is the EXIT / arrivals side, not the departure entrance",
            detail=("Chinese stations separate inbound and outbound flows. Walk around to the "
                    "signed 进站口 (departure entrance) — do not try to enter through here."),
            why_translation_fails=("\"出站口\" and \"进站口\" differ by one character and both "
                                   "translate to something like \"station entrance/ exit\". "
                                   "Direction is a procedure rule, not a vocabulary problem."),
            zh_phrase="请问进站口在哪里？",
            zh_pinyin="Qǐngwèn jìnzhàn kǒu zài nǎlǐ?",
        ))

    if scene == "rail_kiosk":
        out.append(Finding(
            rule_ref="RAIL-KIOSK-01",
            severity="critical",
            title="This machine cannot read a passport — go to the staffed counter",
            detail=("Most self-service ticket machines at Chinese stations only read a Chinese "
                    "ID card (二代身份证). Foreign passports are not supported. Take your "
                    "passport to the 人工售票窗口 / 服务台 (staffed counter)."),
            why_translation_fails=("The machine shows a perfectly readable message — often just "
                                   "\"请使用二代身份证\". Translating it does not help: it does "
                                   "not tell you the machine is impossible for you, nor which "
                                   "counter to walk to, nor that you may not need a paper "
                                   "ticket at all."),
            zh_phrase="我是外国人，用护照买票，这台机器用不了，请问去哪个窗口？",
            zh_pinyin="Wǒ shì wàiguórén, yòng hùzhào mǎi piào, zhè tái jīqì yòng bù liǎo, "
                      "qǐngwèn qù nǎge chuāngkǒu?",
        ))
        out.append(Finding(
            rule_ref="RAIL-KIOSK-02",
            severity="info",
            title="You probably do not need a paper ticket at all",
            detail=("China's railway is fully e-ticket (电子客票): your passport IS your ticket. "
                    "You can walk straight into security and the gate with it. Only get paper "
                    "if you need a reimbursement invoice (报销凭证)."),
            why_translation_fails=("Nothing on the machine says \"you may not need me\". This is "
                                   "a process fact, not text on the screen."),
            zh_phrase="请问报销凭证在哪里打印？",
            zh_pinyin="Qǐngwèn bàoxiāo píngzhèng zài nǎlǐ dǎyìn?",
        ))
        if extracted.get("machine_error"):
            out.append(Finding(
                rule_ref="RAIL-KIOSK-03",
                severity="warn",
                title=f"Machine message: \"{extracted['machine_error']}\"",
                detail="Do not keep retrying the machine — repeated failures do not clear the block.",
                why_translation_fails="",
            ))

    if scene in ("rail_gate", "rail_waiting_hall", "rail_ticket"):
        out.append(Finding(
            rule_ref="RAIL-GATE-01",
            severity="info",
            title="Passport tickets: use the WIDE lane / staffed lane, not the ID-only lane",
            detail=("Automatic gates with a card reader are built for Chinese ID cards. With a "
                    "passport, use the 人工通道 (staffed lane) or the wide lane and show your "
                    "passport to the attendant."),
            why_translation_fails=("The sign \"凭购票时所用证件原件检票\" translates fine, but "
                                   "does not say which physical lane your document works in. "
                                   "Travellers lose 5-10 minutes in the wrong lane."),
            zh_phrase="我用护照，请问走哪个通道？",
            zh_pinyin="Wǒ yòng hùzhào, qǐngwèn zǒu nǎge tōngdào?",
        ))
        out.append(Finding(
            rule_ref="RAIL-GATE-02",
            severity="info",
            title="Check the big screen — the check-in gate can change",
            detail=("The gate printed on your ticket (e.g. B12) is provisional. The departure "
                    "board is authoritative and usually confirms the gate ~15-30 min before "
                    "departure."),
            why_translation_fails="",
            zh_phrase="请问这个检票口是对的吗？",
            zh_pinyin="Qǐngwèn zhège jiǎnpiào kǒu shì duì de ma?",
        ))

    if scene == "rail_platform":
        out.append(Finding(
            rule_ref="RAIL-BOARD-01",
            severity="warn",
            title="On a doubled (16-car) train, car 1-8 and 9-16 are NOT connected",
            detail=("If your carriage number is above 8 you cannot walk through from car 8. "
                    "Match the coloured ground marker on the platform to the colour on your "
                    "ticket, and stand there."),
            why_translation_fails=("Carriage and seat numbers are just numbers — readable in any "
                                   "language. The failure is physical: walking to the wrong end "
                                   "of a 500 m platform with luggage."),
            zh_phrase="请问这个车厢在哪里等？",
            zh_pinyin="Qǐngwèn zhège chēxiāng zài nǎlǐ děng?",
        ))

    if scene == "hotel_checkin":
        out.append(Finding(
            rule_ref="HOTEL-01",
            severity="critical",
            title="Hotels must register your passport — original only, and they keep it ~3 minutes",
            detail=("Chinese hotels are legally required to scan/register every foreign guest's "
                    "passport at check-in. Hand over the physical passport, not a photo. If the "
                    "hotel says they cannot accept foreigners, ask them to check their 涉外 "
                    "registration, or call your booking platform."),
            why_translation_fails=("The front desk speaks a sentence you can translate word for "
                                   "word and still not know that the law requires the original "
                                   "document, or that a refusal is a registration-capacity issue "
                                   "rather than a rejection of you."),
            zh_phrase="我要办理入住，这是我的护照原件。",
            zh_pinyin="Wǒ yào bànlǐ rùzhù, zhè shì wǒ de hùzhào yuánjiàn.",
        ))
        out.append(Finding(
            rule_ref="HOTEL-02",
            severity="info",
            title="Deposit is normal — and it is a pre-authorisation, not a charge",
            detail=("Expect a deposit (often ¥200-¥1000) by card pre-auth or cash. Ask for the "
                    "收据 (receipt) and confirm it is released at check-out."),
            why_translation_fails="",
            zh_phrase="请问押金什么时候退？可以刷卡吗？",
            zh_pinyin="Qǐngwèn yājīn shénme shíhòu tuì? Kěyǐ shuākǎ ma?",
        ))

    # --- timing findings (RAIL-TIME-*) ---------------------------------------
    if timing.has_departure:
        if timing.level == "departed":
            out.append(Finding(
                rule_ref="RAIL-TIME-03", severity="critical",
                title="Departure time has passed — this train is gone",
                detail=("Do not run for the platform. Go to the 改签 (rebooking) counter with "
                        "your passport; same-day rebooking is usually possible subject to "
                        "availability."),
                why_translation_fails="",
                zh_phrase="我要改签，请问改签窗口在哪里？",
                zh_pinyin="Wǒ yào gǎiqiān, qǐngwèn gǎiqiān chuāngkǒu zài nǎlǐ?",
            ))
        elif timing.level == "gate_closed":
            out.append(Finding(
                rule_ref="RAIL-TIME-01", severity="critical",
                title=f"The gate is already closed (it closed at {timing.gate_close_time})",
                detail=("Chinese gates close BEFORE departure, not at departure. Go to the "
                        "改签 counter — you cannot board now."),
                why_translation_fails=("Your ticket says 09:00. Nothing on it says the gate "
                                       "closed at 08:55. The deadline is a rule, not text."),
                zh_phrase="我要改签下一班车。",
                zh_pinyin="Wǒ yào gǎiqiān xià yī bān chē.",
            ))
        elif timing.level == "danger":
            out.append(Finding(
                rule_ref="RAIL-TIME-01", severity="critical",
                title=f"Only {timing.minutes_to_gate_close} min left — the gate closes at "
                      f"{timing.gate_close_time}",
                detail=("Walk fast, do not queue for a paper ticket, go straight to the staffed "
                        "wide lane with your passport in hand. Skip shops and restrooms."),
                why_translation_fails=("The countdown a traveller needs is computed from the "
                                       "departure time MINUS the station's closing rule. No OCR "
                                       "or translation output contains that number."),
                zh_phrase="我的车马上开了，可以优先一下吗？",
                zh_pinyin="Wǒ de chē mǎshàng kāi le, kěyǐ yōuxiān yīxià ma?",
            ))
        elif timing.level == "warn":
            out.append(Finding(
                rule_ref="RAIL-TIME-01", severity="warn",
                title=f"{timing.minutes_to_gate_close} min to gate close "
                      f"({timing.gate_close_time}) — go through security now",
                detail=("Security + real-name check can take 15-25 min at busy stations. "
                        "Enter now rather than waiting in the plaza."),
                why_translation_fails="",
                zh_phrase="请问安检在哪里？",
                zh_pinyin="Qǐngwèn ānjiǎn zài nǎlǐ?",
            ))
    return out


# ---------------------------------------------------------------------------
# ordered procedures (RAIL-PROC-* / HOTEL-PROC-*)
# ---------------------------------------------------------------------------

PROCEDURES: dict[str, list[Step]] = {
    "rail_ticket": [
        Step(1, "Confirm which station your train departs from",
             "Compare the departure station on the ticket with the station you are standing at. "
             "Big cities have several stations (e.g. 北京站 / 北京南站 / 北京西站).",
             "RAIL-PLACE-01"),
        Step(2, "Have your passport in your hand and walk to 进站口 (departure entrance)",
             "Not the exit. Real-name check + security are before the waiting hall.",
             "RAIL-PROC-01"),
        Step(3, "Real-name check: passport goes to the staffed lane",
             "Show the passport page with your photo. No paper ticket needed — e-ticket is "
             "linked to the passport.",
             "RAIL-PROC-02"),
        Step(4, "Security check: laptop out, power banks in hand, liquids separate",
             "Power banks must have a visible capacity label (Wh).",
             "RAIL-PROC-03"),
        Step(5, "Find your check-in gate on the departure board",
             "Match your train number (e.g. G7). The board overrides the ticket if they differ.",
             "RAIL-GATE-02"),
        Step(6, "Board through the wide / staffed lane with your passport",
             "Usually starts 15-20 min before departure and closes minutes before the train leaves.",
             "RAIL-GATE-01"),
        Step(7, "On the platform: follow the coloured ground marker for your carriage",
             "Find your seat; overhead racks fit most cabin bags.",
             "RAIL-BOARD-01"),
    ],
    "rail_entrance": [
        Step(1, "Check the station name on the building before you queue",
             "If it does not match your ticket's departure station, you are at the wrong station.",
             "RAIL-PLACE-01"),
        Step(2, "Choose the 进站口 (departure entrance), not 出站口",
             "If the sign mentions 出站/出口/到达, walk around the building.",
             "RAIL-PLACE-02"),
        Step(3, "Real-name verification lane: use the staffed lane with your passport",
             "Automated lanes scan Chinese ID cards only.",
             "RAIL-PROC-02"),
        Step(4, "Security: passport + bag screening, power bank in hand",
             "Arrive at least 45 min before departure (60 min at hub stations).",
             "RAIL-TIME-02"),
        Step(5, "Enter the waiting hall and read the big board for your gate",
             "Gate numbers (e.g. B12) are usually shown 15-30 min before departure.",
             "RAIL-GATE-02"),
    ],
    "rail_kiosk": [
        Step(1, "Stop using the machine — it cannot read a passport",
             "These machines are built for Chinese ID cards (二代身份证).",
             "RAIL-KIOSK-01"),
        Step(2, "Ask yourself: do I actually need paper?",
             "With an e-ticket you can enter with the passport alone. Paper is only needed for a "
             "reimbursement invoice (报销凭证).",
             "RAIL-KIOSK-02"),
        Step(3, "Walk to 人工售票窗口 / 服务台 (staffed counter) with your passport",
             "Say the Chinese phrase below; staff will print the ticket or the invoice.",
             "RAIL-KIOSK-01"),
        Step(4, "Allow ~15 min for the counter queue, then go through security",
             "Keep the passport out — you will show it twice more.",
             "RAIL-TIME-02"),
        Step(5, "If your train is close: skip the counter entirely",
             "Go straight to security and the staffed boarding lane; the passport is your ticket.",
             "RAIL-TIME-01"),
    ],
    "rail_waiting_hall": [
        Step(1, "Locate your train number on the big departure board",
             "Status words: 候车 waiting / 正在检票 now boarding / 停止检票 closed.",
             "RAIL-GATE-02"),
        Step(2, "Confirm the check-in gate, and whether it is A or B",
             "A and B gates for the same train lead to different ends of the platform.",
             "RAIL-GATE-02"),
        Step(3, "Queue only when the board says 正在检票",
             "Boarding normally starts 15-20 min before departure.",
             "RAIL-GATE-01"),
        Step(4, "Use the wide / staffed lane and hand over your passport",
             "Automated lanes do not read passports.",
             "RAIL-GATE-01"),
        Step(5, "Go down to the platform and stand at your carriage's colour marker",
             "Keep the passport accessible — it can be checked onboard.",
             "RAIL-BOARD-01"),
    ],
    "rail_gate": [
        Step(1, "Do not enter the ID-card-only lane",
             "Look for 人工通道 / 宽通道 (staffed or wide lane).",
             "RAIL-GATE-01"),
        Step(2, "Open your passport to the photo page and show it to the attendant",
             "They may scan it manually; that is normal and takes a few seconds.",
             "RAIL-PROC-02"),
        Step(3, "After the gate, follow signs to your platform (A or B)",
             "If you came through the wrong side, ask staff — do not cross the tracks.",
             "RAIL-GATE-02"),
        Step(4, "Stand at the coloured marker matching your carriage number",
             "On 16-car trains, car 1-8 and 9-16 are not connected.",
             "RAIL-BOARD-01"),
    ],
    "rail_platform": [
        Step(1, "Match the colour marker on the ground to the colour on your ticket",
             "Markers are painted for each carriage position.",
             "RAIL-BOARD-01"),
        Step(2, "If your carriage is 9-16, walk to the far end before the train stops",
             "The two halves of a doubled train are not connected inside.",
             "RAIL-BOARD-01"),
        Step(3, "Board, then find the seat number plate above the seat",
             "Window seats: A/F. Aisle: C/D. Middle: B.",
             "RAIL-BOARD-02"),
        Step(4, "Keep your passport in your pocket — conductors check it onboard",
             "Stow large bags at the end of the carriage.",
             "RAIL-PROC-02"),
    ],
    "hotel_checkin": [
        Step(1, "Put your physical passport on the counter, open at the photo page",
             "Registration is a legal requirement; photos and copies are refused.",
             "HOTEL-01"),
        Step(2, "Show the booking confirmation (Chinese name of the hotel helps)",
             "Many foreign names differ from the local registration name.",
             "HOTEL-PROC-01"),
        Step(3, "Expect the visa/entry-stamp page to be scanned or photographed",
             "This is normal and takes about 3 minutes.",
             "HOTEL-01"),
        Step(4, "Pay the deposit and keep the receipt (收据)",
             "Card pre-auth or cash; confirm the release time at check-out.",
             "HOTEL-02"),
        Step(5, "Take the room card and check whether the lift needs it",
             "Many Chinese hotels only let you press your floor after tapping the room card.",
             "HOTEL-PROC-02"),
    ],
    "unknown": [
        Step(1, "Tell us where you are in one line, or take a wider photo",
             "Include the sign or the machine screen so the scene can be identified.",
             "GEN-01"),
        Step(2, "If you are in a hurry, find a staff member and show the phrase below",
             "Uniformed staff at stations and hotels usually know the English words they need.",
             "GEN-02"),
    ],
}

SCENE_LABELS = {
    "rail_ticket": "Train ticket / booking",
    "rail_kiosk": "Self-service ticket machine",
    "rail_entrance": "Station entrance / ID check",
    "rail_waiting_hall": "Waiting hall / departure board",
    "rail_gate": "Boarding gate",
    "rail_platform": "Platform / on the train",
    "hotel_checkin": "Hotel check-in",
    "unknown": "Unidentified scene",
}


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def evaluate(vision: dict[str, Any], trip: TripContext, now: datetime) -> RuleResult:
    extracted = dict(vision.get("extracted") or {})
    extracted["_ocr"] = vision.get("ocr_text") or []
    scene = vision.get("scene") or "unknown"

    # 1. which departure time do we trust? trip profile > what OCR read.
    # For hotel scenes, IGNORE OCR'd times entirely — a 14:00 on the sign is the
    # check-in time, not a departure.
    depart = None
    if scene != "hotel_checkin":
        depart = _parse_dt(trip.depart_time, now) or _parse_dt(extracted.get("depart_time"), now)
        if not depart and extracted.get("depart_date") and extracted.get("depart_time"):
            depart = _parse_dt(f"{extracted['depart_date']} {extracted['depart_time']}", now)
    station_for_rules = (trip.planned_station
                         or extracted.get("station_name_on_site")
                         or extracted.get("from_station"))

    # 2. timing is computed by rules, never by the model
    timing = build_timing(depart, now, station_for_rules)

    # 3. gather rule findings
    findings: list[Finding] = []
    findings += document_findings(trip, extracted)
    findings += scene_findings(scene, extracted, trip, timing)

    # 4. missing-items checklist
    missing: list[dict[str, str]] = []
    docset = {d.lower() for d in (trip.documents or [])}
    need_passport = (trip.booked_with == "passport"
                     or extracted.get("id_type_on_ticket") == "passport"
                     or scene.startswith("rail"))
    if need_passport and "passport" not in docset:
        missing.append({
            "item": "Original passport",
            "why": "Required at ID check, ticket gate and hotel registration.",
            "how_to_fix": "Go back for it before queueing — copies are refused.",
        })
    if scene == "hotel_checkin" and "booking_qr" not in docset:
        missing.append({
            "item": "Booking confirmation (QR or number)",
            "why": "The hotel needs the local reservation name to match their system.",
            "how_to_fix": "Open your booking app and show the Chinese hotel name.",
        })
    if not docset:
        missing.append({
            "item": "Trip profile not filled in",
            "why": "Rules compare your documents and departure time with what is on site.",
            "how_to_fix": "Fill in the trip panel (2 fields is enough).",
        })

    # 5. ordered procedure for this scene
    steps = [Step(s.order, s.action, s.detail, s.rule_ref) for s in
             PROCEDURES.get(scene, PROCEDURES["unknown"])]

    facts: list[dict[str, str]] = []
    if extracted.get("train_no"):
        facts.append({"k": "Train", "v": str(extracted["train_no"])})
    if extracted.get("from_station") or trip.planned_station:
        facts.append({"k": "From", "v": str(trip.planned_station or extracted["from_station"])})
    if extracted.get("to_station"):
        facts.append({"k": "To", "v": str(extracted["to_station"])})
    if extracted.get("gate"):
        facts.append({"k": "Gate", "v": str(extracted["gate"])})
    if extracted.get("carriage") or extracted.get("seat"):
        facts.append({"k": "Car / Seat",
                      "v": f"{extracted.get('carriage') or '-'} / {extracted.get('seat') or '-'}"})
    if extracted.get("station_name_on_site"):
        facts.append({"k": "Station on site", "v": str(extracted["station_name_on_site"])})
    facts.append({"k": "Document used to book", "v": DOC_LABEL.get(trip.booked_with, trip.booked_with)})

    return RuleResult(
        scene=scene,
        scene_label=SCENE_LABELS.get(scene, scene),
        timing=timing,
        steps=steps,
        findings=findings,
        missing=missing,
        facts_used=facts,
    )
