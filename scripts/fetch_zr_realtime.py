#!/usr/bin/env python3
"""
职人码实时数据抓取脚本 v2
从Apollo职人码页面用DOM直接读取，写入 data/zr_realtime.json
"""
import subprocess, json, os, datetime, sys, time, re, base64, urllib.request

WORKSPACE = "/root/.openclaw/workspace"
OUT_FILE = f"{WORKSPACE}/data/zr_realtime.json"
DAILY_FILE = f"{WORKSPACE}/data/zrq_daily_bind.json"
GH_TOKEN = ""
GH_REPO = "huhu2u/task-canvas"

APOLLO_URL = "https://apollo.meituan.com/crm-platform?iurl=JTJGJTJGYXBvbGxvLm1laXR1YW4uY29tJTJGY3JtLXBjLWRhdGEtYnVsbGV0aW4tYm9hcmQlMkZzdHJhdGVneS1tYW5hZ2VtZW50JTJGaW5kZXguaHRtbCUyMyUyRmRhdGEtb3ZlcnZpZXclM0ZzdHJhdGVneUlkJTNENw%253D%253D&pageId=1721888474rcncbe"

# 列索引
COL_NAME = 0
COL_TODAY_GTV = 1
COL_TODAY_ORDERS = 2
COL_SHOPS = 3
COL_BIND_CNT = 4
COL_MATERIAL_CNT = 5
COL_SALE_SHOP = 6
COL_BIND_RATE = 7
COL_MATERIAL_RATE = 8
COL_SALE_RATE = 9
COL_MONTH_SALE_ORDERS = 10   # 月累计店转订单量
COL_MONTH_SALE_GTV = 12      # 月累计店转GTV
COL_MONTH_SALE_GTV_RATE = 13 # 月累计店转GTV渗透率
COL_MONTH_GTV = 26           # 月累计核销实付GTV（整体）
COL_MONTH_ORDERS = 27        # 月累计订单量

JS_EXPAND_AND_READ = r"""
(function() {
  var iframe = document.querySelector('iframe');
  var iwin = iframe ? iframe.contentWindow : null;
  if (!iwin) return JSON.stringify({err: 'no iframe'});

  // 先展开所有未展开的行
  var icons = Array.from(iwin.document.querySelectorAll('.mtd-table-tree-expand-icon:not(.mtd-table-expand-icon-expanded)'));
  icons.forEach(function(i){ i.click(); });

  // 读取表格行
  var rows = Array.from(iwin.document.querySelectorAll('tr.mtd-table-row'));
  var data = rows.map(function(r){
    var cells = Array.from(r.querySelectorAll('td'));
    return cells.map(function(c){ return c.textContent.trim().replace(/\s+/g,' '); });
  }).filter(function(r){ return r.length > 5; });

  return JSON.stringify({rows: data, expanded: icons.length});
})()
"""

SESSION = "apollo"

def run_ab(cmd_args, stdin_data=None):
    kwargs = dict(capture_output=True, text=True, timeout=30)
    if stdin_data:
        kwargs['input'] = stdin_data
    r = subprocess.run(["agent-browser", "--session", SESSION] + cmd_args, **kwargs)
    return r.stdout.strip(), r.returncode

def eval_js(js_code):
    out, _ = run_ab(["eval", "--stdin"], stdin_data=js_code)
    out = out.strip()
    if out.startswith('"') and out.endswith('"'):
        try:
            out = json.loads(out)
        except:
            out = out[1:-1]
    return out

def safe_num(val, is_float=False):
    try:
        v = str(val).replace(',', '').replace('%', '').strip()
        if not v or v == '-' or v == '0.0%':
            return 0
        return float(v) if is_float else int(float(v))
    except:
        return 0

def is_org_row(name):
    """判断是代运营商行（有-且含乐生活）"""
    return '-' in name and '乐生活' in name

def is_total_row(name):
    return '高线粤闽浙城市群' in name

def main():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    print(f"[{now.strftime('%H:%M:%S')}] 开始抓取职人码实时数据 (DOM方式)...")

    # 确保浏览器已打开Apollo职人码页面
    url_out, _ = run_ab(["get", "url"])
    if "strategy-management" not in url_out:
        print("  打开Apollo职人码页面...")
        run_ab(["open", APOLLO_URL])
        time.sleep(8)
    else:
        print("  Apollo职人码页面已打开，直接读取...")

    # 展开并读取DOM数据（最多三轮展开，确保L2销售行全部加载）
    print("  读取表格数据...")
    rows = []
    for round_i in range(3):
        out = eval_js(JS_EXPAND_AND_READ)
        if not out:
            print("  ERROR: eval返回空")
            sys.exit(1)
        try:
            parsed = json.loads(out)
        except Exception as e:
            print(f"  ERROR: JSON解析失败: {e}\n  raw: {out[:300]}")
            sys.exit(1)
        if 'err' in parsed:
            print(f"  ERROR: {parsed['err']}")
            sys.exit(1)
        rows = parsed['rows']
        expanded = parsed['expanded']
        print(f"  第{round_i+1}轮：展开了 {expanded} 个折叠行，共读取 {len(rows)} 行")
        if expanded == 0:
            break  # 没有新的待展开，退出
        time.sleep(4)  # 等待新行加载

    # 解析数据
    total_row = None
    org_rows = []
    sales_rows_by_org = {}   # {org_short: [{name, month_sale_gtv}, ...]}
    current_org_short = None

    for row in rows:
        if len(row) < 7:
            continue
        name = row[COL_NAME]
        if is_total_row(name):
            total_row = row
        elif is_org_row(name):
            org_rows.append(row)
            # 记录当前代运营商
            full = name.split("-")[0]
            current_org_short = ORG_SHORT_MAP.get(full, full)
            if current_org_short not in sales_rows_by_org:
                sales_rows_by_org[current_org_short] = []
        elif current_org_short and len(name) >= 2 and len(row) >= 11:
            # 销售个人行：col4=绑码数, col10=月累计店转GTV, col6=今日店转GTV
            month_sale_gtv = safe_num(row[10], True)
            today_sale_gtv = safe_num(row[6], True)
            bind_cnt = safe_num(row[COL_BIND_CNT], False) if len(row) > COL_BIND_CNT else 0
            sales_rows_by_org[current_org_short].append({
                "name": name,
                "month_sale_gtv": month_sale_gtv,
                "today_sale_gtv": today_sale_gtv,
                "bind_cnt": int(bind_cnt) if bind_cnt else 0,
            })

    if not total_row:
        print("  ERROR: 未找到汇总行")
        sys.exit(1)

    def parse_row(row):
        return {
            "name": row[COL_NAME],
            "today_gtv": safe_num(row[COL_TODAY_GTV], True),
            "today_orders": safe_num(row[COL_TODAY_ORDERS]),
            "shops": safe_num(row[COL_SHOPS]),
            "bind_cnt": safe_num(row[COL_BIND_CNT]),
            "material_cnt": safe_num(row[COL_MATERIAL_CNT]),
            "sale_shop_cnt": safe_num(row[COL_SALE_SHOP]),
            "bind_rate": row[COL_BIND_RATE] if len(row) > COL_BIND_RATE else "",
            "month_sale_orders": safe_num(row[COL_MONTH_SALE_ORDERS]) if len(row) > COL_MONTH_SALE_ORDERS else 0,
            "month_sale_gtv": safe_num(row[COL_MONTH_SALE_GTV], True) if len(row) > COL_MONTH_SALE_GTV else 0,
            "month_sale_gtv_rate": row[COL_MONTH_SALE_GTV_RATE] if len(row) > COL_MONTH_SALE_GTV_RATE else "",
            "month_gtv": safe_num(row[COL_MONTH_GTV], True) if len(row) > COL_MONTH_GTV else 0,
            "month_orders": safe_num(row[COL_MONTH_ORDERS]) if len(row) > COL_MONTH_ORDERS else 0,
        }

    result = {
        "update_time": now.strftime("%Y-%m-%d %H:%M"),
        "date": now.strftime("%Y-%m-%d"),
        "total": parse_row(total_row),
        "orgs": [parse_row(r) for r in org_rows]
    }

    # 计算日净增：用今日月累计 - 昨日月累计
    today_str = now.strftime("%Y-%m-%d")
    yesterday_str = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    daily_data = {}
    if os.path.exists(DAILY_FILE):
        with open(DAILY_FILE, 'r') as f:
            daily_data = json.load(f)

    # 提取昨日存档
    yest_data = daily_data.get(yesterday_str, {})

    def org_short_name(full_name):
        """代运营商简称：去掉-xxx部分，再用ORG_SHORT_MAP统一映射"""
        n = full_name.split("-")[0]
        return ORG_SHORT_MAP.get(n, n)

    def calc_daily_diff(org_short, field_today, field_yest_key=None):
        """计算日净增：今日月累计 - 昨日月累计"""
        if not yest_data:
            return None
        yest_key = field_yest_key or org_short
        yest_val = yest_data.get(yest_key, {})
        if not yest_val:
            return None
        return field_today - yest_val

    # 为total和每个org计算日净增
    def enrich_with_daily(row_dict, yest_org_data):
        if yest_org_data is None:
            row_dict["daily_bind_inc"] = None
            row_dict["daily_sale_gtv"] = None
            row_dict["daily_sale_orders"] = None
            row_dict["daily_sale_gtv_rate"] = None
        else:
            row_dict["daily_bind_inc"] = row_dict["bind_cnt"] - yest_org_data.get("bind_cnt", row_dict["bind_cnt"])
            row_dict["daily_sale_gtv"] = round(row_dict["month_sale_gtv"] - yest_org_data.get("month_sale_gtv", row_dict["month_sale_gtv"]), 2)
            row_dict["daily_sale_orders"] = row_dict["month_sale_orders"] - yest_org_data.get("month_sale_orders", row_dict["month_sale_orders"])
            # 渗透率：昨日店转GTV / 今日总GTV（简化）
            if row_dict["today_gtv"] > 0:
                row_dict["daily_sale_gtv_rate"] = f"{row_dict['daily_sale_gtv'] / row_dict['today_gtv'] * 100:.1f}%"
            else:
                row_dict["daily_sale_gtv_rate"] = None
        return row_dict

    # total的昨日数据
    yest_total = yest_data.get("_total", None)
    result["total"] = enrich_with_daily(result["total"], yest_total)

    # 各org的昨日数据
    for org_dict in result["orgs"]:
        short = org_short_name(org_dict["name"])
        yest_org = yest_data.get(short, None)
        org_dict = enrich_with_daily(org_dict, yest_org)

    # 计算销售维度昨日店转GTV（月累计差值）
    # sales_rows_by_org: {org_short: [{name, month_sale_gtv, today_sale_gtv}]}
    result["sales_by_org"] = {}
    for org_short, sales_list in sales_rows_by_org.items():
        yest_sales = yest_data.get(f"_sales_{org_short}", {})
        result["sales_by_org"][org_short] = []
        for s in sales_list:
            sname = s["name"]
            yest_sale_gtv = yest_sales.get(sname, {}).get("month_sale_gtv", None)
            if yest_sale_gtv is not None and s["month_sale_gtv"] >= yest_sale_gtv:
                day_sale_gtv = round(s["month_sale_gtv"] - yest_sale_gtv, 2)
            else:
                day_sale_gtv = None
            result["sales_by_org"][org_short].append({
                "name": sname,
                "month_sale_gtv": s["month_sale_gtv"],
                "today_sale_gtv": s["today_sale_gtv"],
                "day_sale_gtv": day_sale_gtv,
                "bind_cnt": s.get("bind_cnt", 0),
            })

    # 今日存档到daily_data（用月累计，存为今日）
    today_snapshot = {"_total": {
        "bind_cnt": result["total"]["bind_cnt"],
        "month_sale_gtv": result["total"]["month_sale_gtv"],
        "month_sale_orders": result["total"]["month_sale_orders"],
    }}
    for org_dict in result["orgs"]:
        short = org_short_name(org_dict["name"])
        today_snapshot[short] = {
            "bind_cnt": org_dict["bind_cnt"],
            "month_sale_gtv": org_dict["month_sale_gtv"],
            "month_sale_orders": org_dict["month_sale_orders"],
        }
    # 存档销售维度月累计店转GTV + 绑码数
    for org_short, sales_list in result["sales_by_org"].items():
        key = f"_sales_{org_short}"
        today_snapshot[key] = {
            s["name"]: {
                "month_sale_gtv": s["month_sale_gtv"],
                "bind_cnt": s.get("bind_cnt", 0),
            } for s in sales_list
        }
    daily_data[today_str] = today_snapshot
    with open(DAILY_FILE, 'w') as f:
        json.dump(daily_data, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 日存档更新: {today_str}（含{sum(len(v) for v in sales_rows_by_org.values())}个销售）")

    # 写入JSON
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  ✓ 写入 {OUT_FILE}")
    t = result['total']
    print(f"  汇总: 合作门店={t['shops']}, 绑码数={t['bind_cnt']}, 有效物料={t['material_cnt']}, 有销门店={t['sale_shop_cnt']}")
    for o in result['orgs']:
        print(f"    {o['name'][:14]:14s}: 门店={o['shops']:4d} 绑码={o['bind_cnt']:4d} 物料={o['material_cnt']:3d} 有销={o['sale_shop_cnt']:3d}")

    # 更新HTML并推送GitHub
    update_html_and_push(result)
    return result


ORG_SHORT_MAP = {
    "惠州市巨浪": "惠州巨浪",
    "惠州市柏万": "惠州柏万",
    "义乌市汐洋": "义乌汐洋",
    "惠安广通": "惠安广通",
    "慈溪哲光": "慈溪哲光",
    "泉州市小花猫": "泉州小花猫",
}

def org_display_name(full_name):
    short = full_name.split("-")[0]
    return ORG_SHORT_MAP.get(short, short)

def is_valid_daily(val, ref):
    """判断日净增值是否合理（不超过ref的5倍）"""
    if val is None:
        return False
    if ref > 0 and abs(val) > ref * 5:
        return False
    return True

def update_html_and_push(result):
    """把最新数据内嵌到task-canvas.html，更新ZR_LIVE/ZR_TOTAL/ZR_DATE/ZR_RT_FALLBACK，并推送GitHub"""
    html_path = f"{WORKSPACE}/task-canvas.html"

    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
    except FileNotFoundError:
        print(f"  WARNING: {html_path} 不存在，跳过HTML更新")
        return

    # 1. 更新 ZR_RT_FALLBACK
    new_rt_line = f'<script>window.ZR_RT_FALLBACK={json.dumps(result, ensure_ascii=False, separators=(",", ":"))};</script>'
    html_new = re.sub(
        r'<script>window\.ZR_RT_FALLBACK=\{.*?\};</script>',
        new_rt_line,
        html
    )
    if html_new == html:
        print("  WARNING: ZR_RT_FALLBACK替换失败（pattern不匹配）")
    else:
        html = html_new

    # 2. 更新 ZR_LIVE 数组
    # 格式：['简称', 合作门店, 绑码数, 有效铺设数, 有效动销数, 铺设率, 动销率, 店转GTV渗透率, 月店转GTV,
    #         昨日店转GTV(9), 昨日店转GTV渗透率(10), 月净增绑码数(11), 日净增绑码数(12)]
    # 从result.orgs构建，月净增 = 今日绑码 - 月初基准（3-01）
    # 日净增 = daily_bind_inc（如果合理）
    # 昨日店转GTV = daily_sale_gtv（如果合理）

    daily_data = {}
    if os.path.exists(DAILY_FILE):
        with open(DAILY_FILE, 'r') as f:
            daily_data = json.load(f)
    base_data = daily_data.get("2026-03-01", {})  # 月初基准

    zr_live_rows = []
    for o in result["orgs"]:
        full = o["name"].split("-")[0]
        short = ORG_SHORT_MAP.get(full, full)
        shops = o["shops"]
        bind = o["bind_cnt"]
        material = o["material_cnt"]
        dx = o["sale_shop_cnt"]
        pave_rate = round(material / bind, 3) if bind > 0 else 0
        dx_rate = round(dx / material, 3) if material > 0 else 0
        month_sale_rate = float(o.get("month_sale_gtv_rate", "0%").replace("%",""))/100 if isinstance(o.get("month_sale_gtv_rate"), str) else 0
        month_sale_gtv = o.get("month_sale_gtv", 0)

        # 月净增 = 今日绑码 - 3月1日基准
        base_bind = base_data.get(short, {})
        if isinstance(base_bind, dict):
            base_bind_cnt = base_bind.get("bind_cnt", 0)
        else:
            base_bind_cnt = base_bind  # 老格式直接是数字
        month_incr = bind - base_bind_cnt if base_bind_cnt > 0 else None

        # 日净增绑码
        day_inc = o.get("daily_bind_inc")
        if not is_valid_daily(day_inc, bind):
            day_inc = None

        # 昨日店转GTV（月累计差值）
        day_sale_gtv = o.get("daily_sale_gtv")
        if not is_valid_daily(day_sale_gtv, month_sale_gtv):
            day_sale_gtv = None

        # 昨日店转GTV渗透率 = 昨日店转GTV / 昨日总GTV（月累计差值近似）
        day_sale_rate = None
        if day_sale_gtv is not None:
            # 用月店转GTV渗透率作为参考，渗透率直接取daily_sale_gtv_rate字符串转换
            raw_rate = o.get("daily_sale_gtv_rate")
            if raw_rate and isinstance(raw_rate, str) and raw_rate.endswith("%"):
                try:
                    rate_val = float(raw_rate.rstrip("%")) / 100
                    # 渗透率超200%属于异常（今日GTV太小），置null
                    if rate_val <= 2.0:
                        day_sale_rate = round(rate_val, 4)
                except Exception:
                    pass

        # 昨日店转订单数
        day_sale_orders = o.get("daily_sale_orders")
        if not is_valid_daily(day_sale_orders, o.get("month_sale_orders", 0)):
            day_sale_orders = None

        zr_live_rows.append(
            f"  ['{short}', {shops}, {bind}, {material}, {dx}, "
            f"{pave_rate}, {dx_rate}, {month_sale_rate}, {round(month_sale_gtv)}, "
            f"{'null' if day_sale_gtv is None else round(day_sale_gtv, 2)}, "
            f"{'null' if day_sale_rate is None else day_sale_rate}, "
            f"{'null' if month_incr is None else month_incr}, "
            f"{'null' if day_inc is None else day_inc}, "
            f"{'null' if day_sale_orders is None else int(day_sale_orders)}],"
        )

    # 总计
    tot = result["total"]
    tot_base = base_data.get("高线粤闽浙城市群", 0)
    if isinstance(tot_base, dict):
        tot_base_bind = tot_base.get("bind_cnt", 0)
    else:
        tot_base_bind = tot_base

    new_zr_live = "const ZR_LIVE = [\n" + "\n".join(zr_live_rows) + "\n];"
    html = re.sub(r'const ZR_LIVE = \[[\s\S]*?\];', new_zr_live, html)

    # 更新 ZR_TOTAL
    t_bind = tot["bind_cnt"]
    t_shops = tot["shops"]
    t_mat = tot["material_cnt"]
    t_dx = tot["sale_shop_cnt"]
    t_pave = round(t_mat / t_bind, 3) if t_bind > 0 else 0
    t_dxr = round(t_dx / t_mat, 3) if t_mat > 0 else 0
    t_gtv_rate = float(tot.get("month_sale_gtv_rate", "0%").replace("%",""))/100 if isinstance(tot.get("month_sale_gtv_rate"), str) else 0
    t_month_gtv = round(tot.get("month_sale_gtv", 0))
    new_zr_total = (f"const ZR_TOTAL = {{ stores:{t_shops}, bind:{t_bind}, valid:{t_mat}, dx:{t_dx}, "
                    f"pave_rate:{t_pave}, dx_rate:{t_dxr}, gtv_rate:{t_gtv_rate}, month_gtv:{t_month_gtv} }};")
    html = re.sub(r'const ZR_TOTAL = \{[^}]+\};', new_zr_total, html)

    # 更新 ZR_DATE
    new_zr_date = f"const ZR_DATE  = '{result['date']}';"
    html = re.sub(r"const ZR_DATE\s*= '[^']*';", new_zr_date, html)

    # 更新 ZR_SALES 中的 s[9] (昨日店转GTV) 和 s[10] (昨日店转渗透率)
    # 从BOARD_DATA解析昨日GTV（o[4]=gtv_y）用于计算渗透率
    yday_gtv_map = {}
    bd_match = re.search(r'const BOARD_DATA\s*=\s*\{[^;]+ops:\s*\[([\s\S]*?)\]\s*\}', html)
    if bd_match:
        for m in re.finditer(r"\['([^']+)'[^,]*,\s*'[^']*'[^,]*,\s*[\d.]+,\s*[\d.]+,\s*([\d.]+)", bd_match.group(1)):
            org_name = m.group(1)
            short = org_name.replace('市', '').split('-')[0].strip()
            yday_gtv_map[short] = float(m.group(2))

    # 解析并重写ZR_SALES
    sales_by_org = result.get("sales_by_org", {})
    if sales_by_org:
        def rewrite_sales_row(m):
            # 解析一行ZR_SALES：['代运营商','城市','姓名',月GTV,绑码,门店,铺设,动销,月渗透,s9,s10,...]
            row_str = m.group(0)
            # 提取字段
            parts = re.match(
                r"\s*\['([^']+)','([^']+)','([^']+)',\s*([\d.]+),\s*([\d]+),\s*([\d]+),\s*([\d]+),\s*([\d]+),\s*([\d.]+)(,[\s\S]*?)?\]",
                row_str
            )
            if not parts:
                return row_str
            org, city, sname = parts.group(1), parts.group(2), parts.group(3)
            rest = [parts.group(4), parts.group(5), parts.group(6), parts.group(7), parts.group(8), parts.group(9)]
            # 查销售昨日店转GTV + 最新绑码数
            org_short = org.replace('市', '').split('-')[0].strip()
            sales_list = sales_by_org.get(org_short, [])
            sale_entry = next((s for s in sales_list if s["name"] == sname), None)
            day_gtv = sale_entry["day_sale_gtv"] if sale_entry else None
            # 更新绑码数（col4）
            if sale_entry and sale_entry.get("bind_cnt", 0) > 0:
                rest[1] = str(sale_entry["bind_cnt"])
            # 计算渗透率 = 昨日店转GTV / 代运营商昨日GTV × (销售门店/代运营商门店) 近似
            # 更准确：直接用 昨日店转GTV / BOARD_DATA中代运营商的昨日GTV
            yd_org_gtv = yday_gtv_map.get(org_short, 0)
            if day_gtv is not None and yd_org_gtv > 0:
                # 渗透率：销售昨日店转GTV / 代运营商昨日GTV（按销售维度分母无法精确，用代运营商昨日GTV近似）
                # 实际上渗透率 = 昨日店转GTV / 昨日GTV（此处用代运营商昨日GTV作为分母，不够精准）
                # 更好方案：用sales维度的"昨日GTV"（暂无），先存null等后续完善
                day_rate = None  # 销售维度昨日GTV暂不可知，渗透率先null
            else:
                day_gtv = None
                day_rate = None
            s9 = 'null' if day_gtv is None else str(round(day_gtv, 2))
            s10 = 'null' if day_rate is None else str(round(day_rate, 4))
            # 重建行，保留原始月GTV等字段，只更新s9/s10
            # 找原行中s9/s10位置
            orig_tail = parts.group(10) or ''
            # 原tail格式: ,s9,s10,s11,...
            tail_parts = re.split(r',\s*', orig_tail.lstrip(','))
            # tail_parts[0]=s9, [1]=s10, [2..]=其余
            if len(tail_parts) >= 2:
                new_tail = ', ' + s9 + ', ' + s10 + (''.join(', '+x for x in tail_parts[2:]) if len(tail_parts) > 2 else '')
            else:
                new_tail = ', ' + s9 + ', ' + s10
            return f"  ['{org}','{city}','{sname}', {rest[0]},  {rest[1]},  {rest[2]},  {rest[3]}, {rest[4]}, {rest[5]}{new_tail}]"

        html = re.sub(
            r"\s*\['[^']+','[^']+','[^']+',\s*[\d.]+,\s*[\d]+,\s*[\d]+,\s*[\d]+,\s*[\d]+,\s*[\d.]+[^\]]*\]",
            rewrite_sales_row,
            html
        )
        print(f"  ✓ ZR_SALES 昨日店转GTV已更新（s[9]字段）")

    print(f"  ✓ HTML ZR_LIVE/ZR_TOTAL/ZR_DATE/ZR_RT_FALLBACK/ZR_SALES 已更新")

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  ✓ HTML内嵌数据已更新")

    # 推送GitHub
    content_b64 = base64.b64encode(html.encode('utf-8')).decode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{GH_REPO}/contents/index.html",
        headers={"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        file_info = json.loads(resp.read())
        sha = file_info.get('sha', '')
    except Exception as e:
        print(f"  WARNING: 获取GitHub SHA失败: {e}")
        return

    put_data = json.dumps({
        "message": f"auto: 职人码实时数据更新 {result['update_time']}",
        "content": content_b64,
        "sha": sha
    }).encode('utf-8')
    put_req = urllib.request.Request(
        f"https://api.github.com/repos/{GH_REPO}/contents/index.html",
        data=put_data, method='PUT',
        headers={
            "Authorization": f"token {GH_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github.v3+json"
        }
    )
    try:
        resp = urllib.request.urlopen(put_req, timeout=15)
        commit_info = json.loads(resp.read())
        sha_short = commit_info.get('commit', {}).get('sha', 'unknown')[:8]
        print(f"  ✓ GitHub已推送: {sha_short}")
    except Exception as e:
        print(f"  WARNING: GitHub推送失败: {e}")


if __name__ == '__main__':
    main()
