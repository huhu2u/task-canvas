#!/usr/bin/env python3
"""
每日业绩看板更新+发送脚本
流程：fetch_finance_data.py拉最新数据 → 更新gen_v27.py的OPS → 生成图片 → 发给英杰

用法：
  python3 update_and_send_dashboard.py                          # 从Apollo自动抓取
  python3 update_and_send_dashboard.py --mtd-file <xlsx>        # 仅指定MTD文件（个人模版指标）
  python3 update_and_send_dashboard.py --daily-file <xlsx>      # 仅指定昨日文件（全部指标）
  python3 update_and_send_dashboard.py --mtd-file <xlsx> --daily-file <xlsx>  # 完全离线
"""
import subprocess, sys, json, re, argparse
import pandas as pd
from datetime import datetime, date
from pathlib import Path

TODAY = date.today().strftime("%Y-%m-%d")
log = lambda msg: print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ── 解析参数 ─────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--mtd-file',   default=None, help='PC业绩看板个人模版指标xlsx（含MTD列）')
parser.add_argument('--daily-file', default=None, help='PC业绩看板全部指标xlsx（含日环比，用于昨日GTV）')
args, _ = parser.parse_known_args()

NAME_MAP = {
    '惠州市巨浪-惠州乐生活组':   '惠州巨浪',
    '惠州市柏万-惠阳乐生活组':   '惠州柏万',
    '泉州市小花猫-泉州乐生活组': '泉州小花猫',
    '惠安广通-晋江乐生活组':     '惠安广通',
    '慈溪哲光-金华义乌乐生活组': '慈溪哲光',
    '义乌市汐洋-金华义乌乐生活组':'义乌汐洋',
}

DATA_FILE = Path("/root/.openclaw/workspace/data/finance_data.json")

if args.mtd_file:
    # ── 离线模式：从xlsx直接读取并写入finance_data.json ──
    log(f"Step1: 从本地文件读取MTD数据: {args.mtd_file}")
    df_mtd = pd.read_excel(args.mtd_file)
    l2_mtd = df_mtd[df_mtd['层级'] == 'L2'].copy()
    l3_mtd = df_mtd[df_mtd['层级'] == 'L3'].iloc[0]

    # 读取现有或初始化data
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            data = json.load(f)
    else:
        data = {"ops": [{"name": n} for n in ["惠州巨浪","惠州柏万","泉州小花猫","惠安广通","慈溪哲光","义乌汐洋"]]}

    # 更新汇总
    data['gtv_m']  = round(float(l3_mtd['中小发_代运营高线城市_实付验证GTV（剔除风控+退款）']), 0)
    data['cpc_m']  = round(float(l3_mtd['中小发_代运营_CPC&QCPS消耗额（不含区县）']), 0)
    data['mem_m']  = round(float(l3_mtd['MEM收款额']), 2)
    data['time']   = datetime.now().strftime('%Y-%m-%d %H:%M')

    # 更新各代运营商
    ops_map = {o['name']: o for o in data.get('ops', [])}
    for _, row in l2_mtd.iterrows():
        name = NAME_MAP.get(row['L2'])
        if not name:
            continue
        op = ops_map.setdefault(name, {'name': name})
        op['gtv']     = round(float(row['中小发_代运营高线城市_实付验证GTV（剔除风控+退款）']), 2)
        op['cpc']     = round(float(row['中小发_代运营_CPC&QCPS消耗额（不含区县）']), 2)
        op['mem']     = round(float(row['MEM收款额']), 2)
        op['wpu']     = round(float(row['旺铺通消耗额']), 2) if pd.notna(row.get('旺铺通消耗额')) else op.get('wpu', 0)
        op['excl']    = round(float(row['中小发_代运营_高线城市GTV剔除率']) * 100, 4) if pd.notna(row.get('中小发_代运营_高线城市GTV剔除率')) else op.get('excl', 0)
        op['new_sgn'] = int(row['中小发_代运营_CPC有效新签门店数']) if pd.notna(row.get('中小发_代运营_CPC有效新签门店数')) else op.get('new_sgn', 0)
        # 暂时保留gtv_y不变，等daily-file处理
    data['ops'] = list(ops_map.values())
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    log(f"✅ 已写入 {DATA_FILE}")

    if args.daily_file:
        log(f"Step1b: 从本地文件读取昨日GTV: {args.daily_file}")
        df_daily = pd.read_excel(args.daily_file)
        l2_daily = df_daily[df_daily['层级'] == 'L2'].copy()
        ops_map = {o['name']: o for o in data.get('ops', [])}
        for _, row in l2_daily.iterrows():
            name = NAME_MAP.get(row['L2'])
            if name and name in ops_map:
                v = row['中小发_代运营高线城市_实付验证GTV（剔除风控+退款）']
                ops_map[name]['gtv_y'] = round(float(v), 2) if pd.notna(v) else 0
        data['ops'] = list(ops_map.values())
        DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        log("✅ 昨日GTV已写入")
    else:
        log("⚠️ 未提供--daily-file，昨日GTV保持原值")

else:
    # ── 在线模式：从Apollo API拉数据 ─────────────────
    log("Step1: 从Apollo API拉最新财收数据...")
    r = subprocess.run(
        ["python3", "/root/.openclaw/workspace/scripts/fetch_finance_data_api.py"],
        capture_output=True, text=True, timeout=60
    )
    log(r.stdout[-600:] if r.stdout else "no stdout")
    if r.returncode != 0:
        log(f"❌ fetch失败: {r.stderr[-300:]}")
        sys.exit(1)

    # ── Step1b: 补充昨日GTV（从财收分析页单独抓取，只写gtv_y字段）────────────
    log("Step1b: 补充昨日GTV...")
    r2 = subprocess.run(
        ["python3", "/root/.openclaw/workspace/scripts/fetch_ytd_gtv.py"],
        capture_output=True, text=True, timeout=120
    )
    if r2.returncode == 0:
        log("昨日GTV抓取完成")
    else:
        log(f"⚠️ 昨日GTV抓取失败（继续）: {r2.stderr[-100:]}")

# ── Step2: 读取finance_data.json ──────────────────────
DATA_FILE = Path("/root/.openclaw/workspace/data/finance_data.json")
if not DATA_FILE.exists():
    log("❌ finance_data.json不存在")
    sys.exit(1)

data = json.loads(DATA_FILE.read_text())
log(f"数据时间: {data.get('time')}")

# ops数据字段映射（2026-03-31更新，列索引已修正）：
#   gtv     = 月GTV（实付验证，col20）
#   gtv_y   = 昨日GTV（col21）
#   cpc     = 月CPC&QCPS消耗额（col10）
#   mem     = MEM收款额（col1）
#   excl    = GTV剔除率%（col14）
#   renewal = MEM续约率%（col6）
#   new_sgn = CPC有效新签（col9）
#   wpu     = 旺铺通消耗额（col19）

# 代运营商固定信息（负责人、目标、有效新签目标等）
OP_META = {
    "惠州巨浪":  {"owner": "肖立铭", "gtv_tgt": 3922600, "cpc_tgt": 58740,  "new_tgt": 18, "mem_renewal": 0.5179, "mem_mom": 0.6687},
    "惠州柏万":  {"owner": "林启梁", "gtv_tgt": 3355000, "cpc_tgt": 88330,  "new_tgt": 14, "mem_renewal": 0.5208, "mem_mom": 0.0417},
    "泉州小花猫":{"owner": "康子诚", "gtv_tgt": 3089900, "cpc_tgt": 123530, "new_tgt": 14, "mem_renewal": 0.4595, "mem_mom": 0.6081},
    "惠安广通":  {"owner": "尤云生", "gtv_tgt": 2477200, "cpc_tgt": 51260,  "new_tgt": 10, "mem_renewal": 0.5238, "mem_mom":-0.0833},
    "慈溪哲光":  {"owner": "贾凌姗", "gtv_tgt": 3891648, "cpc_tgt": 158008, "new_tgt": 12, "mem_renewal": 0.5172, "mem_mom": 0.0345},
    "义乌汐洋":  {"owner": "陈铨",   "gtv_tgt": 3764960, "cpc_tgt": 139466, "new_tgt":  6, "mem_renewal": 0.5385, "mem_mom": 0.0000},
}
ORDER = ["惠州巨浪","惠州柏万","泉州小花猫","惠安广通","慈溪哲光","义乌汐洋"]

# 从ops数据组装
ops_map = {o["name"]: o for o in data.get("ops", [])}

ops_lines = []
for name in ORDER:
    o = ops_map.get(name, {})
    meta = OP_META.get(name, {})
    
    gtv_month = int(o.get("gtv", 0))      # 月GTV（实付验证）
    cpc_month = int(o.get("cpc", 0))      # 月CPC&QCPS消耗额
    mem_month = int(o.get("mem", 0))      # MEM收款
    gtv_yday  = int(o.get("gtv_y", 0))   # 昨日GTV
    excl_rate = o.get("excl", 0) / 100.0 if o.get("excl", 0) > 1 else o.get("excl", 0)
    renewal   = o.get("renewal", meta.get("mem_renewal", 0))
    if renewal > 1: renewal = renewal / 100.0  # 如果是百分比值转换
    new_sgn   = int(o.get("new_sgn", 0))  # 有效新签
    wpu       = int(o.get("wpu", 0))      # 旺铺通消耗额
    gtv_tgt = meta.get("gtv_tgt", 0)
    cpc_tgt = meta.get("cpc_tgt", 0)
    new_tgt = meta.get("new_tgt", 0)
    owner = meta.get("owner", "")
    mem_renewal = meta.get("mem_renewal", 0)
    mem_mom = meta.get("mem_mom", 0)
    
    ops_lines.append((name, owner, gtv_month, gtv_tgt, gtv_yday, cpc_month, cpc_tgt, new_sgn, wpu, mem_month, renewal, mem_mom, excl_rate))
    log(f"  {name}: GTV={gtv_month:,} 昨日GTV={gtv_yday:,} CPC={cpc_month:,} 新签={new_sgn} 旺铺通={wpu:,} MEM={mem_month:,}")

# ── Step3: 更新gen_v27.py的OPS数据块 ─────────────────
GEN_FILE = Path("/root/.openclaw/workspace/gen_v27.py")
content = GEN_FILE.read_text()

# 构建新的OPS块（dict格式，与gen_v27.py保持一致）
new_ops_lines = [f"# ── 代运营商数据（Apollo {data.get('time', TODAY)}更新） ──",
                 "OPS = ["]

NAME_PAD = 8
for name, owner, gtv_m, gtv_tgt, gtv_yday, cpc_m, cpc_tgt, new_sgn, wpu_m, mem_m, renewal, mom, excl_r in ops_lines:
    short = name.replace("惠州市", "惠州").replace("泉州市", "泉州").replace("义乌市", "义乌")
    new_tgt = OP_META[name]["new_tgt"]
    mem_renewal = OP_META[name].get("mem_renewal", renewal)
    mem_mom = OP_META[name].get("mem_mom", mom)
    new_ops_lines.append(
        f'    {{"name": "{short}", "owner": "{owner}", '
        f'"gtv": {gtv_m}, "gtv_tgt": {gtv_tgt}, "gtv_y": {gtv_yday}, "excl": {excl_r:.4f}, '
        f'"cpc": {cpc_m}, "cpc_tgt": {cpc_tgt}, "cpc_y": 0, "cpc_newsgn": {new_sgn}, "cpc_new_tgt": {new_tgt}, "cpc_wpu": {wpu_m}, '
        f'"mem": {mem_m}, "mem_renewal": {mem_renewal:.4f}, "mem_mom": {mem_mom:.4f}}},'
    )

new_ops_lines.append("]")
new_ops_block = "\n".join(new_ops_lines)

# 替换OPS块（从注释行到]）
new_content = re.sub(
    r'# ── 代运营商数据.*?^]',
    new_ops_block,
    content,
    flags=re.DOTALL | re.MULTILINE
)

if new_content == content:
    log("⚠️ OPS块替换失败，尝试直接替换OPS = [...]")
    new_content = re.sub(r'OPS = \[.*?\]', 
                          '\n'.join(new_ops_lines),
                          content, flags=re.DOTALL)

GEN_FILE.write_text(new_content)
log(f"✅ gen_v27.py OPS数据已更新")

# ── Step4: 生成图片 ───────────────────────────────────
log("Step4: 生成业绩看板图片...")
r2 = subprocess.run(
    ["python3", "/root/.openclaw/workspace/gen_v27.py"],
    capture_output=True, text=True, timeout=60,
    cwd="/root/.openclaw/workspace"
)
log(r2.stdout[-300:] if r2.stdout else "no output")
if r2.returncode != 0:
    log(f"❌ 生成失败: {r2.stderr[-300:]}")
    sys.exit(1)

IMG = "/tmp/files/dashboard_v27.png"
if not Path(IMG).exists():
    log(f"❌ 图片不存在: {IMG}")
    sys.exit(1)
log(f"✅ 图片生成: {Path(IMG).stat().st_size // 1024}KB")

# ── Step5: 发送 ───────────────────────────────────────
log("Step5: 发送给英杰...")
# 使用openclaw内置API发送（避免CLI版本冲突）
import urllib.request, base64, json as _json
cfg_path = Path("/root/.openclaw/openclaw.json")
try:
    # 直接用media发送图片
    r3 = subprocess.run(
        ["openclaw", "message", "send",
         "--target", "3264994429",
         "--channel", "daxiang",
         "--media", IMG,
         "--message", f"📊 粤闽浙业绩进度表（{data.get('time', TODAY)}）"],
        capture_output=True, text=True, timeout=60
    )
    if r3.returncode == 0:
        log("✅ 发送成功（CLI）")
    else:
        log(f"⚠️ CLI发送异常，已生成图片: {IMG}")
        log(f"stderr: {r3.stderr[-200:]}")
        # 不退出，图片已生成，cron的announce模式会处理发送
except Exception as e:
    log(f"⚠️ 发送异常: {e}，图片已生成: {IMG}")

log("🎉 全部完成")
