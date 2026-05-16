#!/usr/bin/env python3
"""
每天9点自动抓取前一天拜访明细数据，生成3Sheet Excel，发给英杰
v2: 新增Sheet1昨日好店拜访数列、Sheet3是否好店列，去掉月合计/日均列
"""
import requests, json, time, math, os, sys
import pandas as pd
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
from collections import defaultdict

# 加载好店池
HAODIAN_PATH = '/root/.openclaw/workspace/data/haodian_pool.xlsx'
try:
    hd_df = pd.read_excel(HAODIAN_PATH, usecols=['shopId'])
    HAODIAN_SET = set(str(x) for x in hd_df['shopId'].dropna())
except Exception as e:
    print(f"WARNING: 好店池加载失败: {e}", file=sys.stderr)
    HAODIAN_SET = set()

# 配置
TARGET_USER = "3264994429"
OUT_DIR = "/tmp/files"
os.makedirs(OUT_DIR, exist_ok=True)

# 分析前一天的数据
today = datetime.now()
target_date = (today - timedelta(days=1)).strftime('%Y-%m-%d')
date_str = (today - timedelta(days=1)).strftime('%Y%m%d')
OUT_FILE = f"{OUT_DIR}/粤闽浙拜访分析_{date_str}.xlsx"

COOKIE = os.environ.get('APOLLO_COOKIE', '')
if not COOKIE:
    # 读取存储的cookie
    cookie_file = '/root/.openclaw/workspace/scripts/.apollo_cookie'
    if os.path.exists(cookie_file):
        with open(cookie_file) as f:
            COOKIE = f.read().strip()

if not COOKIE:
    print("ERROR: No APOLLO_COOKIE set", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "Content-Type": "application/json",
    "Cookie": COOKIE,
    "Referer": "https://a.dper.com/gw/smartreport/",
    "User-Agent": "Mozilla/5.0"
}

COLUMNS = ["attribute_org_id","attribute_org_name","employee_id","employee_name",
           "visit_date","is_valid","is_signin","is_ivr_call","visit_form",
           "visit_form_name","distance","is_500m","sign_in_time","start_time",
           "end_time","shop_id","shop_name","org_name_l8"]

def fetch_page(page, page_size=200):
    body = [{"category":"query","type":"SmartQuery","params":{"dsl":{
        "date": target_date,
        "reportId": 478,
        "pageIndex": str(page),
        "pageSize": str(page_size),
        "tableId": 995,
        "params": [{"field":"attribute_org_id","method":"in","id":35231,"transformType":1,"value":20903327}],
        "columns": COLUMNS,
        "sorts": [{}]
    }}, "as":"result"}]
    r = requests.post("https://a.dper.com/gw/__cascade__/SmartQuery.query",
                      json=body, headers=HEADERS, timeout=120)
    r.raise_for_status()
    result = r.json()["data"]["result"]
    return result["data"], result["total"]

# 拉取全量数据
all_rows = []
page_size = 200
_, total = fetch_page(1, page_size)
total_pages = math.ceil(total / page_size)
print(f"[{target_date}] 总数: {total}, 共{total_pages}页")

for p in range(1, total_pages + 1):
    rows, _ = fetch_page(p, page_size)
    all_rows.extend(rows)
    if p % 5 == 0:
        print(f"  第{p}/{total_pages}页, 累计{len(all_rows)}条")
    time.sleep(0.1)

print(f"拉取完成，共{len(all_rows)}条")

# 获取本月日期范围
month_start = datetime.strptime(target_date, '%Y-%m-%d').replace(day=1)
target_dt = datetime.strptime(target_date, '%Y-%m-%d')
dates = []
d = month_start
while d <= target_dt:
    dates.append(d.strftime('%Y-%m-%d'))
    d = d + timedelta(days=1)

# 统计
valid_by_person_date = defaultdict(int)
hd_valid_by = defaultdict(int)  # 好店有效拜访
persons = {}

for row in all_rows:
    org = str(row.get("attribute_org_name",""))
    emp_id = str(row.get("employee_id",""))
    emp_name = str(row.get("employee_name",""))
    vdate = str(row.get("visit_date",""))[:10]
    is_valid = row.get("is_valid")
    shop_id = str(row.get("shop_id",""))
    key = (org, emp_id, emp_name)
    persons[key] = True
    if is_valid == 1:
        valid_by_person_date[(org, emp_id, emp_name, vdate)] += 1
        if shop_id in HAODIAN_SET:
            hd_valid_by[(org, emp_id, emp_name, vdate)] += 1

sorted_persons = sorted(persons.keys(), key=lambda x: (x[0], x[1]))

# 统计昨日好店拜访数（每人昨日有效拜访中好店门店数）
haodian_visit_by_person = defaultdict(int)
for row in all_rows:
    if str(row.get("visit_date",""))[:10] != target_date:
        continue
    if row.get("is_valid") != 1:
        continue
    org = str(row.get("attribute_org_name",""))
    emp_id = str(row.get("employee_id",""))
    emp_name = str(row.get("employee_name",""))
    shop_id = str(row.get("shop_id",""))
    if shop_id in HAODIAN_SET:
        haodian_visit_by_person[(org, emp_id, emp_name)] += 1

# Excel生成
wb = Workbook()
RED_FILL = PatternFill("solid", fgColor="FFCCCC")
GREEN_FILL = PatternFill("solid", fgColor="C6EFCE")
LIGHT_GREEN_FILL = PatternFill("solid", fgColor="E2EFDA")
YELLOW_FILL = PatternFill("solid", fgColor="FFFF99")
HEADER_FILL = PatternFill("solid", fgColor="4472C4")
HEADER_FONT = Font(color="FFFFFF", bold=True)
CENTER = Alignment(horizontal="center")

# Sheet1：日期列倒序（最新在左），末尾加「昨日好店拜访数」，无月合计/日均
ws1 = wb.active
ws1.title = "每日有效拜访数"
dates_rev = list(reversed(dates))  # 最新日期在左
headers1 = ["代运营商","销售工号","销售姓名"] + [d[5:] for d in dates_rev] + ["昨日好店拜访数"]
for col, h in enumerate(headers1, 1):
    cell = ws1.cell(1, col, h)
    cell.fill = HEADER_FILL; cell.font = HEADER_FONT
    cell.alignment = CENTER

for r_idx, (org, emp_id, emp_name) in enumerate(sorted_persons, 2):
    ws1.cell(r_idx, 1, org)
    ws1.cell(r_idx, 2, emp_id)
    ws1.cell(r_idx, 3, emp_name)
    for d_idx, date in enumerate(dates_rev, 4):
        # 每天显示好店有效拜访数
        cnt = hd_valid_by.get((org, emp_id, emp_name, date), 0)
        cell = ws1.cell(r_idx, d_idx, cnt)
        cell.alignment = CENTER
        cell.fill = RED_FILL if cnt == 0 else (LIGHT_GREEN_FILL if cnt >= 3 else PatternFill())
    # 末尾：昨日好店拜访数
    hd_cnt = haodian_visit_by_person.get((org, emp_id, emp_name), 0)
    hd_col = 4 + len(dates)
    hd_cell = ws1.cell(r_idx, hd_col, hd_cnt)
    hd_cell.alignment = CENTER
    hd_cell.fill = LIGHT_GREEN_FILL if hd_cnt >= 3 else RED_FILL
ws1.freeze_panes = "D3"

# Sheet2
ws2 = wb.create_sheet("月度汇总")
for col, h in enumerate(["代运营商","销售工号","销售姓名","月有效拜访总数","有效拜访天数","好店有效拜访≥3的天数"], 1):
    cell = ws2.cell(1, col, h)
    cell.fill = HEADER_FILL; cell.font = HEADER_FONT
for r_idx, (org, emp_id, emp_name) in enumerate(sorted_persons, 2):
    total_valid = sum(valid_by_person_date.get((org,emp_id,emp_name,d),0) for d in dates)
    valid_days = sum(1 for d in dates if valid_by_person_date.get((org,emp_id,emp_name,d),0)>0)
    # 好店有效拜访≥3的天数
    ge3_days = sum(1 for d in dates if hd_valid_by.get((org,emp_id,emp_name,d),0)>=3)
    ws2.cell(r_idx,1,org); ws2.cell(r_idx,2,emp_id); ws2.cell(r_idx,3,emp_name)
    ws2.cell(r_idx,4,total_valid); ws2.cell(r_idx,5,valid_days)
    c = ws2.cell(r_idx,6,ge3_days)
    c.fill = GREEN_FILL if ge3_days>=20 else (YELLOW_FILL if ge3_days>=15 else RED_FILL)

# Sheet3：昨日签到检核，含「是否好店」列
ws3 = wb.create_sheet("昨日签到检核")
DARK_GREEN_FILL = PatternFill("solid", fgColor="1F6E3E")
DARK_GREEN_FONT = Font(color="FFFFFF", bold=True)
IVR_FILL = PatternFill("solid", fgColor="FFFF99")  # IVR电话拜访黄色

h3 = ["代运营商","销售工号","销售姓名","拜访门店名","是否好店","是否IVR电话拜访","是否有效","是否签到","500米内签到","签到距离","签到时间","拜访开始时间","拜访结束时间"]
for col, h in enumerate(h3, 1):
    cell = ws3.cell(1, col, h)
    cell.fill = HEADER_FILL; cell.font = HEADER_FONT

day_rows = [r for r in all_rows if str(r.get("visit_date",""))[:10]==target_date]
day_rows.sort(key=lambda x: (str(x.get("attribute_org_name","")), str(x.get("employee_name",""))))
for r_idx, row in enumerate(day_rows, 2):
    shop_id = str(row.get("shop_id",""))
    is_haodian = shop_id in HAODIAN_SET
    is_ivr = str(row.get("visit_form","")) == "1"
    is_signin = row.get("is_signin") == 1
    vals = [
        str(row.get("attribute_org_name","")),
        str(row.get("employee_id","")),
        str(row.get("employee_name","")),
        str(row.get("shop_name","")),
        "⭐好店" if is_haodian else "-",
        "是" if is_ivr else "否",
        "是" if row.get("is_valid")==1 else "否",
        "是" if is_signin else "否",
        "是" if row.get("is_500m")==1 else ("否" if row.get("is_500m")==0 else "-"),
        str(row.get("distance","")) if row.get("distance") is not None else "-",
        str(row.get("sign_in_time","") or "-"),
        str(row.get("start_time","") or "-"),
        str(row.get("end_time","") or "-"),
    ]
    for col, v in enumerate(vals, 1):
        ws3.cell(r_idx, col, v)
    
    # 颜色逻辑：未签到=整行红，好店=深绿，IVR=黄
    if not is_signin:
        for col in range(1, 14):
            ws3.cell(r_idx, col).fill = RED_FILL
    else:
        if is_haodian:
            hd_cell = ws3.cell(r_idx, 5)
            hd_cell.fill = DARK_GREEN_FILL
            hd_cell.font = DARK_GREEN_FONT
        if is_ivr:
            ws3.cell(r_idx, 6).fill = IVR_FILL

# 列宽
for ws in [ws1, ws2, ws3]:
    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=0)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(max_len+2,8),30)

wb.save(OUT_FILE)
size = os.path.getsize(OUT_FILE)
print(f"✓ {OUT_FILE} ({size:,} bytes)")
print(f"Sheet1:{ws1.max_row-1}行 Sheet2:{ws2.max_row-1}行 Sheet3:{ws3.max_row-1}行")

# 发大象消息
import subprocess
msg = f"{target_date[:7][5:].replace('-','')}月拜访分析报告（{target_date[5:]}数据），共{len(all_rows)}条：\n· Sheet1 每日有效拜访数\n· Sheet2 月度汇总（达标天数绿/黄/红）\n· Sheet3 昨日签到检核（未签到标红）"
subprocess.run(['openclaw', 'message', 'send', '--channel', 'daxiang', '--target', TARGET_USER, '--media', OUT_FILE, '--message', msg], timeout=120)
print("✓ 消息已发送")

# ---- Sheet4: 代理商汇总 ----
HC_MAP = {
    '义乌市汐洋-金华义乌乐生活组': 6,
    '惠安广通-晋江乐生活组': 5,
    '惠州市巨浪-惠州乐生活组': 9,
    '惠州市柏万-惠阳乐生活组': 7,
    '慈溪哲光-金华义乌乐生活组': 6,
    '泉州市小花猫-泉州乐生活组': 7,
}

ORANGE_FILL = PatternFill("solid", fgColor="FFD966")
TOTAL_FILL = PatternFill("solid", fgColor="D9E1F2")
CENTER = Alignment(horizontal="center", vertical="center")

ws4 = wb.create_sheet("代理商汇总")
# 从Sheet3读数据
org_emp_visits4 = defaultdict(int)
org_emp_signin4 = defaultdict(list)
org_set4 = {}
for row in day_rows:
    org = str(row.get("attribute_org_name","")).strip()
    emp_id = str(row.get("employee_id","")).strip()
    if not org or not emp_id: continue
    org_set4[org] = True
    if row.get("is_valid") == 1:
        org_emp_visits4[(org, emp_id)] += 1
    org_emp_signin4[(org, emp_id)].append(row.get("is_signin"))

results4 = []
for org in sorted(org_set4.keys()):
    hc = HC_MAP.get(org, 0)
    emp_visits = {k[1]: v for k, v in org_emp_visits4.items() if k[0] == org}
    gt4 = sum(1 for v in emp_visits.values() if v > 4)
    unsigned = {eid for (o, eid), signs in org_emp_signin4.items() if o == org and 0 in signs}
    nosign = len(unsigned)
    results4.append((org, gt4, hc, nosign))

hdr4 = ["代运营商","昨日拜访>4人数","HC编制","HC达标率","未签到人数"]
BOLD_WHITE = Font(color="FFFFFF", bold=True, size=12)
for col, h in enumerate(hdr4, 1):
    c = ws4.cell(1, col, h); c.fill = HEADER_FILL; c.font = BOLD_WHITE; c.alignment = CENTER
ws4.row_dimensions[1].height = 32
for r_idx, (org, gt4, hc, nosign) in enumerate(results4, 2):
    rate = round(gt4/hc*100,1) if hc > 0 else 0
    ws4.row_dimensions[r_idx].height = 28
    for col, v in enumerate([org, gt4, hc, f"{rate}%", nosign], 1):
        c = ws4.cell(r_idx, col, v); c.alignment = CENTER
    cr = ws4.cell(r_idx, 4)
    if rate >= 80: ws4.cell(r_idx,2).fill = GREEN_FILL; cr.fill = GREEN_FILL
    elif rate >= 60: ws4.cell(r_idx,2).fill = YELLOW_FILL; cr.fill = YELLOW_FILL
    elif rate >= 40: ws4.cell(r_idx,2).fill = ORANGE_FILL; cr.fill = ORANGE_FILL
    else: ws4.cell(r_idx,2).fill = RED_FILL; cr.fill = RED_FILL
    ws4.cell(r_idx,5).fill = RED_FILL if nosign > 0 else GREEN_FILL
r = len(results4)+2
total_gt4 = sum(x[1] for x in results4); total_hc = sum(x[2] for x in results4)
total_nosign = sum(x[3] for x in results4)
total_rate = round(total_gt4/total_hc*100,1) if total_hc > 0 else 0
BOLD_FONT = Font(bold=True, size=12)
for col, v in enumerate(['合计', total_gt4, total_hc, f"{total_rate}%", total_nosign], 1):
    c = ws4.cell(r, col, v); c.fill = TOTAL_FILL; c.font = BOLD_FONT; c.alignment = CENTER
ws4.column_dimensions['A'].width = 32
for col in ['B','C','D','E']: ws4.column_dimensions[col].width = 16

# ---- 更新 task-canvas.html 的 VISIT_DATA ----
import re, base64, urllib.request

# 简称映射
ORG_SHORT = {
    '义乌市汐洋-金华义乌乐生活组': '义乌汐洋',
    '惠安广通-晋江乐生活组': '惠安广通',
    '惠州市巨浪-惠州乐生活组': '惠州巨浪',
    '惠州市柏万-惠阳乐生活组': '惠州柏万',
    '泉州市小花猫-泉州乐生活组': '泉州小花猫',
    '慈溪哲光-金华义乌乐生活组': '慈溪哲光',
}

rows_js = []
for (org, gt4, hc, nosign) in results4:
    short = ORG_SHORT.get(org, org[:6])
    rows_js.append(f"    ['{short}', {hc}, {gt4}, {nosign}],")

new_visit_data = (
    "// VISIT_DATA_START — 每日09:00由fetch_visit_analysis.py自动更新\n"
    "const VISIT_DATA = {\n"
    f"  date: '{target_date}',\n"
    "  // [代运营商简称, HC编制, 日拜访>4人数, 未签到人数]\n"
    "  rows: [\n"
    + "\n".join(rows_js) + "\n"
    "  ]\n"
    "};\n"
    "// VISIT_DATA_END"
)

html_path = '/root/.openclaw/workspace/task-canvas.html'
with open(html_path, 'r') as f:
    html = f.read()

html_new = re.sub(
    r'// VISIT_DATA_START[\s\S]*?// VISIT_DATA_END',
    new_visit_data,
    html
)
if html_new == html:
    print("WARNING: VISIT_DATA替换失败")
else:
    with open(html_path, 'w') as f:
        f.write(html_new)
    print(f"✓ task-canvas.html VISIT_DATA已更新（{target_date}，{len(results4)}个代运营商）")

    # 推送GitHub
    GH_TOKEN = ''
    GH_REPO = 'huhu2u/task-canvas'
    with open(html_path, 'rb') as f:
        content = base64.b64encode(f.read()).decode()
    req = urllib.request.Request(
        f'https://api.github.com/repos/{GH_REPO}/contents/index.html',
        headers={'Authorization': f'token {GH_TOKEN}', 'Accept': 'application/vnd.github.v3+json'})
    info = json.loads(urllib.request.urlopen(req, timeout=10).read())
    sha = info['sha']
    put_data = json.dumps({'message': f'update VISIT_DATA {target_date}', 'content': content, 'sha': sha}).encode()
    preq = urllib.request.Request(
        f'https://api.github.com/repos/{GH_REPO}/contents/index.html',
        data=put_data, method='PUT',
        headers={'Authorization': f'token {GH_TOKEN}', 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json'})
    r = json.loads(urllib.request.urlopen(preq, timeout=15).read())
    print(f"✓ GitHub已推送: {r['commit']['sha'][:8]}")
