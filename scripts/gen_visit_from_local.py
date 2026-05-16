#!/usr/bin/env python3
"""从本地月拜访明细xlsx生成3Sheet分析表"""
import sys, os, re
import pandas as pd
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
from collections import defaultdict

INPUT_FILE = sys.argv[1]
OUTPUT_FILE = sys.argv[2]

# 好店池
HAODIAN_PATH = '/root/.openclaw/workspace/data/haodian_pool.xlsx'
hd_df = pd.read_excel(HAODIAN_PATH, usecols=['shopId'])
HAODIAN_SET = set(str(x) for x in hd_df['shopId'].dropna())
print(f"好店池: {len(HAODIAN_SET)}家")

df = pd.read_excel(INPUT_FILE)
print(f"拜访明细: {len(df)}行, {df['拜访日期'].min()}~{df['拜访日期'].max()}")

# 字段归一化（兼容新旧格式）
def norm(df):
    col_map = {}
    for c in df.columns:
        if '销售' in c and ('ID' in c or '工号' in c or 'id' in c):
            col_map[c] = 'emp_id'
        elif '销售姓名' in c or ('销售' in c and '名' in c and 'ID' not in c and 'id' not in c):
            col_map[c] = 'emp_name'
        elif '归属组织' in c or 'L9组织' in c:
            col_map[c] = 'org'
    return col_map

# 用已知字段名
df['拜访日期'] = df['拜访日期'].astype(str).str[:10]
df['emp_id'] = df['销售ID'].astype(str)
df['emp_name'] = df['销售姓名'].astype(str)
def simplify_org(org_name):
    """简化代运营商名称：取'-'前面部分，去掉'市'字"""
    name = str(org_name).split('-')[0].strip()
    # 只去掉"市"字（如惠州市→惠州，义乌市→义乌，泉州市→泉州）
    import re
    name = re.sub(r'^(\S{2,3})市(\S)', r'\1\2', name)
    return name

df['org'] = df['销售业绩归属组织'].apply(simplify_org)
df['is_valid'] = df['是否有效拜访'].apply(lambda x: 1 if x==1 or x=='1' or x=='是' else 0)
df['is_signin'] = df['是否签到'].apply(lambda x: 1 if x==1 or x=='1' or x=='是' else 0)
df['is_ivr'] = df['是否IVR电话拜访'].apply(lambda x: 1 if x==1 or x=='1' or x=='是' else 0)
df['shop_id'] = df['门店ID'].astype(str)
df['shop_name'] = df['门店名'].astype(str)
df['is_haodian'] = df['shop_id'].isin(HAODIAN_SET)
df['is_500m'] = df['是否500米内'].apply(lambda x: 1 if x==1 or x=='1' or x=='是' else (0 if x==0 or x=='0' or x=='否' else -1))
df['distance'] = df['签到距离'].fillna('-').astype(str)
df['sign_in_time'] = df['签到时间'].fillna('-').astype(str)
df['start_time'] = df['拜访开始时间'].fillna('-').astype(str)
df['end_time'] = df['拜访结束时间'].fillna('-').astype(str)

# 日期范围
all_dates = sorted(df['拜访日期'].unique())
target_date = max(all_dates)
print(f"昨日: {target_date}")

month_start = target_date[:8] + '01'
dates = [d for d in all_dates if d >= month_start and d <= target_date]

# 人员列表
persons_set = {}
for _, row in df.iterrows():
    key = (row['org'], row['emp_id'], row['emp_name'])
    persons_set[key] = True
sorted_persons = sorted(persons_set.keys(), key=lambda x: (x[0], x[1]))

# 统计有效拜访（普通，用于月度汇总总数和有效天数）
valid_by = defaultdict(int)
for _, row in df[df['is_valid']==1].iterrows():
    valid_by[(row['org'], row['emp_id'], row['emp_name'], row['拜访日期'])] += 1

# 统计好店有效拜访（每人每天，用于Sheet1日期列 + Sheet2达标天数）
hd_valid_by = defaultdict(int)
for _, row in df[(df['is_valid']==1) & df['is_haodian']].iterrows():
    hd_valid_by[(row['org'], row['emp_id'], row['emp_name'], row['拜访日期'])] += 1

# 昨日好店拜访数（末尾汇总列）
hd_by = defaultdict(int)
for (org, emp_id, emp_name, date), cnt in hd_valid_by.items():
    if date == target_date:
        hd_by[(org, emp_id, emp_name)] += cnt

# 颜色
RED_FILL = PatternFill("solid", fgColor="FFCCCC")
GREEN_FILL = PatternFill("solid", fgColor="C6EFCE")
LIGHT_GREEN_FILL = PatternFill("solid", fgColor="E2EFDA")
YELLOW_FILL = PatternFill("solid", fgColor="FFFF99")
HEADER_FILL = PatternFill("solid", fgColor="4472C4")
HEADER_FONT = Font(color="FFFFFF", bold=True)
DARK_GREEN_FILL = PatternFill("solid", fgColor="1F6E3E")
DARK_GREEN_FONT = Font(color="FFFFFF", bold=True)
CENTER = Alignment(horizontal="center")

wb = Workbook()

# ===== Sheet1 =====
ws1 = wb.active
ws1.title = "每日有效拜访数"
dates_rev = list(reversed(dates))
# 每天两列：XX-XX 有效 | XX-XX 好店
date_headers = []
for d in dates_rev:
    date_headers.append(f"{d[5:]} 有效")
    date_headers.append(f"{d[5:]} 好店")
headers1 = ["代运营商","销售工号","销售姓名"] + date_headers + ["昨日好店拜访数"]
for col, h in enumerate(headers1, 1):
    c = ws1.cell(1, col, h)
    c.fill = HEADER_FILL; c.font = HEADER_FONT; c.alignment = CENTER

for r_idx, (org, emp_id, emp_name) in enumerate(sorted_persons, 2):
    ws1.cell(r_idx, 1, org)
    ws1.cell(r_idx, 2, emp_id)
    ws1.cell(r_idx, 3, emp_name)
    col_idx = 4
    for date in dates_rev:
        # 有效拜访数
        valid_cnt = valid_by.get((org, emp_id, emp_name, date), 0)
        c1 = ws1.cell(r_idx, col_idx, valid_cnt)
        c1.alignment = CENTER
        c1.fill = RED_FILL if valid_cnt == 0 else PatternFill()
        col_idx += 1
        # 好店有效拜访数
        hd_cnt_day = hd_valid_by.get((org, emp_id, emp_name, date), 0)
        c2 = ws1.cell(r_idx, col_idx, hd_cnt_day)
        c2.alignment = CENTER
        c2.fill = LIGHT_GREEN_FILL if hd_cnt_day >= 3 else (RED_FILL if hd_cnt_day == 0 else PatternFill())
        col_idx += 1
    # 末尾：昨日好店拜访数汇总
    hd_cnt = hd_by.get((org, emp_id, emp_name), 0)
    hd_cell = ws1.cell(r_idx, col_idx, hd_cnt)
    hd_cell.alignment = CENTER
    hd_cell.fill = LIGHT_GREEN_FILL if hd_cnt >= 3 else RED_FILL
ws1.freeze_panes = "D3"

# ===== Sheet2 =====
ws2 = wb.create_sheet("月度汇总")
h2 = ["代运营商","销售工号","销售姓名","月有效拜访总数","有效拜访天数","好店有效拜访≥3的天数"]
for col, h in enumerate(h2, 1):
    c = ws2.cell(1, col, h); c.fill = HEADER_FILL; c.font = HEADER_FONT

for r_idx, (org, emp_id, emp_name) in enumerate(sorted_persons, 2):
    total = sum(valid_by.get((org,emp_id,emp_name,d),0) for d in dates)
    days = sum(1 for d in dates if valid_by.get((org,emp_id,emp_name,d),0)>0)
    # 好店有效拜访≥3的天数
    ge3 = sum(1 for d in dates if hd_valid_by.get((org,emp_id,emp_name,d),0)>=3)
    ws2.cell(r_idx,1,org); ws2.cell(r_idx,2,emp_id); ws2.cell(r_idx,3,emp_name)
    ws2.cell(r_idx,4,total); ws2.cell(r_idx,5,days)
    c = ws2.cell(r_idx,6,ge3)
    c.fill = GREEN_FILL if ge3>=20 else (YELLOW_FILL if ge3>=15 else RED_FILL)

# ===== Sheet3 =====
ws3 = wb.create_sheet("昨日签到检核")
h3 = ["代运营商","销售工号","销售姓名","拜访门店名","是否好店","是否IVR电话拜访",
      "是否有效","是否签到","500米内签到","签到距离","签到时间","拜访开始时间","拜访结束时间"]
for col, h in enumerate(h3, 1):
    c = ws3.cell(1, col, h); c.fill = HEADER_FILL; c.font = HEADER_FONT

day_df = df[df['拜访日期']==target_date].sort_values(['org','emp_name'])
for r_idx, (_, row) in enumerate(day_df.iterrows(), 2):
    is_signin = row['is_signin'] == 1
    is_ivr = row['is_ivr'] == 1
    is_hd = bool(row['is_haodian'])
    vals = [
        row['org'], row['emp_id'], row['emp_name'], row['shop_name'],
        "⭐好店" if is_hd else "-",
        "是" if is_ivr else "否",
        "是" if row['is_valid']==1 else "否",
        "是" if is_signin else "否",
        "是" if row['is_500m']==1 else ("否" if row['is_500m']==0 else "-"),
        row['distance'], row['sign_in_time'], row['start_time'], row['end_time'],
    ]
    for col, v in enumerate(vals, 1):
        ws3.cell(r_idx, col, v)
    if not is_signin:
        for col in range(1, 14):
            ws3.cell(r_idx, col).fill = RED_FILL
    else:
        if is_hd:
            ws3.cell(r_idx, 5).fill = DARK_GREEN_FILL
            ws3.cell(r_idx, 5).font = DARK_GREEN_FONT
        if is_ivr:
            ws3.cell(r_idx, 6).fill = YELLOW_FILL

# 列宽
for ws in [ws1, ws2, ws3]:
    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=0)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(max_len+2,8),35)

wb.save(OUTPUT_FILE)
print(f"✅ {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE):,} bytes)")
print(f"Sheet1:{ws1.max_row-1}行 Sheet2:{ws2.max_row-1}行 Sheet3:{ws3.max_row-1}行")
