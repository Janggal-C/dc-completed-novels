// 확장 실제 화면 캡처: 장르소설갤 목록에 확장을 켠 크롬을 띄워 줄임말 팝업을 찍는다 (읽기만)
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import path from 'node:path';

const ext = path.resolve('extension');
const out = path.resolve('shots');
mkdirSync(out, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const ctx = await chromium.launchPersistentContext('/tmp/pw-profile', {
  headless: false,
  viewport: { width: 1280, height: 900 },
  deviceScaleFactor: 2,
  locale: 'ko-KR',
  args: [`--disable-extensions-except=${ext}`, `--load-extension=${ext}`],
});
const page = ctx.pages()[0] ?? (await ctx.newPage());
await page.goto('https://gall.dcinside.com/mgallery/board/lists/?id=genrenovel', { waitUntil: 'domcontentloaded' });
await sleep(5000);
const spans = page.locator('td.gall_tit .dcnx');
const n = await spans.count();
console.log('밑줄 줄임말 수:', n);

let shot = 0;
for (let i = 0; i < n && shot < 6; i++) {
  const el = spans.nth(i);
  if (!(await el.isVisible())) continue;
  await el.scrollIntoViewIfNeeded();
  await sleep(300);
  await page.mouse.move(0, 0);
  await sleep(400);
  await el.hover();
  await sleep(700);
  const tip = page.locator('.dcnx-tip');
  if (!(await tip.isVisible())) continue;
  const row = el.locator('xpath=ancestor::tr[1]');
  const a = await row.boundingBox(), b = await tip.boundingBox();
  if (!a || !b) continue;
  const x = Math.max(0, Math.min(a.x, b.x) - 10), y = Math.max(0, Math.min(a.y, b.y) - 10);
  const w = Math.min(1280 - x, Math.max(a.x + a.width, b.x + b.width) - x + 10);
  const h = Math.max(a.y + a.height, b.y + b.height) - y + 10;
  const text = (await tip.innerText()).replace(/\s+/g, ' ');
  await page.screenshot({ path: `${out}/tip-${++shot}.png`, clip: { x, y, width: w, height: h } });
  await page.screenshot({ path: `${out}/view-${shot}.png` });
  console.log(`캡처 ${shot}: "${await el.innerText()}" → ${text}`);
}
await ctx.close();
console.log('캡처 수:', shot);
