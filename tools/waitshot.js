// Navigate and screenshot after waiting, without clicking anything.
// Usage: node waitshot.js <url> <waitMs> <out.png>
const { chromium } = require('playwright');

(async () => {
  const [, , url, waitMs, out] = process.argv;
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const errors = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('pageerror', err => errors.push(String(err)));
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForTimeout(parseInt(waitMs, 10));
  await page.screenshot({ path: out });
  const btnVisible = await page.locator('#playBtn').isVisible().catch(() => false);
  await browser.close();
  console.log('screenshot ->', out, 'after', waitMs, 'ms; playBtn visible:', btnVisible);
  if (errors.length) { console.log('console errors:'); errors.forEach(e => console.log(' ', e)); }
  else console.log('no console errors');
})();
