"""Stage 3 — expression layer.

The rules already decided WHAT is true. This layer only decides HOW it is said:
  * translate the rule output into the traveller's language (en is the source of truth)
  * let the model add a short, question-specific explanation — but the model is
    explicitly forbidden from changing any fact, number, document or rule verdict.

OFFLINE MODE
------------
When no LLM key is configured (the default for the deployed demo), the built-in
sample cases are baked into code (see app.demo_cases) and translated with the
static dictionaries below. No network call is made — the demo is fully
self-contained and works on Render with zero configuration.
"""
from __future__ import annotations

import logging
import re

from .config import LLM_API_KEY
from .llm import LLMError, text_json
from .rules import RuleResult

log = logging.getLogger("copilot.i18n")

LLM_AVAILABLE = bool(LLM_API_KEY)

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
- Translate ONLY these string fields: title, detail, why_translation_fails, action, item, why, how_to_fix, scene_label.
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

# ---------------------------------------------------------------------------
# Offline translation tables (used when LLM_AVAILABLE is False)
# ---------------------------------------------------------------------------

ZH_SCENE = {
    "rail_ticket": "火车票 / 行程单",
    "rail_kiosk": "自助售票机",
    "rail_entrance": "车站进站口 / 实名验证",
    "rail_waiting_hall": "候车厅 / 出发大屏",
    "rail_gate": "检票口",
    "rail_platform": "站台 / 列车上",
    "hotel_checkin": "酒店入住",
    "unknown": "未识别场景",
}

# rule_ref -> {title, detail, why}  (why omitted when empty)
ZH_FINDINGS = {
    "DOC-01": {  # info variant (passport already in hand)
        "title": "把护照拿在手上，别塞在箱子里",
        "detail": "你要在以下环节出示它：安检/实名验证、必要时的人工窗口、检票闸机，"
                  "车上也可能查。请放在随手能拿到的地方。",
        "why": "",
    },
    "DOC-01-critical": {
        "title": "你需要护照原件——不是照片或复印件",
        "detail": "你的票是用护照买的。中国铁路和酒店在柜台读取护照芯片/号码；"
                  "照片、截图或复印件会被拒。",
        "why": "翻译软件会把“证件”译作“ID”——它无法知道你的票是用护照买的，"
               "也不知道这里只认实体证件。",
    },
    "RAIL-PLACE-01": {  # stations injected via regex from the English title
        "title_tmpl": "你走错车站了：这里是 {on_site}，你的车从 {planned} 发车",
        "detail_tmpl": "两个站都在同一座城市，而且都很常见。{on_site} 和 {planned} "
                       "坐地铁可能相差 30-60 分钟。现在就出发，动身前先确认交通方式。",
    },
    "RAIL-PLACE-02": {
        "title": "这里是出站 / 到达口，不是进站口",
        "detail": "中国车站把到达和出发分流。请绕到写着进站口的一侧——不要从这里硬闯。",
        "why": "“出站口”和“进站口”只差一个字，翻译都近似“station entrance/exit”。"
               "方向是流程规则，不是词汇问题。",
    },
    "RAIL-KIOSK-01": {
        "title": "这台机器读不了护照——请去人工窗口",
        "detail": "中国车站大部分自助售票机只认二代身份证，不支持外国护照。请持护照前往"
                  "人工售票窗口 / 服务台（人工售票窗口）。",
        "why": "机器屏幕上显示的是完全能读懂的信息——通常就是“请使用二代身份证”。"
               "翻译它帮不上忙：它不会告诉你这台机器对你根本用不了，也不会告诉你该去"
               "哪个窗口，更不会告诉你也许你根本不需要纸质票。",
    },
    "RAIL-KIOSK-02": {
        "title": "你可能根本不需要纸质票",
        "detail": "中国铁路已全面实行电子客票：护照就是你的车票。你可以直接凭护照过安检"
                  "和闸机。只有在需要报销凭证时才取纸质票。",
        "why": "机器上没有任何地方写“你可能不需要我”。这是流程事实，不是屏幕上的文字。",
    },
    "RAIL-KIOSK-03": {  # machine_error is already Chinese; wrap it
        "title_tmpl": '机器提示：“{msg}”',
        "detail": "不要反复重试这台机器——重复失败不会解除限制。",
    },
    "RAIL-GATE-01": {
        "title": "护照票：走宽通道 / 人工通道，不要走只认身份证的闸机",
        "detail": "带读卡器的自动闸机是为中国身份证设计的。持护照请走人工通道或宽通道，"
                  "向工作人员出示护照。",
        "why": "“凭购票时所用证件原件检票”翻译起来没问题，但它没说你的证件该走哪种实体"
               "通道。旅客常在错误的闸机前白白浪费 5-10 分钟。",
    },
    "RAIL-GATE-02": {
        "title": "看大屏——检票口可能会变",
        "detail": "车票上印的检票口（如 B12）只是暂定。出发大屏才是权威，通常在开车前"
                  "15-30 分钟确认检票口。",
        "why": "",
    },
    "RAIL-BOARD-01": {
        "title": "16 节长编组列车上，1-8 车与 9-16 车并不连通",
        "detail": "如果你的车厢号大于 8，不能从 8 车走过去。请把站台上的颜色地标与车票上的"
                  "颜色对应，并站在那里。",
        "why": "车厢号和座位号只是数字，任何语言都能读。真正的麻烦是物理上的：拖着行李"
               "在 500 米的站台上走到错误的一端。",
    },
    "HOTEL-01": {
        "title": "酒店必须登记你的护照——只要原件，他们会留存约 3 分钟",
        "detail": "中国酒店依法必须在入住时扫描/登记每位外籍住客的护照。请交验护照原件，"
                  "不要给照片。如果酒店说不能接待外国人，请他们核对涉外登记资质，或联系"
                  "你的预订平台。",
        "why": "前台说的那句话你可以逐字翻译，却依然不知道法律要求的是原件，也不知道拒接"
               "其实是登记资质问题，而不是拒绝你本人。",
    },
    "HOTEL-02": {
        "title": "押金是正常的——而且是预授权，不是扣款",
        "detail": "通常需押金（常见 ¥200-¥1000），可用银行卡预授权或现金。请索取收据，"
                  "并确认退房时释放。",
        "why": "",
    },
    "RAIL-TIME-03": {
        "title": "开车时间已过——这班车走了",
        "detail": "别冲向站台。持护照去改签窗口；当天改签通常可以，视余票而定。",
        "why": "",
    },
}

# RAIL-TIME-01 has three time-dependent variants, keyed by timing.level.
ZH_TIME01 = {
    "gate_closed": {
        "title_tmpl": "闸机已经关了（在 {gate_close_time} 关闭）",
        "detail": "中国闸机在开车前就关闭，不是开车时。去改签窗口——你现在上不了车。",
        "why": "你的票写着 09:00。票上没写闸机在 08:55 就关了。截止时间是规则，不是文字。",
    },
    "danger": {
        "title_tmpl": "只剩 {minutes} 分钟——闸机将在 {gate_close_time} 关闭",
        "detail": "快走，别去排队取纸质票，拿好护照直接去人工宽通道。别逛商店和上洗手间。",
        "why": "旅客真正需要的倒计时，是用“发车时间 减去 车站关闭规则”算出来的。"
               "任何 OCR 或翻译输出里都没有这个数字。",
    },
    "warn": {
        "title_tmpl": "{minutes} 分钟后停止检票（{gate_close_time}）——现在就去安检",
        "detail": "安检加实名验证在繁忙车站可能要 15-25 分钟。现在进场，别在大厅里等。",
        "why": "",
    },
}

# steps keyed by (scene, order) -> {action, detail}
ZH_STEPS = {
    ("rail_entrance", 1): {
        "action": "在排队前先核对建筑上的站名",
        "detail": "如果和车票上的出发站不一致，你就走错站了。",
    },
    ("rail_entrance", 2): {
        "action": "选择进站口，不要走出站口",
        "detail": "如果指示牌出现出站 / 出口 / 到达，请绕到建筑另一侧。",
    },
    ("rail_entrance", 3): {
        "action": "实名验证通道：走人工通道，出示护照",
        "detail": "自动通道只扫身份证。",
    },
    ("rail_entrance", 4): {
        "action": "安检：护照 + 行李过机，充电宝拿在手上",
        "detail": "大型枢纽站请至少提前 60 分钟到达。",
    },
    ("rail_entrance", 5): {
        "action": "进入候车厅，在大屏上找你的检票口",
        "detail": "检票口（如 B12）通常在开车前 15-30 分钟显示。",
    },
    ("rail_kiosk", 1): {
        "action": "别再用这台机器——它读不了护照",
        "detail": "这些机器是为二代身份证设计的。",
    },
    ("rail_kiosk", 2): {
        "action": "问问自己：我真的需要纸质票吗？",
        "detail": "电子客票凭护照即可进站，纸质票只在需要报销凭证时才取。",
    },
    ("rail_kiosk", 3): {
        "action": "拿护照去人工售票窗口 / 服务台",
        "detail": "说出下面的中文，工作人员会打印车票或凭证。",
    },
    ("rail_kiosk", 4): {
        "action": "柜台排队约 15 分钟，然后去安检",
        "detail": "护照一直拿在手上——后面还要再出示两次。",
    },
    ("rail_kiosk", 5): {
        "action": "如果车快开了：干脆跳过柜台",
        "detail": "直接去安检和人工检票通道；护照就是你的车票。",
    },
    ("rail_ticket", 1): {
        "action": "确认车票上的出发站",
        "detail": "把车票上的出发站和你所在车站比对。大城市有好几个站"
                  "（如北京站 / 北京南站 / 北京西站）。",
    },
    ("rail_ticket", 2): {
        "action": "护照拿在手上，走向进站口",
        "detail": "不是出站口。实名验证和安检在候车厅之前。",
    },
    ("rail_ticket", 3): {
        "action": "实名验证：护照走人工通道",
        "detail": "出示有照片的护照页。不需要纸质票——电子客票绑定护照。",
    },
    ("rail_ticket", 4): {
        "action": "安检：笔记本取出，充电宝拿手上，液体分开",
        "detail": "充电宝必须有清晰的容量标识（Wh）。",
    },
    ("rail_ticket", 5): {
        "action": "在出发大屏上找你的检票口",
        "detail": "核对你的车次（如 G7）。大屏与车票不一致时以大屏为准。",
    },
    ("rail_ticket", 6): {
        "action": "走人工 / 宽通道，凭护照检票上车",
        "detail": "通常在开车前 15-20 分钟开始，开车前几分钟关闭。",
    },
    ("rail_ticket", 7): {
        "action": "站台上：按车厢颜色地标排队",
        "detail": "找到座位；头顶行李架放得下大部分登机箱。",
    },
    ("rail_waiting_hall", 1): {
        "action": "在大出发屏上找到你的车次",
        "detail": "状态词：候车 waiting / 正在检票 now boarding / 停止检票 closed。",
    },
    ("rail_waiting_hall", 2): {
        "action": "确认检票口，以及是 A 还是 B",
        "detail": "同一趟车的 A、B 检票口通往站台的不同端。",
    },
    ("rail_waiting_hall", 3): {
        "action": "只在屏幕显示正在检票时排队",
        "detail": "检票通常在开车前 15-20 分钟开始。",
    },
    ("rail_waiting_hall", 4): {
        "action": "走宽 / 人工通道，递上护照",
        "detail": "自动闸机读不了护照。",
    },
    ("rail_waiting_hall", 5): {
        "action": "下到站台，站在对应车厢颜色地标处",
        "detail": "护照放在随手可取处——车上还会查。",
    },
    ("rail_gate", 1): {
        "action": "不要进只认身份证的闸机通道",
        "detail": "找人工通道 / 宽通道（人工通道 / 宽通道）。",
    },
    ("rail_gate", 2): {
        "action": "翻开护照到照片页，递给工作人员",
        "detail": "他们可能手动扫描；正常，几秒钟就好。",
    },
    ("rail_gate", 3): {
        "action": "过闸机后，按指示去对应站台（A 或 B）",
        "detail": "如果你走错侧，问工作人员——不要横穿轨道。",
    },
    ("rail_gate", 4): {
        "action": "站在与车厢号对应的颜色地标处",
        "detail": "16 节编组列车，1-8 车与 9-16 车不连通。",
    },
    ("rail_platform", 1): {
        "action": "把地面颜色地标与车票上的颜色对应",
        "detail": "每个车厢位置都刷了颜色地标。",
    },
    ("rail_platform", 2): {
        "action": "如果你的车厢是 9-16，列车停稳前走到远端",
        "detail": "长编组列车的两半在车内不连通。",
    },
    ("rail_platform", 3): {
        "action": "上车后，找座位号铭牌（头顶）",
        "detail": "靠窗：A/F。过道：C/D。中间：B。",
    },
    ("rail_platform", 4): {
        "action": "护照放口袋里——列车员会在车上查",
        "detail": "大件行李放在车厢两端。",
    },
    ("hotel_checkin", 1): {
        "action": "把护照原件放在柜台上，翻到有照片的一页",
        "detail": "登记是法律要求；照片和复印件都会被拒。",
    },
    ("hotel_checkin", 2): {
        "action": "出示预订确认（酒店中文名有帮助）",
        "detail": "很多外文名和本地登记名不一致。",
    },
    ("hotel_checkin", 3): {
        "action": "签证 / 入境章页会被扫描或拍照",
        "detail": "这是正常流程，约需 3 分钟。",
    },
    ("hotel_checkin", 4): {
        "action": "付押金并保留收据（收据）",
        "detail": "银行卡预授权或现金；确认退房时释放。",
    },
    ("hotel_checkin", 5): {
        "action": "拿房卡，看电梯是否需要刷房卡",
        "detail": "很多中国酒店要先刷房卡才能按楼层。",
    },
}

# missing items keyed by the exact English `item` string
ZH_MISSING = {
    "Original passport": {
        "item": "护照原件",
        "why": "在实名验证、检票闸机和酒店登记处都需要。",
        "how_to_fix": "排队前回去取——复印件会被拒。",
    },
    "Booking confirmation (QR or number)": {
        "item": "预订确认（二维码或单号）",
        "why": "酒店需要本地登记名来匹配系统。",
        "how_to_fix": "打开预订 App，出示酒店中文名。",
    },
    "Trip profile not filled in": {
        "item": "未填写行程信息",
        "why": "规则会把你的证件和出发时间与现场情况比对。",
        "how_to_fix": "填写行程面板（填两项即可）。",
    },
}

_RE_GC = re.compile(r"gates close (\d+) min before departure( \(hub station\))?")
_RE_AB = re.compile(r"arrive by (\S+) \((\d+) min buffer for security \+ ID check\)")


def _zh_timing_rule(en: str) -> str:
    """Translate the two English rule strings embedded in the timing block."""
    m = _RE_GC.search(en or "")
    if m:
        hub = "（枢纽站）" if m.group(2) else ""
        return f"开车前{m.group(1)}分钟停止检票{hub}"
    m = _RE_AB.search(en or "")
    if m:
        return f"请于{m.group(1)}前到达（安检+实名验证预留{m.group(2)}分钟）"
    return en or ""


def _translate_finding_zh(f: dict, timing: dict) -> None:
    ref = f.get("rule_ref", "")
    if ref == "RAIL-TIME-01":
        v = ZH_TIME01.get(timing.get("level"))
        if v:
            f["title"] = v["title_tmpl"].format(
                minutes=timing.get("minutes_to_gate_close", 0),
                gate_close_time=timing.get("gate_close_time", ""),
            )
            f["detail"] = v["detail"]
            f["why_translation_fails"] = v.get("why", "")
        return
    if ref == "RAIL-PLACE-01":
        # stations live inside the English title: "...this is X, your train leaves from Y"
        m = re.search(r"this is (.+?), your train leaves from (.+?)$", f.get("title", ""))
        on_site = m.group(1).strip() if m else ""
        planned = m.group(2).strip() if m else ""
        t = ZH_FINDINGS["RAIL-PLACE-01"]
        f["title"] = t["title_tmpl"].format(on_site=on_site, planned=planned)
        f["detail"] = t["detail_tmpl"].format(on_site=on_site, planned=planned)
        f["why_translation_fails"] = ""
        return
    if ref == "RAIL-KIOSK-03":
        m = re.search(r'Machine message: "(.+?)"', f.get("title", ""))
        msg = m.group(1) if m else (f.get("extracted", {}).get("machine_error", ""))
        t = ZH_FINDINGS["RAIL-KIOSK-03"]
        f["title"] = t["title_tmpl"].format(msg=msg)
        f["detail"] = t["detail"]
        f["why_translation_fails"] = ""
        return
    # DOC-01 has two variants; pick by severity.
    key = ref
    if ref == "DOC-01" and f.get("severity") == "critical":
        key = "DOC-01-critical"
    z = ZH_FINDINGS.get(key)
    if z:
        f["title"] = z.get("title", f["title"])
        f["detail"] = z.get("detail", f["detail"])
        if "why" in z:
            f["why_translation_fails"] = z["why"]


def express_offline(payload: dict, lang: str, ai_note: str = "") -> dict:
    """Translate a rule payload into zh without any LLM call.

    Used by the baked demo cases and as a fallback when no API key is set.
    """
    payload = dict(payload)
    lang = (lang or "en").lower()
    if lang == "en":
        payload["ai_note"] = ai_note or ""
        payload["ai_note_source"] = "baked" if ai_note else ""
        payload["translation"] = "offline:en"
        return payload

    payload["scene_label"] = ZH_SCENE.get(payload.get("scene"), payload.get("scene_label", ""))
    timing = payload.get("timing", {}) or {}
    for f in payload.get("findings", []):
        _translate_finding_zh(f, timing)
    scene = payload.get("scene")
    for s in payload.get("steps", []):
        z = ZH_STEPS.get((scene, s.get("order")))
        if z:
            s["action"] = z["action"]
            s["detail"] = z["detail"]
    for m in payload.get("missing", []):
        z = ZH_MISSING.get(m.get("item"))
        if z:
            m["item"], m["why"], m["how_to_fix"] = z["item"], z["why"], z["how_to_fix"]
    timing["gate_close_rule"] = _zh_timing_rule(timing.get("gate_close_rule"))
    timing["arrive_rule"] = _zh_timing_rule(timing.get("arrive_rule"))
    payload["ai_note"] = ai_note or ""
    payload["ai_note_source"] = "baked" if ai_note else ""
    payload["translation"] = "offline:zh"
    return payload


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

    # Offline mode: no LLM available — use the static dictionaries.
    if not LLM_AVAILABLE:
        return express_offline(payload, lang, ai_note="")

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
