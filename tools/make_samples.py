"""Generate the built-in demo photos (rendered signage, screens, tickets).

Run:  .venv/bin/python tools/make_samples.py
"""
from __future__ import annotations

import json
import os
import random
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "web", "samples")
os.makedirs(OUT, exist_ok=True)

HEI = "/System/Library/Fonts/STHeiti Medium.ttc"
SONG = "/System/Library/Fonts/Supplemental/Songti.ttc"
HIRA = "/System/Library/Fonts/Hiragino Sans GB.ttc"


def f(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.truetype(HIRA, size)


def grain(img: Image.Image, amount: float = 0.02) -> Image.Image:
    """Slight noise + soft focus so it reads as a phone photo, not a graphic."""
    px = img.load()
    w, h = img.size
    rnd = random.Random(7)
    for _ in range(int(w * h * 0.06)):
        x, y = rnd.randrange(w), rnd.randrange(h)
        r, g, b = px[x, y]
        d = int(rnd.uniform(-14, 14))
        px[x, y] = (max(0, min(255, r + d)), max(0, min(255, g + d)), max(0, min(255, b + d)))
    return img.filter(ImageFilter.GaussianBlur(0.6))


def save(img: Image.Image, name: str) -> str:
    path = os.path.join(OUT, name)
    img.convert("RGB").save(path, "JPEG", quality=88)
    print("wrote", path, img.size)
    return name


# ---------------------------------------------------------------------------
# 1. Station sign — Beijing Station (the wrong-station trap)
# ---------------------------------------------------------------------------
def sample_wrong_station() -> str:
    W, H = 1100, 780
    img = Image.new("RGB", (W, H), (12, 74, 148))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)],
               fill=(int(12 + 20 * t), int(74 + 22 * t), int(148 + 12 * t)))
    d.rectangle([40, 40, W - 40, H - 40], outline=(255, 255, 255), width=6)
    d.text((W // 2, 150), "北京站", font=f(HEI, 132), fill=(255, 255, 255), anchor="mm")
    d.text((W // 2, 250), "Beijing Railway Station", font=f(HIRA, 34),
           fill=(206, 224, 246), anchor="mm")
    d.line([(120, 300), (W - 120, 300)], fill=(255, 255, 255), width=3)
    d.text((W // 2, 380), "进站口", font=f(HEI, 92), fill=(255, 255, 255), anchor="mm")
    d.text((W // 2, 462), "Entrance", font=f(HIRA, 40), fill=(206, 224, 246), anchor="mm")
    d.text((W // 2 + 150, 380), "→", font=f(HEI, 92), fill=(255, 214, 64), anchor="mm")
    d.text((W // 2, 580), "凭购票时所用证件原件进站", font=f(HEI, 40),
           fill=(226, 238, 252), anchor="mm")
    d.text((W // 2, 640), "实名制验证  安全检查", font=f(HEI, 34),
           fill=(180, 208, 240), anchor="mm")
    return save(grain(img), "01-wrong-station.jpg")


# ---------------------------------------------------------------------------
# 2. Self-service kiosk refusing the passport
# ---------------------------------------------------------------------------
def sample_kiosk() -> str:
    W, H = 1100, 800
    img = Image.new("RGB", (W, H), (58, 62, 70))
    d = ImageDraw.Draw(img)
    d.rectangle([30, 30, W - 30, H - 30], fill=(24, 28, 36))
    d.rectangle([70, 70, W - 70, H - 70], fill=(30, 58, 96))
    d.text((W // 2, 130), "自助售取票机", font=f(HEI, 62), fill=(255, 255, 255), anchor="mm")
    d.text((W // 2, 190), "Self-service Ticket Machine", font=f(HIRA, 28),
           fill=(170, 200, 230), anchor="mm")
    # error box
    x0, y0, x1, y1 = 150, 250, W - 150, 470
    d.rectangle([x0, y0, x1, y1], fill=(120, 24, 24), outline=(255, 90, 90), width=4)
    d.text((W // 2, 330), "请使用二代身份证", font=f(HEI, 66), fill=(255, 240, 240), anchor="mm")
    d.text((W // 2, 410), "Please insert your 2nd-gen ID card", font=f(HIRA, 30),
           fill=(255, 208, 208), anchor="mm")
    for i, label in enumerate(["取票", "购票", "改签", "退票"]):
        bx = 160 + i * 200
        d.rectangle([bx, 540, bx + 160, 640], fill=(46, 84, 130), outline=(150, 190, 230), width=3)
        d.text((bx + 80, 590), label, font=f(HEI, 46), fill=(235, 244, 255), anchor="mm")
    d.text((W // 2, 710), "持护照购票的旅客请到人工售票窗口办理", font=f(HEI, 34),
           fill=(255, 198, 92), anchor="mm")
    return save(grain(img), "02-kiosk.jpg")


# ---------------------------------------------------------------------------
# 3. E-ticket itinerary screenshot
# ---------------------------------------------------------------------------
def sample_ticket() -> str:
    W, H = 1000, 900
    img = Image.new("RGB", (W, H), (238, 242, 248))
    d = ImageDraw.Draw(img)
    d.rectangle([50, 50, W - 50, H - 50], fill=(255, 255, 255), outline=(200, 212, 228), width=3)
    d.rectangle([50, 50, W - 50, 150], fill=(20, 96, 176))
    d.text((W // 2, 100), "行程信息提示  /  Itinerary", font=f(HEI, 44),
           fill=(255, 255, 255), anchor="mm")

    d.text((110, 220), "G7", font=f(HEI, 82), fill=(20, 40, 70), anchor="lm")
    d.text((300, 200), "北京南", font=f(HEI, 56), fill=(20, 40, 70), anchor="lm")
    d.text((300, 265), "09:00 开", font=f(HEI, 34), fill=(70, 90, 120), anchor="lm")
    d.text((620, 232), "——→", font=f(HEI, 44), fill=(140, 165, 195), anchor="lm")
    d.text((690, 200), "上海虹桥", font=f(HEI, 56), fill=(20, 40, 70), anchor="lm")
    d.text((690, 265), "13:28 到", font=f(HEI, 34), fill=(70, 90, 120), anchor="lm")

    d.line([(110, 340), (W - 110, 340)], fill=(215, 224, 236), width=2)
    rows = [
        ("乘车日期", "2026-10-08"),
        ("检票口", "B12"),
        ("车厢 / 座位", "05车 12A"),
        ("购票证件", "护照 P1234567"),
        ("票价", "¥ 553.0"),
    ]
    y = 390
    for k, v in rows:
        d.text((110, y), k, font=f(HEI, 34), fill=(110, 128, 150), anchor="lm")
        d.text((W - 110, y), v, font=f(HEI, 38), fill=(20, 40, 70), anchor="rm")
        y += 72
    d.rectangle([110, 780, W - 110, 850], fill=(250, 240, 220), outline=(230, 200, 140), width=2)
    d.text((W // 2, 815), "实行电子客票，凭购票时所用证件原件进站乘车", font=f(HEI, 30),
           fill=(140, 100, 40), anchor="mm")
    return save(grain(img), "03-eticket.jpg")


# ---------------------------------------------------------------------------
# 4. Departure board — now boarding
# ---------------------------------------------------------------------------
def sample_board() -> str:
    W, H = 1200, 800
    img = Image.new("RGB", (W, H), (14, 16, 20))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, W - 20, H - 20], outline=(60, 70, 84), width=4)
    d.text((W // 2, 90), "列车时刻表  Departures", font=f(HEI, 46), fill=(255, 210, 90), anchor="mm")
    d.line([(40, 140), (W - 40, 140)], fill=(70, 80, 96), width=2)
    heads = ["车次", "终点站", "开点", "检票口", "状态"]
    xs = [110, 360, 640, 840, 1010]
    for x, h in zip(xs, heads):
        d.text((x, 180), h, font=f(HEI, 34), fill=(150, 168, 190), anchor="lm")
    rows = [
        ("G7", "上海虹桥", "09:00", "B12", "正在检票", (255, 96, 60)),
        ("G13", "上海虹桥", "09:20", "A8", "候车", (150, 200, 240)),
        ("D701", "天津西", "09:35", "B5", "候车", (150, 200, 240)),
        ("G33", "杭州东", "09:48", "A3", "候车", (150, 200, 240)),
    ]
    y = 260
    for r in rows:
        color = r[5]
        for x, val in zip(xs, r[:5]):
            d.text((x, y), val, font=f(HEI, 44), fill=color, anchor="lm")
        y += 110
    d.text((W // 2, 730), "停止检票时间为开车前5分钟", font=f(HEI, 32),
           fill=(190, 200, 214), anchor="mm")
    return save(grain(img), "04-board.jpg")


# ---------------------------------------------------------------------------
# 5. Hotel front desk sign
# ---------------------------------------------------------------------------
def sample_hotel() -> str:
    W, H = 1100, 760
    img = Image.new("RGB", (W, H), (246, 240, 230))
    d = ImageDraw.Draw(img)
    for y in range(H):
        d.line([(0, y), (W, y)], fill=(int(246 - 20 * y / H), int(240 - 22 * y / H),
                                       int(230 - 26 * y / H)))
    d.rectangle([60, 60, W - 60, H - 60], outline=(150, 120, 84), width=5)
    d.text((W // 2, 150), "办理入住登记", font=f(HEI, 76), fill=(60, 44, 30), anchor="mm")
    d.text((W // 2, 228), "Check-in Registration", font=f(HIRA, 36),
           fill=(130, 104, 78), anchor="mm")
    d.line([(180, 280), (W - 180, 280)], fill=(180, 152, 112), width=3)
    d.text((W // 2, 350), "请出示护照原件", font=f(HEI, 62), fill=(150, 40, 40), anchor="mm")
    d.text((W // 2, 425), "Original passport required — no photocopies", font=f(HIRA, 30),
           fill=(120, 90, 70), anchor="mm")
    d.text((W // 2, 520), "入住时间 14:00 以后     退房时间 12:00 以前", font=f(HEI, 36),
           fill=(70, 56, 40), anchor="mm")
    d.text((W // 2, 590), "押金可使用现金或银行卡预授权", font=f(HEI, 32),
           fill=(90, 74, 56), anchor="mm")
    d.text((W // 2, 660), "前台  Front Desk   →", font=f(HEI, 34),
           fill=(110, 88, 66), anchor="mm")
    return save(grain(img), "05-hotel.jpg")


SAMPLES_META = [
    {
        "id": "wrong_station",
        "file": "01-wrong-station.jpg",
        "title": "I'm at the entrance — but is this the right station?",
        "title_zh": "站在车站入口，但这站对吗？",
        "kicker": "Wrong station in the same city",
        "scene_hint": "rail_entrance",
        "question": "I followed the signs to the station. Am I in the right place?",
        "question_zh": "我是跟着指示牌走到这个车站的，我在正确的地方吗？",
        "depart_in_minutes": 55,
        "trip": {
            "city": "北京",
            "planned_station": "北京南站",
            "train_no": "G7",
            "booked_with": "passport",
            "documents": ["passport"],
        },
        "highlight": "OCR reads 北京站 correctly. Only the rule engine knows your train leaves "
                     "from 北京南站, 40 minutes away.",
    },
    {
        "id": "kiosk",
        "file": "02-kiosk.jpg",
        "title": "The machine won't accept me — what now?",
        "title_zh": "自助机不认我，怎么办？",
        "kicker": "Kiosk cannot read a passport",
        "scene_hint": "rail_kiosk",
        "question": "This machine keeps rejecting me. Do I need a paper ticket?",
        "question_zh": "这台机器一直拒绝我，我一定要取纸质票吗？",
        "depart_in_minutes": 40,
        "trip": {
            "city": "北京",
            "planned_station": "北京南站",
            "train_no": "G7",
            "booked_with": "passport",
            "documents": ["passport"],
        },
        "highlight": "The screen is readable in any language. The fix is procedural: this machine "
                     "is impossible for you, and you probably never needed paper.",
    },
    {
        "id": "eticket",
        "file": "03-eticket.jpg",
        "title": "I have my booking — what do I actually do?",
        "title_zh": "我有订单了，接下来做什么？",
        "kicker": "Full departure procedure",
        "scene_hint": "rail_ticket",
        "question": "I have my ticket on my phone. What do I do when I get to the station?",
        "question_zh": "我的票在手机上，到了车站该做什么？",
        "depart_in_minutes": 28,
        "trip": {
            "city": "北京",
            "planned_station": "北京南站",
            "train_no": "G7",
            "booked_with": "passport",
            "documents": ["passport"],
        },
        "highlight": "Translation gives you the words on the ticket. We give you the 7 steps, "
                     "the document rule and the real deadline.",
    },
    {
        "id": "board",
        "file": "04-board.jpg",
        "title": "It says 'now boarding' — where do I go?",
        "title_zh": "大屏显示正在检票，我该去哪？",
        "kicker": "Deadline is minutes away",
        "scene_hint": "rail_waiting_hall",
        "question": "The board says my train is boarding. Which way?",
        "question_zh": "大屏显示我的车正在检票，我该往哪走？",
        "depart_in_minutes": 8,
        "trip": {
            "city": "北京",
            "planned_station": "北京南站",
            "train_no": "G7",
            "booked_with": "passport",
            "documents": ["passport"],
        },
        "highlight": "8 minutes to departure, gate closes at 08:55. The countdown is computed "
                     "from a rule, not printed anywhere.",
    },
    {
        "id": "hotel",
        "file": "05-hotel.jpg",
        "title": "Hotel front desk — what will they ask for?",
        "title_zh": "酒店前台会要什么？",
        "kicker": "Mandatory passport registration",
        "scene_hint": "hotel_checkin",
        "question": "I'm checking in. Do they need my passport or just the booking?",
        "question_zh": "我要办入住，他们要护照还是只要订单？",
        "depart_in_minutes": None,
        "trip": {
            "city": "上海",
            "planned_station": "",
            "train_no": "",
            "booked_with": "passport",
            "documents": ["passport"],
        },
        "highlight": "Registration is a legal requirement on the ORIGINAL document — a fact no "
                     "translation of the sign can supply.",
    },
]


def main() -> None:
    sample_wrong_station()
    sample_kiosk()
    sample_ticket()
    sample_board()
    sample_hotel()
    meta_path = os.path.join(OUT, "samples.json")
    with open(meta_path, "w", encoding="utf-8") as fp:
        json.dump(SAMPLES_META, fp, ensure_ascii=False, indent=2)
    print("wrote", meta_path)


if __name__ == "__main__":
    main()
