// Click the play button, wait, screenshot mid real-time playback.
const { chromium } = require('playwright');

(async () => {
  const [, , url, waitMs, out] = process.argv;
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const errors = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('pageerror', err => errors.push(String(err)));
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.click('#playBtn');
  await page.waitForTimeout(parseInt(waitMs, 10));
  await page.screenshot({ path: out });
  await browser.close();
  console.log('screenshot ->', out, 'after real playback for', waitMs, 'ms');
  if (errors.length) { console.log('console errors:'); errors.forEach(e => console.log(' ', e)); }
  else console.log('no console errors');
})();
