#!/usr/bin/env python3
"""
每天09:00 截取 task-canvas 职人码看板（代运营商维度）并发给英杰私聊
裁剪参数：全页截图后裁 (15, 130, 1265, 660) — 含标题卡片+代运营商汇总表（6行+合计）
"""
import subprocess, sys, time, json
from pathlib import Path
from PIL import Image

DAXIANG_UID = "3264994429"
CANVAS_URL  = "https://huhu2u.github.io/task-canvas/"
SESSION     = "finance-tab"
FULL_IMG    = f"/tmp/zhirenma_full_{int(time.time())}.png"
OUT_IMG     = f"/tmp/zhirenma_org_{int(time.time())}.png"

def run(cmd, timeout=30):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip(), r.returncode

def main():
    # 1. 确保页面已打开（复用 finance-tab session）
    print("=== 切换到职人码看板Tab ===")
    run(["agent-browser", "--session", SESSION, "navigate", CANVAS_URL], timeout=30)
    time.sleep(4)

    out, _ = run(["agent-browser", "--session", SESSION, "eval",
        "(function(){ const tabs=[...document.querySelectorAll('[data-tab],.tab-btn,button,[role=tab]')];"
        " const t=tabs.find(el=>el.textContent.includes('职人码'));"
        " if(t){t.click();return '点击:'+t.textContent.trim();} return '未找到'; })()"])
    print(out)
    time.sleep(2)

    # 2. 全页截图
    print(f"=== 全页截图 → {FULL_IMG} ===")
    _, code = run(["agent-browser", "--session", SESSION, "screenshot", "--full", FULL_IMG], timeout=30)
    if code != 0 or not Path(FULL_IMG).exists():
        print("全页截图失败")
        sys.exit(1)
    print(f"全页截图OK: {Path(FULL_IMG).stat().st_size} bytes")

    # 3. 裁剪：只保留标题+代运营商汇总表（含6行+合计行）
    # 参数：left=15, top=130, right=1265, bottom=660（2026-04-06英杰确认）
    print(f"=== 裁剪 → {OUT_IMG} ===")
    img = Image.open(FULL_IMG)
    crop = img.crop((15, 130, 1265, 660))
    crop.save(OUT_IMG)
    print(f"裁剪OK: {crop.size}, {Path(OUT_IMG).stat().st_size} bytes")

    # 4. 发送
    print(f"=== 发送给 {DAXIANG_UID} ===")
    import urllib.request, base64, mimetypes
    with open(OUT_IMG, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    payload = json.dumps({
        "channel": "daxiang",
        "target": DAXIANG_UID,
        "media": f"data:image/png;base64,{img_b64}"
    }).encode()
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:18789/api/message/send",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"发送成功: {json.loads(resp.read())}")
    except Exception as e:
        # 写pending，由主agent处理
        pending = {"channel": "daxiang", "target": DAXIANG_UID,
                   "media": OUT_IMG, "message": "", "ts": int(time.time())}
        Path("/tmp/pending_zhirenma_send.json").write_text(json.dumps(pending))
        print(f"gateway失败({e})，写pending: /tmp/pending_zhirenma_send.json")

    print("✅ 完成")

if __name__ == "__main__":
    main()
