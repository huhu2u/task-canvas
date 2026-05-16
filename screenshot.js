const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto('file:///root/.openclaw/workspace/yueminzhe_dashboard.html', { waitUntil: 'networkidle0' });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: '/root/.openclaw/workspace/yueminzhe_dashboard.png', fullPage: true });
  await browser.close();
  console.log('Screenshot saved to yueminzhe_dashboard.png');
})();
