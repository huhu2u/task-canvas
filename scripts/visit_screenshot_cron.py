from playwright.sync_api import sync_playwright
import time, subprocess
from datetime import datetime

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width":1280,"height":800})
    page.goto("file:///root/.openclaw/workspace/task-canvas.html")
    time.sleep(2)
    page.evaluate("""()=>{const b=Array.from(document.querySelectorAll(".tabn")).find(b=>b.textContent.includes("拜访统计"));if(b)b.click();}""")
    time.sleep(1.5)
    page.screenshot(path="/tmp/visit_screenshot.png", full_page=True)
    browser.close()

dt = datetime.now().strftime("%m-%d")
result = subprocess.run(
    ["openclaw","message","send","--channel","daxiang","--target","3264994429",
     "--media","/tmp/visit_screenshot.png","--message",f"拜访统计早报 {dt} 📊"],
    capture_output=True, text=True, timeout=30
)
print(result.stdout)
print(result.stderr)
