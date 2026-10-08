# -*- coding: utf-8 -*-
"""Generate the product-introduction PDF for Travel-China Copilot (作品简介附件)."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, KeepTogether)

# ---- CJK font (bundled with reportlab, no external file needed) ----
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
FONT = "STSong-Light"

# ---- palette (Apple-ish) ----
ACCENT = colors.HexColor("#0071E3")
ACCENT_DARK = colors.HexColor("#00468C")
INK = colors.HexColor("#1D1D1F")
SUB = colors.HexColor("#6E6E73")
BG = colors.HexColor("#F5F5F7")
LINE = colors.HexColor("#D2D2D7")
WHITE = colors.white
CRIT = colors.HexColor("#FF3B30")
WARN = colors.HexColor("#FF9500")
INFO = colors.HexColor("#34C759")

PAGE_W, PAGE_H = A4
MARGIN = 50
CONTENT_W = PAGE_W - 2 * MARGIN

# ---- styles ----
body = ParagraphStyle("body", fontName=FONT, fontSize=10.5, leading=17,
                      textColor=INK, spaceAfter=6, alignment=TA_LEFT)
body_sm = ParagraphStyle("body_sm", parent=body, fontSize=9.5, leading=15, textColor=SUB)
cover_title = ParagraphStyle("ct", fontName=FONT, fontSize=30, leading=38,
                             textColor=WHITE, alignment=TA_LEFT)
cover_en = ParagraphStyle("ce", fontName=FONT, fontSize=14, leading=20,
                          textColor=colors.HexColor("#E6F0FF"), alignment=TA_LEFT)
cover_tag = ParagraphStyle("ctg", fontName=FONT, fontSize=11, leading=18,
                           textColor=WHITE, alignment=TA_LEFT)
cell = ParagraphStyle("cell", fontName=FONT, fontSize=9.5, leading=14, textColor=INK)
cell_h = ParagraphStyle("cellh", fontName=FONT, fontSize=9.5, leading=14,
                        textColor=WHITE)
cell_sub = ParagraphStyle("cells", fontName=FONT, fontSize=9, leading=13, textColor=SUB)
note = ParagraphStyle("note", fontName=FONT, fontSize=9.5, leading=15,
                      textColor=SUB, spaceAfter=4)


def section(title, badge=None):
    """Section header with a colored left bar."""
    left = Table([[""]], colWidths=[6])
    left.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT),
                              ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                              ("TOPPADDING", (0, 0), (-1, -1), 0),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    t = title
    if badge:
        t = '%s  <font color="#0071E3">%s</font>' % (title, badge)
    head = Paragraph(t, ParagraphStyle("sh", fontName=FONT, fontSize=15,
                                       leading=20, textColor=INK))
    bar = Table([[left, head]], colWidths=[6, CONTENT_W - 6])
    bar.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("LEFTPADDING", (0, 0), (0, 0), 0),
                             ("RIGHTPADDING", (0, 0), (0, 0), 0),
                             ("LEFTPADDING", (1, 0), (1, 0), 10),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                             ("TOPPADDING", (0, 0), (-1, -1), 4)]))
    return [bar, Spacer(1, 8)]


def bullets(items, color=ACCENT):
    """A list where each row is a small colored square + text."""
    rows = []
    for it in items:
        sq = Table([[""]], colWidths=[9])
        sq.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), color),
                                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                ("TOPPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        rows.append([sq, Paragraph(it, body)])
    t = Table(rows, colWidths=[14, CONTENT_W - 14])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 3),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                           ("LEFTPADDING", (0, 0), (0, -1), 2)]))
    return t


def datatable(header, rows, col_widths, header_bg=ACCENT):
    data = [[Paragraph(h, cell_h) for h in header]]
    for r in rows:
        data.append([Paragraph(c, cell) for c in r])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BG]),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT, 8)
    canvas.setFillColor(SUB)
    canvas.drawString(MARGIN, 26, "Travel-China Copilot  ·  团队 钉子头")
    canvas.drawRightString(PAGE_W - MARGIN, 26, "第 %d 页" % doc.page)
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 36, PAGE_W - MARGIN, 36)
    canvas.restoreState()


def build(path):
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=MARGIN,
                            rightMargin=MARGIN, topMargin=MARGIN,
                            bottomMargin=46, title="Travel-China Copilot 产品介绍",
                            author="团队 钉子头")
    s = []

    # ---------- COVER ----------
    eyebrow = Paragraph("2026 入境游 AI 创新大赛  ·  作品附件", cover_en)
    title_cn = Paragraph("旅行中国搭子", cover_title)
    title_en = Paragraph("Travel-China Copilot", cover_en)
    tagline = Paragraph("入境游客的中国现场流程副驾。拍一张票、一台机器、一块牌子或酒店前台"
                        "—— 它告诉你下一步该做什么，而不只是翻译。", cover_tag)
    team = Paragraph("团队：钉子头", cover_tag)
    meta = Paragraph("模型理解 + 规则兜底  ·  中英双语  ·  零配置可演示", cover_en)

    banner = Table(
        [[eyebrow], [title_cn], [title_en], [Spacer(1, 6)], [tagline],
         [Spacer(1, 10)], [team], [meta]],
        colWidths=[CONTENT_W])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 1), ACCENT),       # top two-tone
        ("BACKGROUND", (0, 2), (-1, -1), ACCENT_DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 26),
        ("RIGHTPADDING", (0, 0), (-1, -1), 26),
        ("TOPPADDING", (0, 0), (0, 0), 30),
        ("BOTTOMPADDING", (0, 0), (0, 1), 2),
        ("TOPPADDING", (0, 2), (0, 2), 0),
        ("BOTTOMPADDING", (0, 2), (0, 2), 10),
        ("TOPPADDING", (0, 3), (-1, -1), 2),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 26),
    ]))
    s.append(banner)
    s.append(Spacer(1, 26))

    # ---------- 作品简介 ----------
    s += section("作品简介")
    s.append(Paragraph("<b>（1）解决什么问题</b>", body))
    s.append(Paragraph(
        "外国游客在中国火车站、酒店、机场遇到的麻烦，几乎不是“看不懂单词”，而是“搞不清流程”："
        "该走哪个口刷护照、开车前几分钟停止检票、这趟车到底是不是从这个站出发、前台要不要扣押照原件。"
        "普通翻译 / OCR 能读出每个字，却给不出下一步动作。本作品把“翻译”升级为“副驾”："
        "在游客拍下现场照片的瞬间，直接给出可执行的下一条动作。", body))
    s.append(Spacer(1, 6))
    s.append(Paragraph("<b>（2）面向哪类用户</b>", body))
    s.append(bullets([
        "入境自由行的外国游客——首次来华、语言不通、对本地流程陌生；",
        "同样适用于中国游客出境时面临的同类“流程盲区”（翻译是双向的）；",
        "间接用户：景区与交通枢纽的服务人员，可凭 App 生成的一句中文短语快速理解游客需求。",
    ]))
    s.append(Spacer(1, 6))
    s.append(Paragraph("<b>（3）核心能力是什么</b>", body))
    s.append(bullets([
        "<b>场景感知</b>：多模态模型看清照片、识别场景并读出文字（只感知，不决策）；",
        "<b>规则决策</b>：确定性规则引擎，每条规则带稳定 ID（如 RAIL-KIOSK-01），结论不会被模型覆盖；",
        "<b>母语表达</b>：把结论翻译成游客母语，并附上一句可给工作人员看的中文（带拼音）；",
        "<b>实时倒计时</b>：按各枢纽不同的停止检票规则，算出真实的“还剩几分钟”；",
        "<b>零配置演示</b>：5 个内置场景写死在代码里，部署后不配任何 API Key 也能完整演示。",
    ], color=INFO))
    s.append(PageBreak())

    # ---------- 能力对比 ----------
    s += section("能力对比：翻译软件 vs 现场副驾")
    cmp_rows = [
        ["读出屏幕上写的是什么", "支持", "支持（多模态模型）"],
        ["知道你在哪座城市的哪个站", "不支持", "支持（规则 RAIL-PLACE-01）"],
        ["告诉你这台机器对你不可用", "不支持", "支持（RAIL-KIOSK-01）"],
        ["算出真实的停止检票倒计时", "不支持", "支持（RAIL-TIME-01，各枢纽可配）"],
        ["提示你是否走错了入口", "不支持", "支持（RAIL-PLACE-02）"],
        ["生成一句可给工作人员看的中文", "不支持", "支持（规则附带，带拼音）"],
    ]
    cmp_tbl = datatable(["能力", "普通翻译 / OCR App", "Travel-China Copilot"],
                        cmp_rows, [200, 130, CONTENT_W - 330])
    # color the third column text blue
    cmp_tbl.setStyle(TableStyle([("TEXTCOLOR", (2, 1), (2, -1), ACCENT)]))
    s.append(cmp_tbl)
    s.append(Spacer(1, 14))

    # ---------- 架构 ----------
    s += section("架构：模型理解 + 规则兜底")
    s.append(Paragraph("感知交给模型，决策交给规则。模型可以出错或被关掉，规则永远在线。", body))
    arch_rows = [
        ["阶段 1 · 感知层", "多模态模型（glm-5.3-flash）看到照片，命名场景、抄录文字。"
         "模型被明确禁止替游客决定该做什么。"],
        ["阶段 2 · 规则引擎", "确定性规则（app/rules.py）。每条规则有稳定 ID，UI 以 RULE 徽章标注；"
         "即使模型不可达，规则照常运行，结论从不被模型覆盖。"],
        ["阶段 3 · 表达层", "把结论翻译成游客母语，并附一句 AI 备注，输出 JSON 给浏览器渲染。"],
    ]
    arch = datatable(["", "说明"], arch_rows, [120, CONTENT_W - 120])
    s.append(arch)
    s.append(Spacer(1, 6))
    s.append(Paragraph(
        "徽章约定：<font color='#0071E3'>RULE</font> = 确定性、可审计的规则结论；"
        "<font color='#6E6E73'>MODEL</font> = 多模态感知或语言润色。两者在界面上清晰区分。",
        note))
    s.append(PageBreak())

    # ---------- 五大内置演示场景 ----------
    s += section("五大内置演示场景（翻译软件解不了的 case）")
    demo_rows = [
        ["1", "北京站站名指示牌", "OCR 读得一字不差，规则却发现你的车从“北京南”出发"],
        ["2", "自助取票机", "屏幕完全能读，规则知道护照在这台机器上永远刷不过"],
        ["3", "手机上的电子客票", "每个字都能翻，规则排出 7 个真实步骤并在 22 分钟时预警"],
        ["4", "显示“正在检票”的出发大屏", "距开车 8 分钟，规则算出真实倒计时"],
        ["5", "酒店前台指示牌", "能翻出“护照”，却说不出前台要扣押照原件 3 分钟"],
    ]
    s.append(datatable(["#", "场景", "翻译软件为什么帮不上忙"],
                      demo_rows, [30, 170, CONTENT_W - 200]))
    s.append(Spacer(1, 14))

    # ---------- 为什么这样设计 ----------
    s += section("为什么这样设计（对应评委三点）")
    s.append(bullets([
        "<b>聚焦垂直切片</b>：只做高铁出发全链（进站 · 取票 · 闸机 · 站台）+ 酒店入住，不贪多；",
        "<b>可见的 AI vs 规则分工</b>：每个面板都带 RULE（确定性、可审计）或 MODEL（感知 / 润色）徽章，规则结论从不被模型覆盖；",
        "<b>专挑翻译软件解不了的场景</b>：5 个内置场景 + 实时拍照，每个结论都附一句“为什么普通翻译 app 帮不了你”。",
    ]))
    s.append(Spacer(1, 10))

    # ---------- 部署与演示 ----------
    s += section("部署与演示")
    s.append(bullets([
        "仓库自带 render.yaml，一键部署到 Render；",
        "演示无需任何 LLM API Key：5 个场景写死在 app/demo_cases.py，由 /api/demo 经规则引擎 + 静态中文翻译表输出，零模型调用；",
        "真实“上传自己的照片”路径，仅在配置 Key 后才会调用多模态模型；",
        "中英双语界面，?lang=zh 深链直达中文版；时间轴滑块实时重算倒计时，亦不调用模型。",
    ], color=WARN))
    s.append(Spacer(1, 10))
    s.append(Paragraph(
        "项目地址（示例）：github.com/Winter-Zero-Lab/travel-cn-copilot", note))

    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    print("PDF written:", path)


if __name__ == "__main__":
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(here, "产品介绍附件.pdf")
    build(out)
