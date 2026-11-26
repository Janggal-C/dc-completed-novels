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

// 마우스 포인터 그림 (스크린샷에는 실제 커서가 안 찍혀서 화살표 모양을 그 자리에 얹는다)
const CURSOR = `<svg xmlns="http://www.w3.org/2000/svg" width="22" height="32" viewBox="0 0 22 32"><path d="M1 1 L1 25 L7 19.5 L11.5 30 L15.5 28.2 L11 18 L19.5 18 Z" fill="#fff" stroke="#000" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
let shot = 0;
const seen = new Set();
for (let i = 0; i < n && shot < 15; i++) {
  const el = spans.nth(i);
  if (!(await el.isVisible())) continue;
  const word = await el.innerText();
  if (seen.has(word)) continue;
  await el.scrollIntoViewIfNeeded();
  await sleep(300);
  await page.mouse.move(0, 0);
  await sleep(400);
  const eb = await el.boundingBox();
  if (!eb) continue;
  const mx = eb.x + eb.width * 0.6, my = eb.y + eb.height * 0.55;
  await page.mouse.move(mx, my);
  await sleep(700);
  const tip = page.locator('.dcnx-tip');
  if (!(await tip.isVisible())) continue;
  seen.add(word);
  await page.evaluate(([x, y, svg]) => {
    document.getElementById('pw-cursor')?.remove();
    const c = document.createElement('div');
    c.id = 'pw-cursor';
    c.innerHTML = svg;
    Object.assign(c.style, { position: 'fixed', left: x + 'px', top: y + 'px', zIndex: 2147483647, pointerEvents: 'none' });
    document.documentElement.appendChild(c);
  }, [mx, my, CURSOR]);
  const td = el.locator('xpath=ancestor::td[1]');
  const a = await td.boundingBox(), b = await tip.boundingBox();
  if (!a || !b) continue;
  const x = Math.max(0, Math.min(a.x, b.x) - 12), y = Math.max(0, Math.min(a.y, b.y) - 8);
  const w = Math.min(1280 - x, Math.max(a.x + a.width, b.x + b.width, mx + 24) - x + 12);
  const h = Math.max(a.y + a.height, b.y + b.height, my + 34) - y + 10;
  const text = (await tip.innerText()).replace(/\s+/g, ' ');
  const title = (await td.innerText()).replace(/\s+/g, ' ');
  await page.screenshot({ path: `${out}/tip-${++shot}.png`, clip: { x, y, width: w, height: h } });
  console.log(`캡처 ${shot}: [${word}] 글제목="${title}" → ${text}`);
}
console.log('캡처 수:', shot);

// 모바일 목록(m.dcinside.com): 밑줄·팝업이 붙는지 확인 (2026-11-25 "목록에서 팝업이 안 뜬다" 신고 점검용)
const mp = await ctx.newPage();
await mp.setViewportSize({ width: 412, height: 900 });
await mp.setExtraHTTPHeaders({ 'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36' });
await mp.goto('https://m.dcinside.com/board/genrenovel', { waitUntil: 'domcontentloaded' });
await sleep(5000);
const rows = await mp.locator('.gall-detail-lnktb .subjectin').count();
const mspans = mp.locator('.gall-detail-lnktb .dcnx');
const mn = await mspans.count();
console.log(`모바일 목록: 제목 ${rows}개, 밑줄 줄임말 수: ${mn}`);
let mshot = 0;
for (let i = 0; i < mn && mshot < 3; i++) {
  const el = mspans.nth(i);
  if (!(await el.isVisible())) continue;
  await el.scrollIntoViewIfNeeded();
  await mp.mouse.move(0, 0);
  await sleep(300);
  const eb = await el.boundingBox();
  if (!eb) continue;
  await mp.mouse.move(eb.x + eb.width * 0.6, eb.y + eb.height * 0.55);
  await sleep(700);
  const tip = mp.locator('.dcnx-tip');
  if (!(await tip.isVisible())) continue;
  const text = (await tip.innerText()).replace(/\s+/g, ' ');
  await mp.screenshot({ path: `${out}/m-tip-${++mshot}.png` });
  console.log(`모바일 캡처 ${mshot}: [${await el.innerText()}] → ${text}`);
}
console.log('모바일 팝업 수:', mshot);
await ctx.close();
