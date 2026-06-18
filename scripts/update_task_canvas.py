import pandas as pd
import re
import os
import base64
import requests
from datetime import datetime

# Load data
df_m = pd.read_excel('/tmp/files/1779933841.xlsx')
df_d = pd.read_excel('/tmp/files/1779933791.xlsx')

# 职人码 - skip merged title row
wb_zrq = pd.ExcelFile('/tmp/粤闽浙职人码分析_20260528.xlsx')
ws_zrq = pd.read_excel(wb_zrq, sheet_name=0, header=1)

# 好店动销 - columns are unnamed, use position
wb_dx = pd.ExcelFile('/tmp/粤闽浙好店职人码动销分析表.xlsx')
ws_dx = pd.read_excel(wb_dx, sheet_name=0, header=1)
ws_dx.columns = ['代运营商','好店池','5月目标','已达标','达标率','目标缺口','日净增达标','2-3单','1单','零动销','已绑码','未绑码','好店动销率']

# 经营评分
wb_sc = pd.ExcelFile('/tmp/粤闽浙好店经营评分分析_20260528.xlsx')
ws_sc = pd.read_excel(wb_sc, sheet_name=0, header=1)
ws_sc.columns = ['代运营商','物理好店数','当前达标','日变化','当前达标率','5月目标','目标缺口','优先级做工','尚需关注','平均评分']

# MEM断续约
wb_mem = pd.ExcelFile('/tmp/MEM断续约分析_2026-05-28.xlsx')
ws_mem = pd.read_excel(wb_mem, sheet_name=0, header=1)
ws_mem.columns = ['代运营商','到期总数','参与续约计算','已续约','昨日新增续约','未续约','续约率','紧急(≤30天未续)']

# 旺铺通
wb_wp = pd.ExcelFile('/tmp/粤闽浙旺铺通分析_20260528.xlsx')
ws_wp = pd.read_excel(wb_wp, sheet_name=0, header=1)
ws_wp.columns = ['代运营商','好店数','开通数','日变化','好店开通','好店未开通','好店开通率','消耗额','好店消耗额','好店金额占比','人均消耗']

# 欧若拉代办
df_aur = pd.read_csv('/tmp/files/1779934488.csv')
op_map = {
    '惠州巨浪': ['惠州巨浪', '惠州市巨浪'],
    '惠州柏万': ['惠州柏万', '惠州市柏万'],
    '泉州小花猫': ['小花猫', '泉州市小花猫'],
    '惠安广通': ['惠安广通', '惠安县广通'],
    '慈溪哲光': ['慈溪哲光', '慈溪市哲光'],
    '义乌汐洋': ['义乌汐洋', '义乌市汐洋'],
}
def map_op(org_str):
    if pd.isna(org_str): return '未知'
    org = str(org_str)
    for op, kws in op_map.items():
        for kw in kws:
            if kw in org:
                return op
    return '未知'
df_aur['代运营商'] = df_aur['组织架构'].apply(map_op)

ops = ['惠州巨浪','惠州柏万','泉州小花猫','惠安广通','慈溪哲光','义乌汐洋']
result = {}

for op in ops:
    d = {}
    
    # GTV/业绩 from monthly MTD - L2 names have 市 prefix
    m_row = df_m[(df_m['层级']=='L2') & (df_m['L2'].str.contains(op, na=False))]
    if len(m_row)==0:
        # Try matching org -> op (L2 has city prefix)
        m_row = df_m[(df_m['层级']=='L2')]
        for _, mr in m_row.iterrows():
            org_name = str(mr['L2']).replace('市','').replace('县','')
            if org_name.startswith(op):
                m_row = pd.DataFrame([mr])
                break
    if len(m_row)>0:
        m = m_row.iloc[0]
        gtv_t = m.get('中小发_代运营高线城市_实付验证GTV（剔除风控+退款）目标值')
        gtv_r = m.get('中小发_代运营高线城市_实付验证GTV（剔除风控+退款）目标完成率')
        d['gtv'] = float(gtv_t * gtv_r) if pd.notna(gtv_t) and pd.notna(gtv_r) else 0
        d['gtv_excl'] = float(m['中小发_代运营_高线城市GTV剔除率'])*100 if pd.notna(m['中小发_代运营_高线城市GTV剔除率']) else 0
        cpc_t = m.get('中小发_代运营_CPC&QCPS消耗额（不含区县）目标值')
        cpc_r = m.get('中小发_代运营_CPC&QCPS消耗额（不含区县）目标完成率')
        d['cpc'] = float(cpc_t * cpc_r) if pd.notna(cpc_t) and pd.notna(cpc_r) else 0
        d['cpc_newsgn'] = int(m['中小发_代运营_CPC有效新签门店数']) if pd.notna(m['中小发_代运营_CPC有效新签门店数']) else 0
        d['mem'] = float(m['MEM收款额']) if pd.notna(m['MEM收款额']) else 0
        d['memrate'] = float(m['MEM续约率']) if pd.notna(m['MEM续约率']) else 0
    
    # 昨日数据 - L2 names have 市 prefix
    d_row = df_d[(df_d['层级']=='L2') & (df_d['L2'].str.contains(op, na=False))]
    if len(d_row)==0:
        d_row = df_d[(df_d['层级']=='L2')]
        for _, dr in d_row.iterrows():
            org_name = str(dr['L2']).replace('市','').replace('县','')
            if org_name.startswith(op):
                d_row = pd.DataFrame([dr])
                break
    if len(d_row)>0:
        d_r = d_row.iloc[0]
        d['gtv_y'] = float(d_r['中小发_代运营高线城市_实付验证GTV（剔除风控+退款）']) if pd.notna(d_r['中小发_代运营高线城市_实付验证GTV（剔除风控+退款）']) else 0
        d['cpc_y'] = float(d_r['CPC消耗额']) if pd.notna(d_r['CPC消耗额']) else 0
        d['cpc_wpu'] = float(d_r['旺铺通消耗额']) if pd.notna(d_r['旺铺通消耗额']) else 0
        d['cps'] = float(d_r['中小发代运营高线城市_交易收入（剔除风控+退款）']) if pd.notna(d_r['中小发代运营高线城市_交易收入（剔除风控+退款）']) else 0
    
    # 职人码
    zrq_row = ws_zrq[ws_zrq['代运营商']==op]
    if len(zrq_row)>0:
        r = zrq_row.iloc[0]
        d['zrq_shops'] = int(r['合作门店数']) if pd.notna(r['合作门店数']) else 0
        d['zrq_bind'] = int(r['绑码商户数']) if pd.notna(r['绑码商户数']) else 0
        d['zrq_bindrate'] = round(float(r['绑码率\n(绑码/合作门店)'])*100, 1) if pd.notna(r['绑码率\n(绑码/合作门店)']) else 0
        d['zrq_bind_inc_m'] = int(r['月净增绑码数\n(vs 5月1日)']) if pd.notna(r['月净增绑码数\n(vs 5月1日)']) else 0
        d['zrq_bind_inc_d'] = int(r['日净增绑码数\n(vs昨日)']) if pd.notna(r['日净增绑码数\n(vs昨日)']) else 0
        d['zrq_dong'] = int(r['有效动销门店数']) if pd.notna(r['有效动销门店数']) else 0
        d['zrq_dongrate'] = round(float(r['动销率'])*100, 1) if pd.notna(r['动销率']) else 0
        d['zrq_gtv'] = int(r['店转GTV（元）']) if pd.notna(r['店转GTV（元）']) else 0
        d['zrq_gtv_y'] = int(r['昨日店转GTV']) if pd.notna(r['昨日店转GTV']) else 0
        d['zrq_pct'] = round(float(r['店转GTV渗透率'])*100, 1) if pd.notna(r['店转GTV渗透率']) else 0
        d['zrq_pct_y'] = round(float(r['昨日店转渗透率'])*100, 1) if pd.notna(r['昨日店转渗透率']) else 0
        d['zrq_pay'] = int(r['实付GTV（元）']) if pd.notna(r.get('实付GTV（元）','')) else 0
        d['zrq_pay_y'] = int(r['昨日实付GTV']) if pd.notna(r['昨日实付GTV']) else 0
        d['zrq_aov'] = round(float(r['店转客单均价']), 1) if pd.notna(r['店转客单均价']) else 0
    
    # 好店动销
    dx_row = ws_dx[ws_dx['代运营商']==op]
    if len(dx_row)>0:
        r = dx_row.iloc[0]
        d['dongxiao'] = int(r['已达标']) if pd.notna(r['已达标']) else 0
        d['dongxiao_day'] = int(r['日净增达标']) if pd.notna(r['日净增达标']) else 0
    
    # 经营评分
    sc_row = ws_sc[ws_sc['代运营商']==op]
    if len(sc_row)>0:
        r = sc_row.iloc[0]
        d['score'] = int(r['当前达标']) if pd.notna(r['当前达标']) else 0
        d['score_near'] = int(r['优先级做工']) if pd.notna(r['优先级做工']) else 0
    
    # MEM断续约
    mem_row = ws_mem[ws_mem['代运营商']==op]
    if len(mem_row)>0:
        r = mem_row.iloc[0]
        d['memrenew'] = int(r['已续约']) if pd.notna(r['已续约']) else 0
        d['memexpire'] = int(r['参与续约计算']) if pd.notna(r['参与续约计算']) else 0
        d['memurgent'] = int(r['紧急(≤30天未续)']) if pd.notna(r['紧急(≤30天未续)']) else 0
        renew_day = r['昨日新增续约']
        d['memrenew_day'] = int(renew_day) if pd.notna(renew_day) and isinstance(renew_day, (int,float)) else '-'
    
    # 旺铺通
    wp_row = ws_wp[ws_wp['代运营商']==op]
    if len(wp_row)>0:
        r = wp_row.iloc[0]
        d['wpu_open'] = int(r['开通数']) if pd.notna(r['开通数']) else 0
        d['wpu_pool'] = int(r['好店数']) if pd.notna(r['好店数']) else 0
        d['wpu_rate'] = round(float(r['好店开通率'])*100, 1) if pd.notna(r['好店开通率']) else 0
        d['wpu_day'] = int(r['日变化']) if pd.notna(r['日变化']) else 0
    
    # 欧若拉代办
    aur_sub = df_aur[df_aur['代运营商']==op]
    if len(aur_sub)>0:
        t = len(aur_sub)
        d['aurora_total'] = t
        d['aurora_act_done'] = len(aur_sub[aur_sub['动作是否完成']=='已完成'])
        d['aurora_act_pend'] = t - d['aurora_act_done']
        d['aurora_res_done'] = len(aur_sub[aur_sub['结果是否完成']=='已完成'])
        d['aurora_res_pend'] = t - d['aurora_res_done']
    
    result[op] = d
    print(f"{op}: gtv={d.get('gtv',0):,.0f} cpc={d.get('cpc',0):,.0f} mem={d.get('mem',0):,.0f} zrq_bind={d.get('zrq_bind',0)} dongxiao={d.get('dongxiao',0)} score={d.get('score',0)} aurora={d.get('aurora_total',0)}")

# Update HTML
with open('/root/.openclaw/workspace/task-canvas.html', 'r') as f:
    content = f.read()

d_start = content.find("const D={")
d_end_marker = content.find("};\n", d_start) + 2
D_block = content[d_start:d_end_marker]

for op in ops:
    op_start = D_block.find(f'"{op}":')
    if op_start < 0:
        print(f"WARNING: {op} not found")
        continue
    
    depth = 0
    brace_end = -1
    for i in range(op_start, len(D_block)):
        if D_block[i] == '{': depth += 1
        elif D_block[i] == '}': depth -= 1
        if depth == 0:
            brace_end = i
            break
    
    if brace_end < 0:
        print(f"WARNING: {op} brace not found")
        continue
    
    defs = result[op]
    fields = []
    for k, v in defs.items():
        if v == '-':
            fields.append(f"  {k}:'{v}'")
        elif isinstance(v, (int, float)):
            fields.append(f"  {k}:{v}")
        else:
            fields.append(f"  {k}:'{v}'")
    
    new_block = "{\n" + ",\n".join(fields) + "\n  }"
    D_block = D_block[:op_start + len(f'"{op}":')] + " " + new_block + D_block[brace_end+1:]

print(f"\nUpdated {len(ops)} operators")

# Update _dataDate and EMBED_VER
now = datetime.now()
now_str = now.strftime('%H:%M')

m = re.search(r"_dataDate==='2026-05-28([a-z]+)'", content)
if m:
    old_suffix = m.group(1)
    last_char = old_suffix[-1]
    new_suffix = old_suffix[:-1] + chr(ord(last_char) + 1)
    print(f"_dataDate: {old_suffix} -> {new_suffix}")
    content = re.sub(r"_dataDate==='2026-05-28[a-z]+'", f"_dataDate==='2026-05-28{new_suffix}'", content)
    content = re.sub(r"_dataDate:'2026-05-28[a-z]+'", f"_dataDate:'2026-05-28{new_suffix}'", content)

content = re.sub(r"const EMBED_VER = '[^']+'", f"const EMBED_VER = '2026-05-28z'", content)
content = re.sub(r"_updated:'\d{2}:\d{2}'", f"_updated:'{now_str}'", content)

content = content[:d_start] + D_block + content[d_end_marker:]

with open('/root/.openclaw/workspace/task-canvas.html', 'w') as f:
    f.write(content)
print(f"HTML updated, time: {now_str}")

# Push to GitHub
with open('/root/.openclaw/gh_token') as f:
    GH_TOKEN = f.read().strip()

with open('/root/.openclaw/workspace/task-canvas.html', 'rb') as f:
    file_content = f.read()

api = "https://api.github.com/repos/huhu2u/task-canvas/contents/index.html"
headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}

r = requests.get(api, headers=headers)
sha = r.json()["sha"]
print(f"SHA: {sha[:12]}")

r = requests.put(api, headers=headers, json={
    "message": f"update: 2026-05-28 full dashboard ({now_str})",
    "content": base64.b64encode(file_content).decode(),
    "sha": sha
})

if r.status_code == 200:
    commit = r.json().get("commit", {}).get("sha", "")
    print(f"Pushed! commit: {commit[:12]}")
else:
    print(f"Push failed: {r.status_code} {r.text[:300]}")
