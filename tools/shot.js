// Minimal headless-Chromium REPL-ish driver: nav -> wait -> screenshot -> console errors.
// Usage: node shot.js <url> <out.png> [waitMs]
const { chromium } = require('playwright');

(async () => {
  const [, , url, out, waitMs] = process.argv;
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const errors = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('pageerror', err => errors.push(String(err)));
  await page.goto(url, { waitUntil: 'networkidle' });
  if (waitMs) await page.waitForTimeout(parseInt(waitMs, 10));
  await page.screenshot({ path: out });
  await browser.close();
  console.log('screenshot ->', out);
  if (errors.length) {
    console.log('console errors:');
    errors.forEach(e => console.log(' ', e));
  } else {
    console.log('no console errors');
  }
})();
