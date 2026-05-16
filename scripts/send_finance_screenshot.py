#!/usr/bin/env python3
"""
每天09:30 截取 task-canvas 财收看板 并发给英杰私聊
"""
import subprocess, sys, time, os, json
from pathlib import Path

DAXIANG_UID = "3264994429"
CANVAS_URL  = "https://huhu2u.github.io/task-canvas/"
OUT_IMG     = f"/tmp/finance_shot_{int(time.time())}.png"
SESSION     = "finance-tab"  # agent-browser session名

def send_via_gateway(media_path, message):
    """通过openclaw gateway HTTP API发送消息（避免CLI版本不兼容）"""
    import base64, mimetypes
    # 读取配置获取gateway端口
    config_paths = [
        "/root/.openclaw/openclaw.json",
    ]
    gateway_port = 18789  # 默认端口
    
    # 读取图片为base64
    with open(media_path, "rb") as f:
        img_data = f.read()
    img_b64 = base64.b64encode(img_data).decode()
    mime = mimetypes.guess_type(media_path)[0] or "image/png"
    
    # 构造请求
    import urllib.request, urllib.error
    payload = json.dumps({
        "channel": "daxiang",
        "target": DAXIANG_UID,
        "message": message,
        "media": f"data:{mime};base64,{img_b64}"
    }).encode("utf-8")
    
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{gateway_port}/api/message/send",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            print(f"发送成功: {result}")
            return True
    except Exception as e:
        print(f"gateway发送失败: {e}")
        return False

def main():
    # 1. 先跑 fetch_finance_data.py 更新数据
    script = Path(__file__).parent / "fetch_finance_data.py"
    print("=== 更新财收数据 ===")
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    print(r.stdout[-800:] if r.stdout else "")
    if r.returncode != 0:
        print("⚠️ fetch_finance_data 失败:", r.stderr[-300:])
        # 继续截图，用旧数据

    # 2. 打开 task-canvas 财收看板
    print("=== 打开 task-canvas ===")
    r = subprocess.run(["agent-browser", "--session", SESSION, "navigate", CANVAS_URL],
                       capture_output=True, text=True, timeout=30)
    print(r.stdout.strip() or r.stderr.strip())
    time.sleep(4)

    # 3. 点财收看板 Tab（按文字匹配，不依赖 ID）
    print("=== 切换到财收看板Tab ===")
    result = subprocess.run(["agent-browser", "--session", SESSION, "eval", """
        const tabs = [...document.querySelectorAll('[data-tab], .tab-btn, button, [role=tab]')];
        const t = tabs.find(el => el.textContent.includes('财收'));
        if(t){ t.click(); '点击:'+t.textContent.trim(); }
        else { '未找到财收tab, 可用:'+tabs.map(e=>e.textContent.trim().substring(0,12)).join('|'); }
    """], capture_output=True, text=True, timeout=15)
    print(result.stdout.strip())
    time.sleep(2)

    # 4. 截图
    print(f"=== 截图 → {OUT_IMG} ===")
    r = subprocess.run(["agent-browser", "--session", SESSION, "screenshot", OUT_IMG],
                       capture_output=True, text=True)
    if r.returncode != 0 or not Path(OUT_IMG).exists():
        print("截图失败:", r.stderr)
        sys.exit(1)
    print(f"截图OK: {Path(OUT_IMG).stat().st_size} bytes")

    # 5. 发送（优先gateway API，失败则写pending文件等主agent处理）
    print(f"=== 发送给 {DAXIANG_UID} ===")
    msg = "📊 今日财收看板（单位：万元）"
    
    ok = send_via_gateway(OUT_IMG, msg)
    if not ok:
        # 写pending文件，等主agent处理
        pending = {
            "channel": "daxiang",
            "target": DAXIANG_UID,
            "media": OUT_IMG,
            "message": msg,
            "ts": int(time.time())
        }
        pending_file = "/tmp/pending_finance_send.json"
        with open(pending_file, "w") as f:
            json.dump(pending, f)
        print(f"⚠️ gateway发送失败，写入pending: {pending_file}")
        print(f"   图片路径: {OUT_IMG}")
    
    print("✅ 完成")

if __name__ == "__main__":
    main()
