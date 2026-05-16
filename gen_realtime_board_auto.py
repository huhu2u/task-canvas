#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from PIL import Image, ImageDraw, ImageFont
import math, datetime, os

# ── 数据 ──────────────────────────────────────────────────────────────
DATA_TIME = "16:30"
TODAY = "2026-03-28"
DAYS_LEFT = 4

OPERATORS = [
    {"name": "惠州巨浪",  "gtv": 309.84, "target": 356.60, "today_gtv": 6.42,  "today_cpc": 0.0635},
    {"name": "惠州柏万",  "gtv": 273.80, "target": 305.00, "today_gtv": 4.99,  "today_cpc": 0.1450},
    {"name": "泉州小花猫","gtv": 236.82, "target": 280.90, "today_gtv": 4.85,  "today_cpc": 0.2772},
    {"name": "宁夏灵创",  "gtv": 239.80, "target": 258.20, "today_gtv": 2.01,  "today_cpc": 0.1497},
    {"name": "惠安广通",  "gtv": 194.53, "target": 225.20, "today_gtv": 4.56,  "today_cpc": 0.1036},
    {"name": "慈溪哲光",  "gtv": 175.97, "target": 212.50, "today_gtv": 2.00,  "today_cpc": 0.2372},
    {"name": "义乌汐洋",  "gtv": 173.83, "target": 202.10, "today_gtv": 3.86,  "today_cpc": 0.1109},
]
TOTAL = {"gtv": 1604.59, "target": 1840.50, "today_gtv": 28.70, "today_cpc": 1.0871}

TODAY_SUMMARY = [
    ("今日CPC消耗额",   "1.09万",  "27.76%", True),
    ("今日CPM消耗额",   "0.01万",  "19.23%", True),
    ("今日MEM收款额",   "0.56万",  "67.31%", True),
    ("今日交易收入",    "1.83万",  "13.53%", True),
    ("今日实付验证GTV", "28.70万", "5.58%",  True),
    ("今日实付GTV",    "37.10万", "-13.56%",False),
]

# ── 颜色 ──────────────────────────────────────────────────────────────
C_BG        = (18, 24, 38)
C_TITLE_BG  = (30, 40, 65)
C_HEADER_BG = (210, 160, 30)
C_HEADER_FG = (255, 255, 255)
C_ROW_ODD   = (28, 36, 56)
C_ROW_EVEN  = (22, 30, 48)
C_TOTAL_BG  = (38, 50, 80)
C_WHITE     = (255, 255, 255)
C_GOLD      = (255, 200, 40)
C_LIGHT     = (180, 200, 230)
C_RED_GAP   = (255, 100, 100)
C_CYAN      = (80, 200, 255)
C_GREEN_VAL = (80, 220, 140)
C_RED_VAL   = (255, 110, 110)
C_BORDER    = (50, 65, 100)

# 进度条色
def bar_color(pct):
    if pct >= 0.93: return (50, 200, 100)
    if pct >= 0.85: return (220, 170, 30)
    if pct >= 0.75: return (220, 120, 30)
    return (200, 60, 60)

# ── 字体 ──────────────────────────────────────────────────────────────
def get_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for p in paths:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except: pass
    return ImageFont.load_default()

# ── 画布尺寸 ──────────────────────────────────────────────────────────
W = 1120
PAD = 28
ROW_H = 44
HDR_H = 42

# 列宽（表1）
COL_W = [140, 110, 110, 210, 105, 100, 100]
COL_LABELS = ["代运营商", "月累计GTV", "月目标", "月完成率", "日均缺口", "今日GTV", "今日CPC"]

# 表1高：header + 7行 + 合计行
T1_H = HDR_H + ROW_H * 7 + ROW_H  # 8行

# 表2行数：6
T2_COL_W = [260, 180, 160]
T2_LABELS = ["指标", "今日金额", "日环比"]
T2_H = HDR_H + ROW_H * 6

# 总高
TITLE_H = 80
SUB_H   = 36
SEP     = 18
SEC_H   = 38
FOOTER_H= 40

TOTAL_H = TITLE_H + SUB_H + SEP + SEC_H + T1_H + SEP*2 + SEC_H + T2_H + SEP + FOOTER_H + PAD*2

img = Image.new("RGB", (W, TOTAL_H), C_BG)
draw = ImageDraw.Draw(img)

f_title  = get_font(28, bold=True)
f_sub    = get_font(15)
f_hdr    = get_font(15, bold=True)
f_cell   = get_font(15)
f_cell_b = get_font(15, bold=True)
f_sec    = get_font(16, bold=True)
f_footer = get_font(13)

def text_w(text, font):
    bb = font.getbbox(text)
    return bb[2] - bb[0]

def draw_cell(x, y, w, h, text, font, fg, bg, align="center"):
    draw.rectangle([x, y, x+w-1, y+h-1], fill=bg)
    tw = text_w(text, font)
    if align == "center":
        tx = x + (w - tw) // 2
    elif align == "right":
        tx = x + w - tw - 8
    else:
        tx = x + 8
    draw.text((tx, y + (h - 16) // 2), text, font=font, fill=fg)

def draw_bar(x, y, w, h, pct):
    """Draw a progress bar with % label above it"""
    bx, by = x + 6, y + h//2 - 7
    bw, bh = w - 12, 14
    # bg
    draw.rectangle([bx, by, bx+bw, by+bh], fill=(50, 60, 90))
    # fill
    filled = int(bw * min(pct, 1.0))
    if filled > 0:
        color = bar_color(pct)
        draw.rectangle([bx, by, bx+filled, by+bh], fill=color)
    # label
    label = f"{pct*100:.1f}%"
    lw = text_w(label, f_cell_b)
    lx = x + (w - lw) // 2
    draw.text((lx, y + (h - 16) // 2 - 10), label, font=f_cell_b, fill=C_WHITE)

def hline(y, x1=PAD, x2=W-PAD, color=C_BORDER):
    draw.line([(x1, y), (x2, y)], fill=color, width=1)

y = PAD

# ── 大标题 ────────────────────────────────────────────────────────────
draw.rectangle([PAD, y, W-PAD, y+TITLE_H-4], fill=C_TITLE_BG)
title = "粤闽浙城市群  实时进度看板"
tw = text_w(title, f_title)
draw.text(((W - tw)//2, y + 14), title, font=f_title, fill=C_GOLD)
y += TITLE_H

# ── 副标题 ────────────────────────────────────────────────────────────
sub = f"数据更新至 {TODAY} {DATA_TIME}  │  今日剩余 {DAYS_LEFT} 天  │  时间进度 87.1%"
sw = text_w(sub, f_sub)
draw.text(((W - sw)//2, y + 8), sub, font=f_sub, fill=C_LIGHT)
y += SUB_H + SEP

# ── 表1标题栏 ─────────────────────────────────────────────────────────
sec_label = "▌ GTV & CPC 实时进度  （数据截至" + DATA_TIME + "）"
draw.rectangle([PAD, y, W-PAD, y+SEC_H-1], fill=(35, 50, 85))
draw.text((PAD+12, y+10), sec_label, font=f_sec, fill=C_GOLD)
y += SEC_H

# ── 表1 ──────────────────────────────────────────────────────────────
tx = PAD
# header
for i, (cw, label) in enumerate(zip(COL_W, COL_LABELS)):
    draw_cell(tx, y, cw, HDR_H, label, f_hdr, C_HEADER_FG, C_HEADER_BG)
    draw.line([(tx+cw, y), (tx+cw, y+HDR_H)], fill=C_BG, width=1)
    tx += cw
y += HDR_H

for ri, op in enumerate(OPERATORS):
    bg = C_ROW_ODD if ri % 2 == 0 else C_ROW_EVEN
    pct = op["gtv"] / op["target"]
    gap = (op["target"] - op["gtv"]) / DAYS_LEFT
    row_data = [
        op["name"],
        f"{op['gtv']:.2f}万",
        f"{op['target']:.2f}万",
        None,  # bar
        f"{gap:.2f}万",
        f"{op['today_gtv']:.2f}万",
        f"{op['today_cpc']:.4f}万",
    ]
    tx = PAD
    for ci, (cw, val) in enumerate(zip(COL_W, row_data)):
        draw.rectangle([tx, y, tx+cw-1, y+ROW_H-1], fill=bg)
        draw.line([(tx+cw-1, y), (tx+cw-1, y+ROW_H)], fill=C_BORDER, width=1)
        if val is None:
            draw_bar(tx, y, cw, ROW_H, pct)
        else:
            fg = C_WHITE
            if ci == 4:  fg = C_RED_GAP
            if ci == 5 and op["today_gtv"] < 3: fg = C_RED_VAL
            font = f_cell_b if ci == 0 else f_cell
            draw_cell(tx, y, cw, ROW_H, val, font, fg, bg, "center" if ci != 0 else "center")
        tx += cw
    hline(y+ROW_H-1, PAD, W-PAD, C_BORDER)
    y += ROW_H

# 合计行
pct_total = TOTAL["gtv"] / TOTAL["target"]
gap_total = (TOTAL["target"] - TOTAL["gtv"]) / DAYS_LEFT
total_data = [
    "合  计",
    f"{TOTAL['gtv']:.2f}万",
    f"{TOTAL['target']:.2f}万",
    None,
    f"{gap_total:.2f}万",
    f"{TOTAL['today_gtv']:.2f}万",
    f"{TOTAL['today_cpc']:.4f}万",
]
tx = PAD
for ci, (cw, val) in enumerate(zip(COL_W, total_data)):
    draw.rectangle([tx, y, tx+cw-1, y+ROW_H-1], fill=C_TOTAL_BG)
    draw.line([(tx+cw-1, y), (tx+cw-1, y+ROW_H)], fill=C_BORDER, width=1)
    if val is None:
        draw_bar(tx, y, cw, ROW_H, pct_total)
    else:
        fg = C_GOLD if ci == 0 else C_WHITE
        if ci == 4: fg = C_RED_GAP
        draw_cell(tx, y, cw, ROW_H, val, f_cell_b, fg, C_TOTAL_BG)
    tx += cw
hline(y+ROW_H-1, PAD, W-PAD, C_BORDER)
y += ROW_H

y += SEP * 2

# ── 表2标题栏 ─────────────────────────────────────────────────────────
sec2_label = "▌ 今日实时汇总  （高线粤闽浙城市群整体）"
draw.rectangle([PAD, y, W-PAD, y+SEC_H-1], fill=(35, 50, 85))
draw.text((PAD+12, y+10), sec2_label, font=f_sec, fill=C_GOLD)
y += SEC_H

# 表2居中
t2_total_w = sum(T2_COL_W)
t2_x = (W - t2_total_w) // 2

# header
tx = t2_x
for cw, label in zip(T2_COL_W, T2_LABELS):
    draw_cell(tx, y, cw, HDR_H, label, f_hdr, C_HEADER_FG, C_HEADER_BG)
    draw.line([(tx+cw, y), (tx+cw, y+HDR_H)], fill=C_BG, width=1)
    tx += cw
y += HDR_H

for ri, (label, amount, ratio, up) in enumerate(TODAY_SUMMARY):
    bg = C_ROW_ODD if ri % 2 == 0 else C_ROW_EVEN
    tx = t2_x
    # 指标名
    draw_cell(tx, y, T2_COL_W[0], ROW_H, label, f_cell, C_WHITE, bg)
    draw.line([(tx+T2_COL_W[0], y), (tx+T2_COL_W[0], y+ROW_H)], fill=C_BORDER, width=1)
    tx += T2_COL_W[0]
    # 金额
    draw_cell(tx, y, T2_COL_W[1], ROW_H, amount, f_cell_b, C_CYAN, bg)
    draw.line([(tx+T2_COL_W[1], y), (tx+T2_COL_W[1], y+ROW_H)], fill=C_BORDER, width=1)
    tx += T2_COL_W[1]
    # 环比
    arrow = "↑" if up else "↓"
    ratio_str = ratio + arrow
    fg_ratio = C_GREEN_VAL if up else C_RED_VAL
    draw_cell(tx, y, T2_COL_W[2], ROW_H, ratio_str, f_cell_b, fg_ratio, bg)
    hline(y+ROW_H-1, t2_x, t2_x+t2_total_w, C_BORDER)
    y += ROW_H

y += SEP

# ── 底部 footer ───────────────────────────────────────────────────────
now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
footer = f"✦ 自动生成  │  {now_str}  │  粤闽浙城市群实时看板"
fw = text_w(footer, f_footer)
draw.text(((W - fw)//2, y + 10), footer, font=f_footer, fill=(80, 100, 140))

# ── 外边框 ────────────────────────────────────────────────────────────
draw.rectangle([PAD-2, PAD-2, W-PAD+2, TOTAL_H-PAD+2], outline=(60, 80, 130), width=2)

out = "/tmp/files/today_board.png"
img.save(out, "PNG")
print(f"保存: {out}  尺寸: {W}x{TOTAL_H}")
