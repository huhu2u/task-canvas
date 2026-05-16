#!/usr/bin/env python3
"""旺铺通分析生成脚本（定稿版，2026-05-16英杰确认）

用法: python3 gen_wangputong_analysis.py <旺铺通xlsx文件> <输出文件>

输入文件要求：含 `旺铺通消耗额`、`责任销售业绩归属组织名称`、`验证商户ID`、`责任销售姓名`、`城市名称（后台）`、`门店名称` 字段

输出：4个Sheet的Excel
- Sheet1「代运营商汇总」：好店数|开通数|日变化|好店开通|好店未开通|好店开通率|消耗额|好店消耗额|好店金额占比|人均消耗
- Sheet2「销售维度」：按代运营商分组（绿色标题行），组内按好店开通率降序，好店开通率列色阶
- Sheet3「好店未开通明细」：好店底表中消耗=0的门店
- Sheet4「全量未开通明细」：全量消耗=0的门店

色阶规则：好店开通率 绿(高)→黄(中)→红(低)
"""

import sys, os, json
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import ColorScaleRule

INPUT_FILE = sys.argv[1]
OUTPUT_FILE = sys.argv[2]

# 代运营商映射
NAME_MAP = {
    '惠州市巨浪-惠州乐生活组': '惠州巨浪',
    '惠州市柏万-惠阳乐生活组': '惠州柏万',
    '泉州市小花猫-泉州乐生活组': '泉州小花猫',
    '惠安广通-晋江乐生活组': '惠安广通',
    '慈溪哲光-金华义乌乐生活组': '慈溪哲光',
    '义乌市汐洋-金华义乌乐生活组': '义乌汐洋',
}
OPS = ['惠州巨浪','惠州柏万','泉州小花猫','惠安广通','慈溪哲光','义乌汐洋']

def get_op(x):
    for k, v in NAME_MAP.items():
        if k in str(x): return v
    return '未知'

def sf(v, d=0):
    try: return float(v) if pd.notna(v) else d
    except: return d

# 读取数据
df = pd.read_excel(INPUT_FILE)
df['代运营商'] = df['责任销售业绩归属组织名称'].apply(get_op)

# 好店底表匹配
hd = pd.read_excel('/root/.openclaw/workspace/data/haodian_pool.xlsx', usecols=['shopId'])
hd_set = set(str(x) for x in hd['shopId'].dropna())
df['is_good'] = df['验证商户ID'].apply(lambda x: str(x) in hd_set)
df['is_open'] = df['旺铺通消耗额'].fillna(0).astype(float) > 0

# 昨日存档
prev = {}
prev_path = '/root/.openclaw/workspace/data/wangputong_archive/2026-05-14.json'
if os.path.exists(prev_path):
    with open(prev_path, 'r', encoding='utf-8') as f:
        prev = json.load(f)

# 从文件名提取日期
date_str = '2026-05-15'
for part in INPUT_FILE.split('/')[-1].split('.')[0].split('_'):
    if len(part) == 10 and part[4] == '-' and part[7] == '-':
        date_str = part
        break

# Sheet1: 代运营商汇总
op_rows = []
cur_archive = {}
for op in OPS:
    sub = df[df['代运营商']==op].copy()
    good = sub[sub['is_good']].copy()
    open_cnt = int(sub['is_open'].sum())
    good_open = int(good['is_open'].sum())
    good_not = len(good) - good_open
    good_rate = good_open / len(good) if len(good) else 0
    amt = float(sub['旺铺通消耗额'].fillna(0).sum())
    good_amt = float(good.loc[good['is_open'], '旺铺通消耗额'].fillna(0).sum())
    sales_n = sub['责任销售姓名'].nunique()
    per_capita = amt / sales_n if sales_n else 0
    day_change = open_cnt - int(prev.get(op, 0))
    cur_archive[op] = open_cnt
    op_rows.append([op, len(good), open_cnt, day_change, good_open, good_not, good_rate, amt, good_amt, (good_amt/amt if amt else 0), per_capita])

# 存档今日
os.makedirs('/root/.openclaw/workspace/data/wangputong_archive', exist_ok=True)
date_key = date_str.replace('-','')  # e.g. 2026-05-15 -> 20260515
with open(f'/root/.openclaw/workspace/data/wangputong_archive/{date_key}.json', 'w', encoding='utf-8') as f:
    json.dump(cur_archive, f, ensure_ascii=False, indent=2)

# Sheet2: 销售维度
sales_rows = []
for op in OPS:
    sub = df[df['代运营商']==op].copy()
    for name, grp in sub.groupby('责任销售姓名'):
        good = grp[grp['is_good']].copy()
        open_cnt = int(grp['is_open'].sum())
        good_open = int(good['is_open'].sum())
        good_not = len(good) - good_open
        good_rate = good_open / len(good) if len(good) else 0
        amt = float(grp['旺铺通消耗额'].fillna(0).sum())
        good_amt = float(good.loc[good['is_open'], '旺铺通消耗额'].fillna(0).sum())
        sales_rows.append({
            '代运营商': op, '销售姓名': name,
            '好店数': len(good), '开通数': open_cnt,
            '好店开通': good_open, '好店未开通': good_not,
            '好店开通率': good_rate,
            '消耗额': amt, '好店消耗额': good_amt,
            '好店金额占比': good_amt/amt if amt else 0,
            '人均消耗': amt,
        })

# Sheet3/4
good_not_open = df[(df['is_good']) & (~df['is_open'])]
all_not_open = df[~df['is_open']]

# 写Excel
wb = Workbook(); wb.remove(wb.active)
header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
header_font = Font(name='微软雅黑', bold=True, color='FFFFFF', size=11)
thin_border = Border(left=Side(style='thin', color='B0B0B0'), right=Side(style='thin', color='B0B0B0'), top=Side(style='thin', color='B0B0B0'), bottom=Side(style='thin', color='B0B0B0'))
alt_fill = PatternFill(start_color='F0F9FF', end_color='F0F9FF', fill_type='solid')

def style_header(ws, row, cols):
    for i, c in enumerate(cols, 1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = thin_border

def style_data_row(ws, r_idx, row, pct_cols=None, amt_cols=None):
    pct_cols = pct_cols or []
    amt_cols = amt_cols or []
    for c_idx, v in enumerate(row, start=1):
        cell = ws.cell(row=r_idx, column=c_idx, value=v)
        cell.border = thin_border
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.font = Font(name='微软雅黑', size=10)
        if c_idx in pct_cols: cell.number_format = '0.0%'
        if c_idx in amt_cols: cell.number_format = '#,##0.00'
    if r_idx % 2 == 0:
        for c_idx in range(1, len(row) + 1):
            ws.cell(row=r_idx, column=c_idx).fill = alt_fill

# Sheet1
ws1 = wb.create_sheet('代运营商汇总')
ws1.merge_cells('A1:K1')
title = f'粤闽浙城市群旺铺通分析（{date_str}）'
ws1['A1'] = title
ws1['A1'].font = Font(name='微软雅黑', bold=True, size=14, color='1F4E79')
ws1['A1'].alignment = Alignment(horizontal='center')
cols1 = ['代运营商','好店数','开通数','日变化','好店开通','好店未开通','好店开通率','消耗额','好店消耗额','好店金额占比','人均消耗']
style_header(ws1, 2, cols1)
for idx, row in enumerate(op_rows, start=3):
    style_data_row(ws1, idx, row, pct_cols=[7,10], amt_cols=[8,9,11])
# 色阶: 好店开通率(G列)
rule = ColorScaleRule(start_type='percentile', start_value=0, start_color='FFC7CE',
                      mid_type='percentile', mid_value=50, mid_color='FFEB9C',
                      end_type='percentile', end_value=100, end_color='C6EFCE')
ws1.conditional_formatting.add(f'G3:G{len(op_rows)+2}', rule)
for i, w in enumerate([12,10,10,8,10,12,12,12,12,12,12], start=1):
    ws1.column_dimensions[get_column_letter(i)].width = w

# Sheet2
ws2 = wb.create_sheet('销售维度')
ws2.merge_cells('A1:K1')
ws2['A1'] = f'粤闽浙城市群旺铺通销售维度（{date_str}）'
ws2['A1'].font = Font(name='微软雅黑', bold=True, size=14, color='1F4E79')
ws2['A1'].alignment = Alignment(horizontal='center')
cols2 = ['代运营商','销售姓名','好店数','开通数','好店开通','好店未开通','好店开通率','消耗额','好店消耗额','好店金额占比','人均消耗']
style_header(ws2, 2, cols2)
row = 3
color_scale_groups = []
for op in OPS:
    op_sales = [s for s in sales_rows if s['代运营商'] == op]
    op_sales.sort(key=lambda x: (-x['好店开通率'], -x['消耗额']))
    if not op_sales:
        continue
    # 标题行
    c1 = ws2.cell(row=row, column=1, value=f'▶ {op}')
    c1.font = Font(name='微软雅黑', bold=True, color='FFFFFF', size=11)
    c1.fill = PatternFill(start_color='059669', end_color='059669', fill_type='solid')
    c1.alignment = Alignment(horizontal='center', vertical='center')
    c1.border = thin_border
    for c in range(2, 12):
        cc = ws2.cell(row=row, column=c)
        cc.fill = PatternFill(start_color='059669', end_color='059669', fill_type='solid')
        cc.border = thin_border
    row += 1
    group_start = row
    for s in op_sales:
        vals = [s['代运营商'], s['销售姓名'], s['好店数'], s['开通数'], s['好店开通'], s['好店未开通'], s['好店开通率'], s['消耗额'], s['好店消耗额'], s['好店金额占比'], s['人均消耗']]
        style_data_row(ws2, row, vals, pct_cols=[7,10], amt_cols=[8,9,11])
        row += 1
    group_end = row - 1
    if group_start <= group_end:
        color_scale_groups.append((group_start, group_end))
# 色阶
for gs, ge in color_scale_groups:
    rule = ColorScaleRule(start_type='percentile', start_value=0, start_color='FFC7CE',
                          mid_type='percentile', mid_value=50, mid_color='FFEB9C',
                          end_type='percentile', end_value=100, end_color='C6EFCE')
    ws2.conditional_formatting.add(f'G{gs}:G{ge}', rule)
for i, w in enumerate([12,10,8,8,10,12,12,12,12,12,12], start=1):
    ws2.column_dimensions[get_column_letter(i)].width = w
ws2.freeze_panes = 'C3'

# Sheet3
ws3 = wb.create_sheet('好店未开通明细')
ws3.merge_cells('A1:F1')
ws3['A1'] = f'好店未开通明细（{len(good_not_open)}家）'
ws3['A1'].font = Font(name='微软雅黑', bold=True, size=14, color='1F4E79')
ws3['A1'].alignment = Alignment(horizontal='center')
cols3 = ['代运营商','销售姓名','验证商户ID','门店名称','城市','旺铺通消耗额']
style_header(ws3, 2, cols3)
for idx, (_, r) in enumerate(good_not_open.iterrows(), start=3):
    vals = [get_op(r['责任销售业绩归属组织名称']), r['责任销售姓名'], r['验证商户ID'], r['门店名称'], r['城市名称（后台）'], sf(r['旺铺通消耗额'])]
    style_data_row(ws3, idx, vals, amt_cols=[6])
for i, w in enumerate([12,10,12,28,10,12], start=1):
    ws3.column_dimensions[get_column_letter(i)].width = w

# Sheet4
ws4 = wb.create_sheet('全量未开通明细')
ws4.merge_cells('A1:F1')
ws4['A1'] = f'全量未开通明细（{len(all_not_open)}家）'
ws4['A1'].font = Font(name='微软雅黑', bold=True, size=14, color='1F4E79')
ws4['A1'].alignment = Alignment(horizontal='center')
style_header(ws4, 2, cols3)
for idx, (_, r) in enumerate(all_not_open.iterrows(), start=3):
    vals = [get_op(r['责任销售业绩归属组织名称']), r['责任销售姓名'], r['验证商户ID'], r['门店名称'], r['城市名称（后台）'], sf(r['旺铺通消耗额'])]
    style_data_row(ws4, idx, vals, amt_cols=[6])
for i, w in enumerate([12,10,12,28,10,12], start=1):
    ws4.column_dimensions[get_column_letter(i)].width = w

wb.save(OUTPUT_FILE)
print(f'✅ {OUTPUT_FILE}')
print(f'Sheet1 ops: {len(op_rows)}')
print(f'Sheet2 sales: {sum(len([s for s in sales_rows if s["代运营商"]==op]) for op in OPS)}')
print(f'Sheet3 good-not-open: {len(good_not_open)}')
print(f'Sheet4 all-not-open: {len(all_not_open)}')
print(f'Archive: /root/.openclaw/workspace/data/wangputong_archive/{date_key}.json')
