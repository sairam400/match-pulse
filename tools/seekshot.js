// Navigate, call window.__seekTo(ms) to fast-forward trigger state, then screenshot.
// Usage: node seekshot.js <url> <ms> <out.png>
const { chromium } = require('playwright');

(async () => {
  const [, , url, ms, out] = process.argv;
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const errors = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('pageerror', err => errors.push(String(err)));
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => typeof window.__seekTo === 'function');
  await page.evaluate((m) => window.__seekTo(m), parseInt(ms, 10));
  await page.screenshot({ path: out });
  await browser.close();
  console.log('screenshot ->', out, 'at ms=', ms);
  if (errors.length) { console.log('console errors:'); errors.forEach(e => console.log(' ', e)); }
  else console.log('no console errors');
})();
