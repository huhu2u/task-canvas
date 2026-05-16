#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
粤闽浙城市群业绩看板 v27
列结构（定稿）：
  GTV(8列)：代运营商|负责人|本月GTV|月度目标|GTV进度(条+%)|日缺口|昨日GTV|GTV剔除率
  CPC(8列)：代运营商|负责人|CPC&QCPS|月度目标|CPC进度(条+%)|日缺口|有效新签|旺铺通
  MEM(5列)：代运营商|负责人|MEM收款额|MEM续约率|续约率月环比
进度条：百分比在条上方，色阶≥90%绿/80-90%黄/70-80%橙/<70%红
续约率口径：MEM付费版续约率（2026-04-06英杰确认，加权平均13.43%）
"""
from PIL import Image, ImageDraw, ImageFont
from datetime import date

FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
def F(size): return ImageFont.truetype(FONT_PATH, size)

import calendar as _cal
TODAY = date.today()
_last_day = _cal.monthrange(TODAY.year, TODAY.month)[1]
DAYS_LEFT = (date(TODAY.year, TODAY.month, _last_day) - TODAY).days + 1
DATA_TIME = TODAY.strftime("%Y-%m-%d") + " 实时"

# ── 代运营商数据（Apollo 2026-05-11 09:39更新） ──
OPS = [
    {"name": "惠州巨浪",   "owner": "肖立铭",  "gtv": 1263214, "gtv_tgt": 3922600, "gtv_y": 147453, "excl": 0.0457,  "cpc": 28462,  "cpc_tgt": 58740,  "cpc_y": 0, "cpc_newsgn": 6,  "cpc_new_tgt": 18, "cpc_wpu": 12479, "mem": 45529,  "mem_renewal": 0.5179, "mem_mom":  0.6687},
    {"name": "惠州柏万",   "owner": "林启梁",  "gtv": 1144504, "gtv_tgt": 3355000, "gtv_y": 116228, "excl": 0.0216,  "cpc": 35559,  "cpc_tgt": 88330,  "cpc_y": 0, "cpc_newsgn": 1,  "cpc_new_tgt": 14, "cpc_wpu": 11404, "mem": 48858,  "mem_renewal": 0.5208, "mem_mom":  0.0417},
    {"name": "泉州小花猫", "owner": "康子诚",  "gtv": 953513,  "gtv_tgt": 3089900, "gtv_y": 82393,  "excl": 0.0258,  "cpc": 37910,  "cpc_tgt": 123530, "cpc_y": 0, "cpc_newsgn": 3,  "cpc_new_tgt": 14, "cpc_wpu": 10626, "mem": 27400,  "mem_renewal": 0.4595, "mem_mom":  0.6081},
    {"name": "惠安广通",   "owner": "尤云生",  "gtv": 701599,  "gtv_tgt": 2477200, "gtv_y": 70355,  "excl": 0.0108,  "cpc": 24231,  "cpc_tgt": 51260,  "cpc_y": 0, "cpc_newsgn": 1,  "cpc_new_tgt": 10, "cpc_wpu": 7429,  "mem": 31329,  "mem_renewal": 0.5238, "mem_mom": -0.0833},
    {"name": "慈溪哲光",   "owner": "贾凌姗",  "gtv": 949516,  "gtv_tgt": 3891648, "gtv_y": 92465,  "excl": 0.0390,  "cpc": 43280,  "cpc_tgt": 158008, "cpc_y": 0, "cpc_newsgn": 5,  "cpc_new_tgt": 12, "cpc_wpu": 5941,  "mem": 44749,  "mem_renewal": 0.5172, "mem_mom":  0.0345},
    {"name": "义乌汐洋",   "owner": "陈铨",    "gtv": 1073777, "gtv_tgt": 3764960, "gtv_y": 121785, "excl": 0.0088,  "cpc": 52757,  "cpc_tgt": 139466, "cpc_y": 0, "cpc_newsgn": 2,  "cpc_new_tgt": 6,  "cpc_wpu": 11135, "mem": 39400,  "mem_renewal": 0.5385, "mem_mom":  0.0000},
]

def pct(v, t): return v / t if t else 0

def bar_color(p):
    if p >= 0.90: return (34, 197, 94)
    if p >= 0.80: return (250, 204, 21)
    if p >= 0.70: return (251, 146, 60)
    return (248, 113, 113)

def pct_color(p):
    if p >= 0.90: return (22, 163, 74)
    if p >= 0.80: return (161, 98, 7)
    if p >= 0.70: return (194, 65, 12)
    return (185, 28, 28)

def renewal_color(r):
    if r >= 0.80: return (22, 163, 74)
    if r >= 0.70: return (161, 98, 7)
    return (185, 28, 28)

def fmt_yuan(v):
    return f"{v:,.0f}"

def fmt_wan(v):
    return f"{v/10000:.2f}万"

def fmt_pct(p):
    return f"{p*100:.1f}%"

def fmt_mom(p):
    if p is None: return "—"
    sign = "▲" if p >= 0 else "▼"
    return f"{sign}{abs(p)*100:.1f}%"

# ── 画布参数 ──
W = 1600
PAD = 28
HDR_H = 36
ROW_H = 46
FOOT_H = 46
SEC_GAP = 36       # 表格间距
TITLE_H = 72       # 大标题行高
TABLE_TITLE_H = 40 # 表标题行高
BAR_W = 160
BAR_H = 14

# 颜色
BG        = (245, 247, 250)
CARD_BG   = (255, 255, 255)
HDR_BG    = (235, 240, 248)
FOOT_BG   = (179, 205, 255)
ROW_EVEN  = (255, 255, 255)
ROW_ODD   = (249, 251, 255)
BORDER    = (200, 212, 228)
TEXT_MAIN = (20,  30,  50)
TEXT_SUB  = (90, 110, 140)
TEXT_HDR  = (40,  60, 100)
ACCENT    = (59, 130, 246)
TABLE_TITLE_BG = (59, 130, 246)  # 蓝色表标题
TABLE_TITLE_FG = (255, 255, 255)

# ── 列宽定义 ──
# GTV表：代运营商|负责人|本月GTV(元)|月度目标|进度条|进度%|日缺口|昨日GTV|剔除率
GTV_COLS = [120, 80, 130, 130, BAR_W+40, 90, 100, 110, 80]
# CPC表：代运营商|负责人|CPC&QCPS(元)|月度目标|进度条|进度%|日缺口|有效新签|旺铺通
CPC_COLS = [120, 80, 120, 110, BAR_W+40, 90, 100, 90, 90]
# MEM表：代运营商|负责人|MEM收款额(元)|MEM续约率|续约率月环比
MEM_COLS = [120, 80, 150, 120, 120]

def table_width(cols): return sum(cols) + 2

def draw_bar(draw, x, y, w, h, p, label):
    """画进度条，label在条上方"""
    bc = bar_color(p)
    fill_w = int(w * min(p, 1.0))
    # 背景
    draw.rectangle([x, y, x+w, y+h], fill=(220, 230, 245), outline=BORDER)
    # 填充
    if fill_w > 0:
        draw.rectangle([x, y, x+fill_w, y+h], fill=bc)
    # 百分比文字在条上方
    txt = label
    tc = pct_color(p)
    draw.text((x + w//2, y - 3), txt, font=F(13), fill=tc, anchor="mb")

def draw_table_title(draw, x, y, w, h, title):
    draw.rectangle([x, y, x+w, y+h], fill=TABLE_TITLE_BG)
    draw.text((x + w//2, y + h//2), title, font=F(16), fill=TABLE_TITLE_FG, anchor="mm")

def col_x(cols, idx):
    return sum(cols[:idx])

def draw_header_row(draw, x, y, cols, labels, h=HDR_H):
    draw.rectangle([x, y, x+sum(cols), y+h], fill=HDR_BG)
    cx = x
    for i, (cw, lbl) in enumerate(zip(cols, labels)):
        draw.text((cx + cw//2, y + h//2), lbl, font=F(13), fill=TEXT_HDR, anchor="mm")
        if i < len(cols)-1:
            draw.line([(cx+cw, y), (cx+cw, y+h)], fill=BORDER, width=1)
        cx += cw
    draw.line([(x, y+h), (x+sum(cols), y+h)], fill=BORDER, width=1)

def draw_data_row(draw, x, y, cols, cells, row_idx, h=ROW_H, is_foot=False):
    bg = FOOT_BG if is_foot else (ROW_ODD if row_idx % 2 else ROW_EVEN)
    tw = sum(cols)
    draw.rectangle([x, y, x+tw, y+h], fill=bg)
    cx = x
    for i, (cw, cell) in enumerate(zip(cols, cells)):
        if isinstance(cell, tuple) and cell[0] == 'bar':
            # bar: ('bar', p, label)
            _, p, lbl = cell
            bx = cx + (cw - BAR_W)//2
            by = y + (h - BAR_H)//2 + 6
            draw_bar(draw, bx, by, BAR_W, BAR_H, p, lbl)
        elif isinstance(cell, tuple) and cell[0] == 'colored':
            # colored: ('colored', text, color)
            _, txt, color = cell
            draw.text((cx + cw//2, y + h//2), txt, font=F(15), fill=color, anchor="mm")
        else:
            txt = str(cell) if cell is not None else "—"
            fw = F(15) if not is_foot else F(15)
            draw.text((cx + cw//2, y + h//2), txt, font=fw, fill=TEXT_MAIN, anchor="mm")
        if i < len(cols)-1:
            draw.line([(cx+cw, y), (cx+cw, y+h)], fill=BORDER, width=1)
        cx += cw
    draw.line([(x, y+h), (x+sum(cols), y+h)], fill=BORDER, width=1)

def draw_outer_border(draw, x, y, w, h):
    draw.rectangle([x, y, x+w, y+h], outline=BORDER, width=2)

# ── 计算汇总 ──
total_gtv    = sum(o['gtv']       for o in OPS)
total_gtv_t  = sum(o['gtv_tgt']   for o in OPS)
total_gtv_y  = sum(o['gtv_y']     for o in OPS)
total_cpc    = sum(o['cpc']       for o in OPS)
total_cpc_t  = sum(o['cpc_tgt']   for o in OPS)
total_cpc_y  = sum(o['cpc_y']     for o in OPS)
total_new    = sum(o['cpc_newsgn'] for o in OPS)
total_new_t  = 0
total_wpu    = sum(o['cpc_wpu']   for o in OPS)
total_mem    = sum(o['mem']       for o in OPS)
# 整体续约率（用户确认值）
TOTAL_RENEWAL = 0.1343  # 付费版续约率加权平均，2026-04-06更新
TOTAL_RENEWAL_MOM = 0.0000  # 月环比暂无历史对比数据

# 计算画布高度
N = len(OPS)
def table_h(n): return HDR_H + n*ROW_H + FOOT_H

gtv_h  = TABLE_TITLE_H + table_h(N)
cpc_h  = TABLE_TITLE_H + table_h(N)
mem_h  = TABLE_TITLE_H + table_h(N)
CANVAS_H = TITLE_H + gtv_h + SEC_GAP + cpc_h + SEC_GAP + mem_h + PAD*2 + 10

img = Image.new("RGB", (W, CANVAS_H), BG)
draw = ImageDraw.Draw(img)

# ── 大标题 ──
draw.rectangle([0, 0, W, TITLE_H], fill=ACCENT)
draw.text((W//2, TITLE_H//2 - 6), "粤闽浙城市群 业绩看板", font=F(26), fill=(255,255,255), anchor="mm")
draw.text((W//2, TITLE_H//2 + 16), f"数据截至 {DATA_TIME}　剩余 {DAYS_LEFT} 天", font=F(14), fill=(200,220,255), anchor="mm")

y = TITLE_H + PAD

# ═══════════════ GTV 表 ═══════════════
TW_GTV = sum(GTV_COLS)
TX = (W - TW_GTV) // 2

draw_table_title(draw, TX, y, TW_GTV, TABLE_TITLE_H, "📊 GTV 月度进度")
y += TABLE_TITLE_H

gtv_hdrs = ["代运营商","负责人","本月GTV(元)","月度目标(元)","GTV进度","进度%","日缺口(元)","昨日GTV(元)","剔除率"]
draw_header_row(draw, TX, y, GTV_COLS, gtv_hdrs)
y += HDR_H

for i, o in enumerate(OPS):
    name  = o['name']; owner = o['owner']
    gtv_m = o['gtv'];  gtv_t = o['gtv_tgt']; gtv_y = o['gtv_y']; excl = o['excl']
    p_gtv = pct(gtv_m, gtv_t)
    gap   = (gtv_t - gtv_m) / DAYS_LEFT
    cells = [
        name, owner,
        fmt_yuan(gtv_m), fmt_yuan(gtv_t),
        ('bar', p_gtv, fmt_pct(p_gtv)),
        ('colored', fmt_pct(p_gtv), pct_color(p_gtv)),
        fmt_yuan(int(gap)),
        fmt_yuan(gtv_y),
        fmt_pct(excl),
    ]
    draw_data_row(draw, TX, y, GTV_COLS, cells, i)
    y += ROW_H

# 合计行
p_tot = pct(total_gtv, total_gtv_t)
gap_tot = (total_gtv_t - total_gtv) / DAYS_LEFT
foot_cells = [
    "合计", "—",
    fmt_yuan(total_gtv), fmt_yuan(total_gtv_t),
    ('bar', p_tot, fmt_pct(p_tot)),
    ('colored', fmt_pct(p_tot), pct_color(p_tot)),
    fmt_yuan(int(gap_tot)),
    fmt_yuan(total_gtv_y),
    "—",
]
draw_data_row(draw, TX, y, GTV_COLS, foot_cells, 0, h=FOOT_H, is_foot=True)
y += FOOT_H
draw_outer_border(draw, TX, TITLE_H+PAD+TABLE_TITLE_H, TW_GTV, HDR_H + N*ROW_H + FOOT_H)
y += SEC_GAP

# ═══════════════ CPC 表 ═══════════════
TW_CPC = sum(CPC_COLS)
TX_CPC = (W - TW_CPC) // 2

draw_table_title(draw, TX_CPC, y, TW_CPC, TABLE_TITLE_H, "📱 CPC 月度进度")
y += TABLE_TITLE_H

cpc_hdrs = ["代运营商","负责人","CPC&QCPS(元)","月度目标(元)","CPC进度","进度%","日缺口(元)","有效新签","旺铺通(元)"]
draw_header_row(draw, TX_CPC, y, CPC_COLS, cpc_hdrs)
y += HDR_H

cpc_y0 = y
for i, o in enumerate(OPS):
    name  = o['name']; owner = o['owner']
    cpc_m = o['cpc'];  cpc_t = o['cpc_tgt']; new = o['cpc_newsgn']; wpu = o['cpc_wpu']
    new_t = 0  # 有效新签目标暂不显示缺口
    p_cpc = pct(cpc_m, cpc_t)
    gap   = (cpc_t - cpc_m) / DAYS_LEFT
    new_gap = new_t - new
    new_str = f"{new:.0f}"
    new_color = (22,163,74)
    cells = [
        name, owner,
        fmt_yuan(cpc_m), fmt_yuan(cpc_t),
        ('bar', p_cpc, fmt_pct(p_cpc)),
        ('colored', fmt_pct(p_cpc), pct_color(p_cpc)),
        fmt_yuan(int(gap)),
        ('colored', new_str, new_color),
        fmt_yuan(wpu),
    ]
    draw_data_row(draw, TX_CPC, y, CPC_COLS, cells, i)
    y += ROW_H

p_cpc_tot = pct(total_cpc, total_cpc_t)
gap_cpc_tot = (total_cpc_t - total_cpc) / DAYS_LEFT
new_gap_tot = total_new_t - total_new
new_tot_str = f"{total_new}/{total_new_t}" + (f" ▲{-new_gap_tot}" if new_gap_tot <= 0 else f" ▼{new_gap_tot}")
cpc_foot = [
    "合计","—",
    fmt_yuan(total_cpc), fmt_yuan(total_cpc_t),
    ('bar', p_cpc_tot, fmt_pct(p_cpc_tot)),
    ('colored', fmt_pct(p_cpc_tot), pct_color(p_cpc_tot)),
    fmt_yuan(int(gap_cpc_tot)),
    ('colored', new_tot_str, pct_color(p_cpc_tot)),
    fmt_yuan(total_wpu),
]
draw_data_row(draw, TX_CPC, y, CPC_COLS, cpc_foot, 0, h=FOOT_H, is_foot=True)
y += FOOT_H
draw_outer_border(draw, TX_CPC, cpc_y0-HDR_H-TABLE_TITLE_H, TW_CPC, TABLE_TITLE_H+HDR_H+N*ROW_H+FOOT_H)
y += SEC_GAP

# ═══════════════ MEM 表 ═══════════════
TW_MEM = sum(MEM_COLS)
TX_MEM = (W - TW_MEM) // 2

draw_table_title(draw, TX_MEM, y, TW_MEM, TABLE_TITLE_H, "💰 MEM 收款与续约率")
y += TABLE_TITLE_H

mem_hdrs = ["代运营商","负责人","MEM收款额(元)","MEM续约率","续约率月环比"]
draw_header_row(draw, TX_MEM, y, MEM_COLS, mem_hdrs)
y += HDR_H

mem_y0 = y
for i, o in enumerate(OPS):
    name  = o['name']; owner = o['owner']
    mem_m = o['mem'];  renewal = o['mem_renewal']; mom = o.get('mem_mom', 0.0)
    rc = renewal_color(renewal)
    mom_str = fmt_mom(mom)
    mom_color = (22,163,74) if mom is not None and mom >= 0 else (185,28,28)
    cells = [
        name, owner,
        fmt_yuan(mem_m),
        ('colored', fmt_pct(renewal), rc),
        ('colored', mom_str, mom_color),
    ]
    draw_data_row(draw, TX_MEM, y, MEM_COLS, cells, i)
    y += ROW_H

mem_foot = [
    "合计","—",
    fmt_yuan(total_mem),
    ('colored', fmt_pct(TOTAL_RENEWAL), renewal_color(TOTAL_RENEWAL)),
    ('colored', f"▲{TOTAL_RENEWAL_MOM*100:.1f}%", (22,163,74)),
]
draw_data_row(draw, TX_MEM, y, MEM_COLS, mem_foot, 0, h=FOOT_H, is_foot=True)
y += FOOT_H
draw_outer_border(draw, TX_MEM, mem_y0-HDR_H-TABLE_TITLE_H, TW_MEM, TABLE_TITLE_H+HDR_H+N*ROW_H+FOOT_H)

out = "/tmp/files/dashboard_v27.png"
img.save(out)
print(f"saved: {out}  {W}x{CANVAS_H}")
