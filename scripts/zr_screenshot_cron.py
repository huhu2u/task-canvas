from playwright.sync_api import sync_playwright
import time, subprocess
from datetime import datetime

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width":1280,"height":900})
    page.goto("file:///root/.openclaw/workspace/task-canvas.html")
    time.sleep(2)
    page.evaluate("""()=>{const b=Array.from(document.querySelectorAll(".tabn")).find(b=>b.textContent.includes("职人码看板"));if(b)b.click();}""")
    time.sleep(1.5)
    page.screenshot(path="/tmp/zr_screenshot.png", full_page=True)
    browser.close()

dt = datetime.now().strftime("%m-%d")
result = subprocess.run(
    ["openclaw","message","send","--channel","daxiang","--target","3264994429",
     "--media","/tmp/zr_screenshot.png","--message",f"职人码看板 {dt} 🎫"],
    capture_output=True, text=True, timeout=30
)
print(result.stdout)
print(result.stderr)
