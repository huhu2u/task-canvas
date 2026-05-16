import sys, os
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from datetime import datetime

# csv_path 从命令行参数或默认路径
if len(sys.argv) > 1:
    arg = sys.argv[1]
    if os.path.isabs(arg):
        csv_path = arg
    elif os.path.exists(arg):
        csv_path = arg
    elif os.path.exists(os.path.join('/tmp/files', arg)):
        csv_path = os.path.join('/tmp/files', arg)
    else:
        csv_path = os.path.join('/tmp', arg)
else:
    csv_path = '/tmp/files/1776570035.csv'

# ── 1. 城市组数据（动态从CSV解析）─────────────────────────────────────
with open(csv_path, encoding='utf-8-sig') as f:
    all_lines = f.readlines()

# 解析「城市组铺设数据」段（pool/laid/ok）
city_agg = {}
in_city = False
for line in all_lines:
    s = line.strip()
    if s == '城市组铺设数据':
        in_city = True
        continue
    if in_city:
        if s == '' or (s and not s[0].isdigit() and '合作商管理组' not in s and '大区' not in s):
            if city_agg:
                in_city = False
            continue
        if '大区' in s:
            continue
        parts = s.split(',')
        if len(parts) >= 7:
            city_name = parts[2].strip()
            try:
                pool_ = int(parts[3].strip())
                laid_ = int(parts[4].strip())
                ok_   = int(parts[5].strip())
                city_agg[city_name] = {'pool': pool_, 'laid': laid_, 'ok': ok_}
            except:
                pass

# 解析「门店铺设明细」段，统计各城市群真实不合格数
import io
detail_start = None
for i, l in enumerate(all_lines):
    if l.strip() == '门店铺设明细':
        detail_start = i + 1
        break

df_detail = pd.read_csv(io.StringIO(''.join(all_lines[detail_start:]))) if detail_start else pd.DataFrame()

city_bad = {}
if not df_detail.empty and '审核状态' in df_detail.columns and '城市组' in df_detail.columns:
    bad_df = df_detail[df_detail['审核状态'] == '不合格']
    city_bad = bad_df.groupby('城市组').size().to_dict()

city_data = []
for city_name, vals in city_agg.items():
    city_data.append({
        'city': city_name,
        'pool': vals['pool'],
        'laid': vals['laid'],
        'ok':   vals['ok'],
        'bad':  city_bad.get(city_name, 0),
    })

# ── 2. 目标数据（来自截图）─────────────────────────────────────────────
targets = {
    # 5月目标：各城市群铺设门店池 × 55%（2026-05-07英杰确认）
    '高线苏鲁豫城市群': {'leader': '高子扬', 'hc': 54, 'work_pool': 2050, 'month_tgt': 1128, 'total_tgt': 1128, 'month_rate_tgt': 0.55, 'total_rate_tgt': 0.55},
    '高线苏皖城市群':   {'leader': '方广生', 'hc': 51, 'work_pool': 1799, 'month_tgt': 989,  'total_tgt': 989,  'month_rate_tgt': 0.55, 'total_rate_tgt': 0.55},
    '高线苏浙城市群':   {'leader': '于继龙', 'hc': 50, 'work_pool': 1682, 'month_tgt': 925,  'total_tgt': 925,  'month_rate_tgt': 0.55, 'total_rate_tgt': 0.55},
    '高线新甘蒙城市群': {'leader': '叶泽锋', 'hc': 40, 'work_pool': 1517, 'month_tgt': 834,  'total_tgt': 834,  'month_rate_tgt': 0.55, 'total_rate_tgt': 0.55},
    '高线粤海城市群':   {'leader': '张涛',   'hc': 54, 'work_pool': 1945, 'month_tgt': 1070, 'total_tgt': 1070, 'month_rate_tgt': 0.55, 'total_rate_tgt': 0.55},
    '高线粤闽浙城市群': {'leader': '胡英杰', 'hc': 46, 'work_pool': 1338, 'month_tgt': 736,  'total_tgt': 736,  'month_rate_tgt': 0.55, 'total_rate_tgt': 0.55},
}

# ── 3. 颜色 ──────────────────────────────────────────────────────────────
C_HEADER = '1E3A5F'
C_TOTAL  = '2C5282'
C_WHITE  = 'FFFFFF'
C_ALT    = 'EBF4FF'
C_GREEN  = 'C6EFCE'; FC_GREEN  = '276221'
C_YELLOW = 'FFEB9C'; FC_YELLOW = '9C6500'
C_RED    = 'FFC7CE'; FC_RED    = '9C0006'

def fill(hex_bg):
    return PatternFill('solid', fgColor=hex_bg)

thin = Side(style='thin', color='BDD7EE')
border = Border(left=thin, right=thin, top=thin, bottom=thin)

def bold_font(color='FFFFFF', size=10):
    return Font(bold=True, color=color, size=size)

def norm_font(color='000000', size=10):
    return Font(color=color, size=size)

def center():
    return Alignment(horizontal='center', vertical='center', wrap_text=True)

def rgt():
    return Alignment(horizontal='right', vertical='center')

def rate_color(ws, row, col, val, tgt, reverse=False):
    """val vs tgt 色阶，超tgt=绿，近tgt(90%以上)=黄，低=红"""
    cell = ws.cell(row=row, column=col)
    ratio = val / tgt if tgt else 0
    if ratio >= 1.0:
        cell.fill = fill(C_GREEN); cell.font = Font(color=FC_GREEN, size=10)
    elif ratio >= 0.85:
        cell.fill = fill(C_YELLOW); cell.font = Font(color=FC_YELLOW, size=10)
    else:
        cell.fill = fill(C_RED); cell.font = Font(color=FC_RED, size=10)
    cell.alignment = center()

# ── 4. 生成Excel ─────────────────────────────────────────────────────────
wb = Workbook()
ws = wb.active
ws.title = '高线物料铺设看板'

# 大标题
ws.merge_cells('A1:K1')
ws['A1'] = f'高线全区域物料铺设看板（{datetime.now().strftime("%Y-%m-%d")}）'
ws['A1'].font = Font(bold=True, color=C_WHITE, size=12)
ws['A1'].fill = fill(C_HEADER)
ws['A1'].alignment = center()
ws.row_dimensions[1].height = 28

# 表头（13列）
headers = [
    '城市群', '负责人',
    '铺设门店池', '铺设门店数', '✅合格门店数', '❌不合格门店数',
    '单月目标(数)', '单月完成进度', '单月缺口',
    '单月覆盖率目标', '单月覆盖率进度', '单月完成率', '达标'
]
for col, h in enumerate(headers, 1):
    cell = ws.cell(row=2, column=col, value=h)
    cell.font = bold_font()
    cell.fill = fill(C_HEADER)
    cell.alignment = center()
    cell.border = border
ws.row_dimensions[2].height = 40

# 排序
order = ['高线粤闽浙城市群','高线粤海城市群','高线新甘蒙城市群','高线苏皖城市群','高线苏浙城市群','高线苏鲁豫城市群']
city_map = {r['city']: r for r in city_data}

total_pool = total_laid = total_ok = total_month_tgt = total_bad = 0

for i, city_name in enumerate(order):
    r = city_map[city_name]
    t = targets[city_name]
    row = i + 3
    bg = C_WHITE if i % 2 == 0 else C_ALT

    month_tgt      = t['month_tgt']
    month_rate_tgt = t['month_rate_tgt']
    month_rate_act = r['ok'] / r['pool'] if r['pool'] else 0
    month_done_pct = r['ok'] / r['pool'] if r['pool'] else 0
    gap            = r['ok'] - month_tgt
    达标            = '✅' if month_rate_act >= month_rate_tgt else '❌'

    bad = r['bad']
    ratio = month_rate_act / month_rate_tgt if month_rate_tgt else 0
    vals = [
        city_name.replace('高线',''), t['leader'],
        r['pool'], r['laid'], r['ok'], bad,
        month_tgt, f"{month_done_pct*100:.1f}%", gap,
        f"{month_rate_tgt*100:.1f}%", f"{month_rate_act*100:.1f}%",
        f"{ratio*100:.1f}%", 达标
    ]

    for col, v in enumerate(vals, 1):
        cell = ws.cell(row=row, column=col, value=v)
        cell.fill = fill(bg)
        cell.border = border
        cell.font = norm_font()
        cell.alignment = center() if col in (1,2,8,10,11,12,13) else rgt()

    # 不合格门店数（无底色）
    ws.cell(row=row, column=6).alignment = rgt()

    # 单月完成进度（无底色）
    ws.cell(row=row, column=8).alignment = center()

    # 单月缺口色阶
    gc = ws.cell(row=row, column=9)
    if gap >= 0:
        gc.fill = fill(C_GREEN); gc.font = Font(color=FC_GREEN, size=10)
    elif gap >= -30:
        gc.fill = fill(C_YELLOW); gc.font = Font(color=FC_YELLOW, size=10)
    else:
        gc.fill = fill(C_RED); gc.font = Font(color=FC_RED, size=10)
    gc.alignment = rgt()

    # 单月覆盖率进度（无色阶，纯展示）
    ws.cell(row=row, column=11).alignment = center()

    # 单月完成率色阶（深色，对比明显）
    mc = ws.cell(row=row, column=12)
    if ratio >= 1.0:
        mc.fill = fill('00B050'); mc.font = Font(color='FFFFFF', size=10, bold=True)
    elif ratio >= 0.85:
        mc.fill = fill('FF8C00'); mc.font = Font(color='FFFFFF', size=10, bold=True)
    else:
        mc.fill = fill('FF6B6B'); mc.font = Font(color='FFFFFF', size=10, bold=True)
    mc.alignment = center()

    # 达标列（无底色，只显示 emoji）
    dc = ws.cell(row=row, column=13)
    dc.font = Font(size=11, bold=True)
    dc.alignment = center()

    ws.row_dimensions[row].height = 22
    total_pool += r['pool']; total_laid += r['laid']
    total_ok += r['ok']; total_month_tgt += month_tgt; total_bad += r['bad']

# 合计行
row = len(order) + 3
total_month_rate_tgt = 0.55  # 5月目标：55%
total_month_rate_act = total_ok / total_pool if total_pool else 0
total_done_pct = f"{total_ok/total_pool*100:.1f}%" if total_pool else '-'
total_gap = total_ok - total_month_tgt
# total_bad 已在循环中累加，无需重算
total_ratio = total_month_rate_act / total_month_rate_tgt if total_month_rate_tgt else 0
vals = [
    '高线区域合计', '李俊',
    total_pool, total_laid, total_ok, total_bad,
    total_month_tgt, total_done_pct, total_gap,
    f"{total_month_rate_tgt*100:.1f}%", f"{total_month_rate_act*100:.1f}%",
    f"{total_ratio*100:.1f}%",
    '✅' if total_month_rate_act >= total_month_rate_tgt else '❌'
]
for col, v in enumerate(vals, 1):
    cell = ws.cell(row=row, column=col, value=v)
    cell.font = bold_font()
    cell.fill = fill(C_TOTAL)
    cell.border = border
    cell.alignment = center() if col in (1,2,8,10,11,12,13) else rgt()
ws.row_dimensions[row].height = 24

# 列宽
widths = [16, 10, 12, 12, 14, 12, 12, 16, 10, 16, 16, 14, 8]
for i, w in enumerate(widths, 1):
    ws.column_dimensions[chr(64+i)].width = w


# ── Sheet2：粤闽浙代运营商下钻 ────────────────────────────────────────────
import pandas as pd

# 代运营商映射
ORG_MAP = {
    '惠州市巨浪': '惠州巨浪',
    '惠州市柏万': '惠州柏万',
    '泉州市小花猫': '泉州小花猫',
    '惠安广通':   '惠安广通',
    '慈溪哲光':   '慈溪哲光',
    '义乌市汐洋': '义乌汐洋',
}
ORG_ORDER = ['惠州巨浪','惠州柏万','泉州小花猫','惠安广通','慈溪哲光','义乌汐洋']

# 各代运营商作业池和单月覆盖目标（来源：英杰截图确认，2026-04-19，本月固定）
ORG_TARGETS = {
    # 5月目标：作业池 × 55%（2026-05-07英杰确认）
    '惠州巨浪':   {'pool': 329, 'month_tgt': round(329*0.55), 'rate_tgt': 0.55},
    '惠州柏万':   {'pool': 201, 'month_tgt': round(201*0.55), 'rate_tgt': 0.55},
    '泉州小花猫': {'pool': 226, 'month_tgt': round(226*0.55), 'rate_tgt': 0.55},
    '惠安广通':   {'pool': 141, 'month_tgt': round(141*0.55), 'rate_tgt': 0.55},
    '慈溪哲光':   {'pool': 251, 'month_tgt': round(251*0.55), 'rate_tgt': 0.55},
    '义乌汐洋':   {'pool': 191, 'month_tgt': round(191*0.55), 'rate_tgt': 0.55},
}

# 粤闽浙全量商户底表（12580行，含跟进销售，用于代运营商归因和销售名称匹配）
merchant_file = '/root/.openclaw/workspace/data/yuemin_zhe_merchant_pool.xlsx'

df_m = pd.read_excel(merchant_file)

def get_org(org_str):
    for k, v in ORG_MAP.items():
        if k in str(org_str):
            return v
    return None

df_m['代运营商'] = df_m['组织'].apply(get_org)
df_yue = df_m[df_m['代运营商'].notna()].copy()

# 复用已解析的 df_detail（第1段已读取）
import csv as _csv
df_yue_raw = df_detail[df_detail['城市组'] == '高线粤闽浙城市群'].copy()
df_yue_raw['门店ID'] = df_yue_raw['门店ID'].astype(str).str.strip()
# ⚠️ 同一门店可能有多条物料记录，必须按门店ID去重，取最优审核状态（合格>不合格>未知）
_status_rank = {'合格': 0, '不合格': 1, '未知': 2}
df_yue_raw['_srank'] = df_yue_raw['审核状态'].map(_status_rank).fillna(9)
df_yue_detail = df_yue_raw.sort_values('_srank').drop_duplicates('门店ID', keep='first').drop(columns='_srank')
df_yue_detail['门店ID'] = df_yue_detail['门店ID'].astype(str).str.strip()
df_m['shopId'] = df_m['shopId'].astype(str).str.strip()

# 合并：物料明细 + 商户代运营商
df_merged = df_yue_detail.merge(df_m[['shopId','代运营商','跟进销售']], left_on='门店ID', right_on='shopId', how='left')

# 汇总各代运营商
rows_data = []
for org in ORG_ORDER:
    sub = df_merged[df_merged['代运营商'] == org]
    # 作业池和目标从截图确认的固定值读取
    pool2     = ORG_TARGETS[org]['pool']
    month_tgt2= ORG_TARGETS[org]['month_tgt']
    rate_tgt2 = ORG_TARGETS[org]['rate_tgt']
    laid2  = len(sub)
    ok2    = len(sub[sub['审核状态'] == '合格'])
    bad2   = len(sub[sub['审核状态'] == '不合格'])
    done_pct2 = ok2 / pool2 if pool2 else 0
    rate_act2 = ok2 / pool2 if pool2 else 0
    ratio2 = rate_act2 / rate_tgt2 if rate_tgt2 else 0
    gap2 = ok2 - month_tgt2
    rows_data.append({
        '代运营商': org, '作业池': pool2, '铺设门店数': laid2,
        '✅合格门店数': ok2, '❌不合格门店数': bad2,
        '单月目标(数)': month_tgt2,
        '单月缺口': gap2,
        '单月完成进度': f"{done_pct2*100:.1f}%",
        '单月覆盖率目标': f"{rate_tgt2*100:.1f}%",
        '单月覆盖率进度': f"{rate_act2*100:.1f}%",
        '单月完成率': f"{ratio2*100:.1f}%",
        '_ratio': ratio2, '_ok': ok2, '_pool': pool2, '_gap': gap2,
    })

# 合计行
tot_pool2  = sum(r['作业池'] for r in rows_data)
tot_laid2  = sum(r['铺设门店数'] for r in rows_data)
tot_ok2    = sum(r['✅合格门店数'] for r in rows_data)
tot_bad2   = sum(r['❌不合格门店数'] for r in rows_data)
tot_mtgt2  = sum(r['单月目标(数)'] for r in rows_data)
tot_gap2   = sum(r['单月缺口'] for r in rows_data)
tot_done2  = tot_ok2 / tot_pool2 if tot_pool2 else 0
tot_rate_tgt2 = tot_mtgt2 / tot_pool2 if tot_pool2 else 0
tot_rate_act2 = tot_ok2 / tot_pool2 if tot_pool2 else 0
tot_ratio2 = tot_rate_act2 / tot_rate_tgt2 if tot_rate_tgt2 else 0

# 写 Sheet2
ws2 = wb.create_sheet('粤闽浙代运营商下钻')

# 大标题
ws2.merge_cells('A1:K1')
ws2['A1'] = '粤闽浙城市群 · 代运营商物料铺设下钻'
ws2['A1'].font = Font(name='微软雅黑', size=13, bold=True, color='FFFFFF')
ws2['A1'].fill = PatternFill('solid', fgColor='047857')
ws2['A1'].alignment = Alignment(horizontal='center', vertical='center')
ws2.row_dimensions[1].height = 28

# 表头
h2 = ['代运营商','作业池','铺设门店数','✅合格门店数','❌不合格门店数',
      '单月目标(数)','单月缺口','单月完成进度','单月覆盖率目标','单月覆盖率进度','单月完成率']
for ci, h in enumerate(h2, 1):
    cell = ws2.cell(row=2, column=ci, value=h)
    cell.font = bold_font()
    cell.fill = fill(C_HEADER)
    cell.alignment = center()
    cell.border = border
ws2.row_dimensions[2].height = 36

# 数据行
for i, r in enumerate(rows_data):
    rrow = i + 3
    bg2 = C_WHITE if i % 2 == 0 else C_ALT
    vals2 = [r['代运营商'], r['作业池'], r['铺设门店数'], r['✅合格门店数'], r['❌不合格门店数'],
             r['单月目标(数)'], r['单月缺口'], r['单月完成进度'], r['单月覆盖率目标'], r['单月覆盖率进度'], r['单月完成率']]
    for ci, v in enumerate(vals2, 1):
        cell = ws2.cell(row=rrow, column=ci, value=v)
        cell.fill = fill(bg2)
        cell.border = border
        cell.font = norm_font()
        cell.alignment = center() if ci in (1,8,9,10,11) else rgt()
    # 单月缺口色阶（第7列）
    gc2 = ws2.cell(row=rrow, column=7)
    gap_v = r['_gap']
    if gap_v >= 0:
        gc2.fill = fill('C6EFCE'); gc2.font = Font(color='276221', size=10)
    elif gap_v >= -15:
        gc2.fill = fill('FFEB9C'); gc2.font = Font(color='9C6500', size=10)
    else:
        gc2.fill = fill('FFC7CE'); gc2.font = Font(color='9C0006', size=10)
    gc2.alignment = center()
    # 单月完成率深色色阶（第11列）
    mc2 = ws2.cell(row=rrow, column=11)
    ratio2 = r['_ratio']
    if ratio2 >= 1.0:
        mc2.fill = fill('00B050'); mc2.font = Font(color='FFFFFF', size=10, bold=True)
    elif ratio2 >= 0.85:
        mc2.fill = fill('FF8C00'); mc2.font = Font(color='FFFFFF', size=10, bold=True)
    else:
        mc2.fill = fill('FF6B6B'); mc2.font = Font(color='FFFFFF', size=10, bold=True)
    mc2.alignment = center()
    mc2.border = border
    ws2.row_dimensions[rrow].height = 22

# 合计行
rrow = len(rows_data) + 3
vals_tot = ['粤闽浙合计', tot_pool2, tot_laid2, tot_ok2, tot_bad2,
            tot_mtgt2, tot_gap2, f"{tot_done2*100:.1f}%", f"{tot_rate_tgt2*100:.1f}%",
            f"{tot_rate_act2*100:.1f}%", f"{tot_ratio2*100:.1f}%"]
for ci, v in enumerate(vals_tot, 1):
    cell = ws2.cell(row=rrow, column=ci, value=v)
    cell.font = bold_font()
    cell.fill = fill(C_TOTAL)
    cell.border = border
    cell.alignment = center() if ci in (1,8,9,10,11) else rgt()
ws2.row_dimensions[rrow].height = 24

# 列宽（11列）
w2 = [14, 10, 12, 14, 14, 12, 10, 14, 14, 14, 14]
for i, w in enumerate(w2, 1):
    ws2.column_dimensions[chr(64+i)].width = w

# ── Sheet3：粤闽浙作业池门店明细 ──────────────────────────────────────
ws3 = wb.create_sheet('粤闽浙作业池')
# 加代运营商列（通过门店ID匹配）
df_pool = df_yue_detail.merge(df_m[['shopId','代运营商','跟进销售']], left_on='门店ID', right_on='shopId', how='left')
df_pool['代运营商'] = df_pool['代运营商'].fillna('未归因')
# 销售名称：优先用商户底表的跟进销售，CSV里的销售名称全为空
df_pool['销售名称'] = df_pool['跟进销售'].fillna(df_pool['销售名称']).fillna('')
# 按代运营商+审核状态排序
status_order = {'合格': 0, '不合格': 1, '未知': 2}
df_pool['_status_sort'] = df_pool['审核状态'].map(status_order).fillna(9)
df_pool = df_pool.sort_values(['代运营商', '_status_sort', '门店名称']).drop(columns=['_status_sort','shopId','跟进销售'], errors='ignore')

sheet3_cols = ['代运营商', '门店名称', '门店ID', '物料名称', '销售名称', '审核状态', '不合格原因', 'AI审核结果', '近3天扫码UV', '是否码动销']
# 表头
ws3.row_dimensions[1].height = 28
title3 = ws3.cell(row=1, column=1, value=f'粤闽浙作业池门店明细（共{len(df_pool)}家）')
title3.font = Font(bold=True, color='FFFFFF', size=11)
title3.fill = fill(C_HEADER)
title3.alignment = center()
ws3.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(sheet3_cols))

for ci, h in enumerate(sheet3_cols, 1):
    cell = ws3.cell(row=2, column=ci, value=h)
    cell.font = bold_font('FFFFFF', 10)
    cell.fill = fill(C_HEADER)
    cell.alignment = center()
    cell.border = border
ws3.row_dimensions[2].height = 28

# 状态颜色映射
STATUS_COLOR = {'合格': 'C6EFCE', '不合格': 'FFC7CE', '未知': 'FFEB9C'}
STATUS_FC    = {'合格': '276221', '不合格': '9C0006', '未知': '9C6500'}

for i, (_, row) in enumerate(df_pool.iterrows()):
    rr = i + 3
    bg = C_WHITE if i % 2 == 0 else C_ALT
    status = str(row.get('审核状态', ''))
    for ci, col in enumerate(sheet3_cols, 1):
        val = row.get(col, '')
        if pd.isna(val): val = ''
        cell = ws3.cell(row=rr, column=ci, value=val)
        cell.fill = fill(bg)
        cell.border = border
        cell.font = norm_font()
        cell.alignment = center() if ci in (1, 6) else Alignment(vertical='center', wrap_text=False)
    # 审核状态列上色
    sc = ws3.cell(row=rr, column=6)
    if status in STATUS_COLOR:
        sc.fill = fill(STATUS_COLOR[status])
        sc.font = Font(color=STATUS_FC[status], size=10, bold=(status == '不合格'))
    ws3.row_dimensions[rr].height = 18

ws3_widths = [14, 24, 14, 16, 12, 10, 36, 10, 12, 10]
for i, w in enumerate(ws3_widths, 1):
    ws3.column_dimensions[chr(64+i)].width = w
ws3.freeze_panes = 'A3'

# ── Sheet4：粤闽浙不合格门店明细 ──────────────────────────────────────
ws4 = wb.create_sheet('粤闽浙不合格门店')
df_bad = df_pool[df_pool['审核状态'] == '不合格'].copy()

ws4.row_dimensions[1].height = 28
title4 = ws4.cell(row=1, column=1, value=f'粤闽浙不合格门店明细（共{len(df_bad)}家）')
title4.font = Font(bold=True, color='FFFFFF', size=11)
title4.fill = fill('9C0006')
title4.alignment = center()
ws4.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(sheet3_cols))

for ci, h in enumerate(sheet3_cols, 1):
    cell = ws4.cell(row=2, column=ci, value=h)
    cell.font = bold_font('FFFFFF', 10)
    cell.fill = fill('C00000')
    cell.alignment = center()
    cell.border = border
ws4.row_dimensions[2].height = 28

for i, (_, row) in enumerate(df_bad.iterrows()):
    rr = i + 3
    bg = 'FFF0F0' if i % 2 == 0 else 'FFE0E0'
    for ci, col in enumerate(sheet3_cols, 1):
        val = row.get(col, '')
        if pd.isna(val): val = ''
        cell = ws4.cell(row=rr, column=ci, value=val)
        cell.fill = fill(bg)
        cell.border = border
        cell.font = norm_font()
        cell.alignment = center() if ci in (1, 6) else Alignment(vertical='center')
    ws4.row_dimensions[rr].height = 22

ws4_widths = [14, 24, 14, 16, 12, 10, 42, 10, 12, 10]
for i, w in enumerate(ws4_widths, 1):
    ws4.column_dimensions[chr(64+i)].width = w
ws4.freeze_panes = 'A3'

# ── 保存 ─────────────────────────────────────────────────────────────
out = f'/tmp/高线物料铺设看板_{datetime.now().strftime("%Y%m%d")}.xlsx'
wb.save(out)
print('Done:', out)



