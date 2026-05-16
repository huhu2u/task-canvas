import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from collections import defaultdict

wb_src = openpyxl.load_workbook('/tmp/files/haodian_score_0408.xlsx', data_only=True)
ws_src = wb_src['Sheet0']
rows = list(ws_src.iter_rows(values_only=True))
headers = rows[0]
data = rows[1:]

col_map = {h: i for i, h in enumerate(headers) if h}
score_col = col_map['\u7ecf\u8425\u8bc4\u5206\u5206\u6570']
org_col = col_map['\u7ec4\u7ec7']
shop_col = col_map['\u5546\u6237\u540d']
shopid_col = col_map['shopId']
gtv_col = col_map['\u8fd130\u65e5\u5b9e\u4ed8\u9a8c\u8bc1GTV']
zrq_col = col_map['\u804c\u4eba\u7801\u6838\u9500\u8ba2\u5355\u6570(\u5254\u9664\u98ce\u63a7+\u9000\u6b3e)']
sales_col = col_map['\u8ddf\u8fdb\u9500\u552e']

OP_KEYS = {
    ('\u60e0\u5dde', '\u5de8\u6d6a'): '\u60e0\u5dde\u5de8\u6d6a',
    ('\u60e0\u5dde', '\u67cf\u4e07'): '\u60e0\u5dde\u67cf\u4e07',
    ('\u6cc9\u5dde', '\u5c0f\u82b1\u732b'): '\u6cc9\u5dde\u5c0f\u82b1\u732b',
    ('\u60e0\u5b89', '\u5e7f\u901a'): '\u60e0\u5b89\u5e7f\u901a',
    ('\u6148\u6eaa', '\u54f2\u5149'): '\u6148\u6eaa\u54f2\u5149',
    ('\u4e49\u4e4c', '\u6c50\u6d0b'): '\u4e49\u4e4c\u6c50\u6d0b',
}

# \u5f53\u524d\u8fbe\u6807\u6570\u548c\u589e\u91cf\u76ee\u6807\u6765\u81ea\u56fe\u7247
OP_TARGETS = {
    '\u60e0\u5dde\u5de8\u6d6a': {'hc': 9, 'per': 3, 'current': 219, 'incr': 27},
    '\u60e0\u5dde\u67cf\u4e07': {'hc': 7, 'per': 3, 'current': 135, 'incr': 21},
    '\u4e49\u4e4c\u6c50\u6d0b': {'hc': 9, 'per': 4, 'current': 125, 'incr': 36},
    '\u60e0\u5b89\u5e7f\u901a': {'hc': 5, 'per': 4, 'current': 96,  'incr': 20},
    '\u6cc9\u5dde\u5c0f\u82b1\u732b': {'hc': 7, 'per': 4, 'current': 147, 'incr': 28},
    '\u6148\u6eaa\u54f2\u5149': {'hc': 9, 'per': 5, 'current': 116, 'incr': 45},
}
ORDER = ['\u60e0\u5dde\u5de8\u6d6a','\u60e0\u5dde\u67cf\u4e07','\u4e49\u4e4c\u6c50\u6d0b','\u60e0\u5b89\u5e7f\u901a','\u6cc9\u5dde\u5c0f\u82b1\u732b','\u6148\u6eaa\u54f2\u5149']

def get_op(org):
    for (city, kw), name in OP_KEYS.items():
        if city in str(org) and kw in str(org):
            return name
    return None

def safe_float(v):
    try:
        s = str(v).replace('-','').strip()
        return float(s) if s else 0.0
    except:
        return 0.0

op_shops = defaultdict(list)
for r in data:
    op = get_op(r[org_col])
    if not op:
        continue
    score = safe_float(r[score_col])
    gtv = safe_float(r[gtv_col])
    sales_raw = str(r[sales_col]) if r[sales_col] else ''
    sales_name = sales_raw.split('/')[0].strip() if '/' in sales_raw else sales_raw
    op_shops[op].append({
        'shop': r[shop_col], 'shopid': r[shopid_col],
        'org': r[org_col], 'score': score, 'gtv': gtv,
        'zrq': safe_float(r[zrq_col]), 'sales': sales_name,
    })

wb = openpyxl.Workbook()
wb.remove(wb.active)

C_WHITE = 'FFFFFFFF'
C_GREEN_BG = 'FFdcfce7'; C_GREEN_FG = 'FF166534'
C_YELLOW_BG = 'FFfef9c3'; C_YELLOW_FG = 'FF92400e'
C_RED_BG = 'FFfee2e2'; C_RED_FG = 'FFb91c1c'
C_GRAY_BG = 'FFF8FAFC'
C_BLUE_BG = 'FFe0f2fe'; C_BLUE_FG = 'FF1D4ED8'

def thin_border(color='FFD1D5DB'):
    s = Side(style='thin', color=color)
    return Border(left=s, right=s, top=s, bottom=s)

def hdr_cell(ws, row, col, val, bg='FF1D4ED8'):
    c = ws.cell(row=row, column=col, value=val)
    c.font = Font(name='Arial', bold=True, size=9, color='FFFFFFFF')
    c.fill = PatternFill('solid', start_color=bg[2:] if bg.startswith('FF') else bg)
    c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    c.border = thin_border('FF93C5FD')
    return c

def std_cell(ws, row, col, val, bg=None, fg='FF000000', bold=False, size=10, fmt=None, align='center'):
    c = ws.cell(row=row, column=col, value=val)
    c.font = Font(name='Arial', bold=bold, size=size, color=fg)
    if bg:
        c.fill = PatternFill('solid', start_color=bg[2:] if bg.startswith('FF') else bg)
    c.alignment = Alignment(horizontal=align, vertical='center')
    c.border = thin_border()
    if fmt:
        c.number_format = fmt
    return c

# ====== Sheet1: \u4ee3\u8fd0\u8425\u5546\u6c47\u603b ======
ws1 = wb.create_sheet('\u4ee3\u8fd0\u8425\u5546\u6c47\u603b')
ws1.merge_cells('A1:L1')
ws1['A1'].value = '\u597d\u5e97\u7ecf\u8425\u8bc4\u5206\u5206\u6790\u2014\u2014\u4ee3\u8fd0\u8425\u5546\u6c47\u603b\uff082026-04-08\uff09'
ws1['A1'].font = Font(name='Arial', bold=True, size=13, color='FFFFFFFF')
ws1['A1'].fill = PatternFill('solid', start_color='0F172A')
ws1['A1'].alignment = Alignment(horizontal='center', vertical='center')
ws1.row_dimensions[1].height = 32

hdrs1 = [
    '\u4ee3\u8fd0\u8425\u5546', 'HC', '\u4eba\u6548\u76ee\u6807',
    '\u7269\u7406\u597d\u5e97\u6570',
    '\u5f53\u524d\u8fbe\u6807\u6570\n(\u226570\u5206)',
    '\u5f53\u524d\u8fbe\u6807\u7387',
    '4\u6708\u589e\u91cf\u76ee\u6807\n(HC\u00d7\u4eba\u6548)',
    '4\u6708\u6700\u7ec8\u9700\u8fbe\u6807\n(\u5f53\u524d+\u589e\u91cf)',
    '\u76ee\u6807\u7f3a\u53e3\n(\u5f53\u524d-\u6700\u7ec8\u76ee\u6807)',
    '\u4f18\u5148\u7ea7\u505a\u5de5\n(50~69\u5206)',
    '\u5c1a\u9700\u5173\u6ce8\n(<50\u5206)',
    '\u5e73\u5747\u8bc4\u5206'
]
for j, h in enumerate(hdrs1, 1):
    hdr_cell(ws1, 2, j, h)
ws1.row_dimensions[2].height = 44

for i, op in enumerate(ORDER):
    row = i + 3
    shops = op_shops[op]
    tgt = OP_TARGETS[op]
    current = tgt['current']
    incr = tgt['incr']
    final_target = current + incr
    gap = current - final_target  # = -incr
    n = len(shops)
    has_score = [s for s in shops if s['score'] > 0]
    gte70 = sum(1 for s in shops if s['score'] >= 70)
    s50_69 = sum(1 for s in shops if 50 <= s['score'] < 70)
    lt50 = sum(1 for s in shops if 0 < s['score'] < 50)
    avg = sum(s['score'] for s in has_score) / len(has_score) if has_score else 0
    rate = current / n if n > 0 else 0
    bg = C_GRAY_BG if i % 2 == 0 else C_WHITE

    std_cell(ws1, row, 1, op, bg=bg, bold=True)
    std_cell(ws1, row, 2, tgt['hc'], bg=bg)
    std_cell(ws1, row, 3, tgt['per'], bg=bg)
    std_cell(ws1, row, 4, n, bg=bg)
    std_cell(ws1, row, 5, current, bg=bg, bold=True)

    # \u5f53\u524d\u8fbe\u6807\u7387
    if rate >= 0.28:
        std_cell(ws1, row, 6, rate, bg=C_GREEN_BG, fg=C_GREEN_FG, fmt='0.0%')
    elif rate >= 0.22:
        std_cell(ws1, row, 6, rate, bg=C_YELLOW_BG, fg=C_YELLOW_FG, fmt='0.0%')
    else:
        std_cell(ws1, row, 6, rate, bg=C_RED_BG, fg=C_RED_FG, fmt='0.0%')

    std_cell(ws1, row, 7, incr, bg=bg)

    # 4\u6708\u6700\u7ec8\u9700\u8fbe\u6807 (\u8513\u84dd\u9ad8\u4eae)
    std_cell(ws1, row, 8, final_target, bg=C_BLUE_BG, fg=C_BLUE_FG, bold=True)

    # \u76ee\u6807\u7f3a\u53e3
    if gap >= 0:
        std_cell(ws1, row, 9, gap, bg=C_GREEN_BG, fg=C_GREEN_FG, bold=True)
    elif gap >= -20:
        std_cell(ws1, row, 9, gap, bg=C_YELLOW_BG, fg=C_YELLOW_FG, bold=True)
    else:
        std_cell(ws1, row, 9, gap, bg=C_RED_BG, fg=C_RED_FG, bold=True)

    std_cell(ws1, row, 10, s50_69, bg=bg)
    std_cell(ws1, row, 11, lt50, bg=bg)
    std_cell(ws1, row, 12, round(avg, 1), bg=bg)
    ws1.row_dimensions[row].height = 22

# \u6c47\u603b\u884c
sr = len(ORDER) + 3
t_n = sum(len(op_shops[op]) for op in ORDER)
t_cur = sum(OP_TARGETS[op]['current'] for op in ORDER)
t_incr = sum(OP_TARGETS[op]['incr'] for op in ORDER)
t_final = t_cur + t_incr
t_gap = t_cur - t_final
t_50 = sum(sum(1 for s in op_shops[op] if 50 <= s['score'] < 70) for op in ORDER)
t_lt50 = sum(sum(1 for s in op_shops[op] if 0 < s['score'] < 50) for op in ORDER)
all_scores = [s['score'] for op in ORDER for s in op_shops[op] if s['score'] > 0]
t_avg = sum(all_scores) / len(all_scores) if all_scores else 0

for j, v in enumerate(['\u5408\u8ba1', '-', '-', t_n, t_cur, t_cur/t_n, t_incr, t_final, t_gap, t_50, t_lt50, round(t_avg, 1)], 1):
    c = ws1.cell(row=sr, column=j, value=v)
    c.font = Font(name='Arial', bold=True, size=10, color='FFFFFFFF')
    c.fill = PatternFill('solid', start_color='334155')
    if j == 6:
        c.number_format = '0.0%'
    c.alignment = Alignment(horizontal='center', vertical='center')
    c.border = thin_border('FF64748B')
ws1.row_dimensions[sr].height = 24

for j, w in enumerate([14, 5, 8, 12, 14, 10, 14, 20, 18, 16, 14, 10], 1):
    ws1.column_dimensions[get_column_letter(j)].width = w

note_row = sr + 2
ws1.cell(row=note_row, column=1).value = '\u8bf4\u660e\uff1a4\u6708\u6700\u7ec8\u9700\u8fbe\u6807=\u5f53\u524d\u8fbe\u6807\u6570+4\u6708\u589e\u91cf\u76ee\u6807\uff1b\u76ee\u6807\u7f3a\u53e3=\u5f53\u524d\u8fbe\u6807\u6570-4\u6708\u6700\u7ec8\u76ee\u6807\uff08\u8d1f\u6570\u8868\u793a\u8fd8\u5dee\u591a\u5c11\uff09\uff1b\u6570\u636e\u65e5\u671f\uff1a2026-04-08'
ws1.cell(row=note_row, column=1).font = Font(name='Arial', size=9, color='FF64748B', italic=True)

# ====== Sheet2: \u9500\u552e\u7ef4\u5ea6 ======
ws2 = wb.create_sheet('\u9500\u552e\u7ef4\u5ea6\u5206\u6790')
ws2.merge_cells('A1:J1')
ws2['A1'].value = '\u597d\u5e97\u7ecf\u8425\u8bc4\u5206\u5206\u6790\u2014\u2014\u9500\u552e\u7ef4\u5ea6\uff082026-04-08\uff09'
ws2['A1'].font = Font(name='Arial', bold=True, size=13, color='FFFFFFFF')
ws2['A1'].fill = PatternFill('solid', start_color='0F172A')
ws2['A1'].alignment = Alignment(horizontal='center', vertical='center')
ws2.row_dimensions[1].height = 32

hdrs2 = ['\u4ee3\u8fd0\u8425\u5546', '\u9500\u552e\u59d3\u540d', '\u8d1f\u8d23\u95e8\u5e97\u6570',
         '\u226570\u5206', '50~69\u5206', '<50\u5206',
         '\u8fbe\u6807\u7387', '\u5e73\u5747\u8bc4\u5206', '\u6709GTV\u4f46<60\u5206\u6570', '\u5c45\u5148TOP3\u95e8\u5e97']
for j, h in enumerate(hdrs2, 1):
    hdr_cell(ws2, 2, j, h)
ws2.row_dimensions[2].height = 36

row = 3
for op in ORDER:
    sales_map = defaultdict(list)
    for s in op_shops[op]:
        sales_map[s['sales']].append(s)
    for sname in sorted(sales_map.keys()):
        shops = sales_map[sname]
        n = len(shops)
        gte70 = sum(1 for s in shops if s['score'] >= 70)
        s50_69 = sum(1 for s in shops if 50 <= s['score'] < 70)
        lt50 = sum(1 for s in shops if 0 < s['score'] < 50)
        has_s = [s for s in shops if s['score'] > 0]
        avg = sum(s['score'] for s in has_s) / len(has_s) if has_s else 0
        rate = gte70 / n if n > 0 else 0
        low_gtv = sum(1 for s in shops if s['gtv'] > 0 and 0 < s['score'] < 60)
        top3 = sorted([s for s in shops if s['score'] >= 70], key=lambda x: x['score'], reverse=True)[:3]
        top3_str = ', '.join(s['shop'][:8] for s in top3) if top3 else '-'
        bg = C_GRAY_BG if row % 2 == 0 else C_WHITE
        for j, v in enumerate([op, sname, n, gte70, s50_69, lt50, rate, round(avg,1), low_gtv, top3_str], 1):
            c = ws2.cell(row=row, column=j, value=v)
            c.font = Font(name='Arial', size=9, bold=(j <= 2))
            if j == 7:
                if rate >= 0.28: cb,cf = C_GREEN_BG, C_GREEN_FG
                elif rate >= 0.22: cb,cf = C_YELLOW_BG, C_YELLOW_FG
                else: cb,cf = C_RED_BG, C_RED_FG
                c.fill = PatternFill('solid', start_color=cb[2:])
                c.font = Font(name='Arial', size=9, color=cf)
                c.number_format = '0.0%'
            else:
                c.fill = PatternFill('solid', start_color=bg[2:])
            c.alignment = Alignment(horizontal='center' if j != 10 else 'left', vertical='center', wrap_text=(j==10))
            c.border = thin_border()
        ws2.row_dimensions[row].height = 20
        row += 1

for j, w in enumerate([14,12,10,8,8,8,8,10,14,30], 1):
    ws2.column_dimensions[get_column_letter(j)].width = w

# ====== Sheet3: 优先级做工（50-69分）======
ws3 = wb.create_sheet('\u4f18\u5148\u7ea7\u505a\u5de5\uff0850-69\u5206\uff09')
ws3.merge_cells('A1:H1')
ws3['A1'].value = '\u4f18\u5148\u7ea7\u505a\u5de5\u95e8\u5e97\uff0850~69\u5206\uff0c\u8865\u9f50\u8bc4\u5206\u6548\u7387\u6700\u9ad8\uff09\u2014\u2014 2026-04-08'
ws3['A1'].font = Font(name='Arial', bold=True, size=12, color='FFFFFFFF')
ws3['A1'].fill = PatternFill('solid', start_color='065F46')
ws3['A1'].alignment = Alignment(horizontal='center', vertical='center')
ws3.row_dimensions[1].height = 30

hdrs3 = ['\u4ee3\u8fd0\u8425\u5546','\u95e8\u5e97\u540d\u79f0','\u8bc4\u5206','\u8ddf\u8fdb\u9500\u552e','\u8fd130\u65e5GTV','\u804c\u4eba\u7801\u8ba2\u5355','\u7ec4\u7ec7\u540d\u79f0','\u5907\u6ce8']
for j, h in enumerate(hdrs3, 1):
    c = ws3.cell(row=2, column=j, value=h)
    c.font = Font(name='Arial', bold=True, size=9, color='FFFFFFFF')
    c.fill = PatternFill('solid', start_color='059669')
    c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    c.border = thin_border('FF6EE7B7')
ws3.row_dimensions[2].height = 30

row = 3
for op in ORDER:
    priority = sorted([s for s in op_shops[op] if 50 <= s['score'] < 70], key=lambda x: x['score'], reverse=True)
    for s in priority:
        if s['score'] >= 65: bg='dcfce7'; remark='\u63a5\u8fd130\u5206\u8fbe\u6807'
        elif s['score'] >= 60: bg='fef9c3'; remark='\u8fdb\u5c55\u4e2d'
        else: bg='fff7ed'; remark='\u9700\u91cd\u70b9\u8ddf\u8fdb'
        vals = [op, s['shop'], s['score'], s['sales'], s['gtv'], int(s['zrq']) if s['zrq'] else 0, str(s['org']), remark]
        for j, v in enumerate(vals, 1):
            c = ws3.cell(row=row, column=j, value=v)
            c.font = Font(name='Arial', size=9, bold=(j==3))
            c.fill = PatternFill('solid', start_color=bg)
            if j == 5: c.number_format = '#,##0'
            c.alignment = Alignment(horizontal='center' if j in [1,3,4,8] else 'left', vertical='center')
            c.border = thin_border()
        ws3.row_dimensions[row].height = 18
        row += 1

for j, w in enumerate([14,22,8,12,12,10,30,12], 1):
    ws3.column_dimensions[get_column_letter(j)].width = w

# ====== Sheet4: 原始表格 ======
ws4 = wb.create_sheet('\u539f\u59cb\u8868\u683c')
for j, h in enumerate(headers, 1):
    c = ws4.cell(row=1, column=j, value=h)
    c.font = Font(name='Arial', bold=True, size=8, color='FFFFFFFF')
    c.fill = PatternFill('solid', start_color='334155')
    c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
ws4.row_dimensions[1].height = 28

op_id_set = set(str(s['shopid']) for op in ORDER for s in op_shops[op])
sorted_data = []
for op in ORDER:
    for s in sorted(op_shops[op], key=lambda x: x['score'], reverse=True):
        for r in data:
            if str(r[shopid_col]) == str(s['shopid']) and str(r[shop_col]) == s['shop']:
                sorted_data.append(r)
                break
for r in data:
    if str(r[shopid_col]) not in op_id_set:
        sorted_data.append(r)

for i, r in enumerate(sorted_data, 2):
    bg = 'F8FAFC' if i % 2 == 0 else 'FFFFFF'
    for j, v in enumerate(r, 1):
        c = ws4.cell(row=i, column=j, value=v)
        c.font = Font(name='Arial', size=8)
        c.fill = PatternFill('solid', start_color=bg)
        c.alignment = Alignment(horizontal='center', vertical='center')
        c.border = thin_border('FFE2E8F0')

ws4.freeze_panes = 'A2'
for j in range(1, len(headers)+1):
    ws4.column_dimensions[get_column_letter(j)].width = 12

out = '/tmp/files/\u597d\u5e97\u7ecf\u8425\u8bc4\u5206\u5206\u6790_20260408_v2.xlsx'
wb.save(out)
print(f"OK: {out}")
print(f"Sheet3 rows: {row-3}")
