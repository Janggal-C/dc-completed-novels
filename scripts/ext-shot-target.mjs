// 확장 캡처 (지정한 글 제목만): 장르소설갤 목록 1~5쪽에서 TARGETS 제목을 찾아 줄임말 팝업을 커서 없이 찍고,
// 줄임말 위치(캡처 기준 좌표)를 json으로 남긴다. 포인터는 나중에 원하는 크기·위치로 합성한다. (읽기만)
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const ext = path.resolve('extension');
const out = path.resolve('shots');
mkdirSync(out, { recursive: true });
const targets = (process.env.TARGETS || '').split('|').map((s) => s.trim()).filter(Boolean);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const ctx = await chromium.launchPersistentContext('/tmp/pw-profile', {
  headless: false, viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2, locale: 'ko-KR',
  args: [`--disable-extensions-except=${ext}`, `--load-extension=${ext}`],
});
const page = ctx.pages()[0] ?? (await ctx.newPage());
const meta = [];
const left = new Set(targets);
for (let p = 1; p <= 5 && left.size; p++) {
  await page.goto(`https://gall.dcinside.com/mgallery/board/lists/?id=genrenovel&page=${p}`, { waitUntil: 'domcontentloaded' });
  await sleep(4000);
  for (const t of [...left]) {
    const td = page.locator('td.gall_tit', { hasText: t }).first();
    if (!(await td.count())) continue;
    const el = td.locator('.dcnx').first();
    if (!(await el.count())) { console.log(`줄임말 없음: ${t}`); left.delete(t); continue; }
    await el.scrollIntoViewIfNeeded(); await sleep(300);
    await page.mouse.move(0, 0); await sleep(400);
    await el.hover(); await sleep(700);
    const tip = page.locator('.dcnx-tip');
    if (!(await tip.isVisible())) continue;
    await page.mouse.move(1270, 5); // 커서 치우기 (팝업은 300ms 뒤 닫히므로 바로 찍음)
    const a = await td.boundingBox(), b = await tip.boundingBox(), e = await el.boundingBox();
    const x = Math.max(0, Math.min(a.x, b.x) - 12), y = Math.max(0, Math.min(a.y, b.y) - 8);
    const w = Math.max(a.x + a.width, b.x + b.width) - x + 12, h = Math.max(a.y + a.height, b.y + b.height) - y + 30;
    const i = meta.length + 1;
    await page.screenshot({ path: `${out}/target-${i}.png`, clip: { x, y, width: w, height: h } });
    const shown = await tip.isVisible();
    meta.push({ file: `target-${i}.png`, title: t, word: await el.innerText(), tipVisible: shown,
      scale: 2, wordBox: { x: e.x - x, y: e.y - y, w: e.width, h: e.height }, tipBox: { x: b.x - x, y: b.y - y, w: b.width, h: b.height } });
    console.log(`찾음 p${p}: ${t} (팝업 보임: ${shown})`);
    left.delete(t);
  }
}
writeFileSync(`${out}/targets.json`, JSON.stringify(meta, null, 1));
console.log('못 찾음:', [...left].join(' / ') || '없음');
await ctx.close();
