// 배포된 사이트(github.io) 실제 화면 캡처 + 요약 (읽기만). Claude 세션에서는 github.io가 막혀서 Actions에서 대신 찍는다.
// 결과: shots/site-<탭>.png, shots/site.txt (탭마다 갱신 시각·표 줄 수·링크 수·앞부분 글자)
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const SITE = process.env.SITE || 'https://janggal-c.github.io/dc-completed-novels/';
const TABS = ['mentions', 'complete', 'trend', 'dict', 'check', 'metrics'];
const out = path.resolve('shots');
mkdirSync(out, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch();
const lines = [];
for (const [label, vp] of [['pc', { width: 1280, height: 900 }], ['m', { width: 390, height: 844 }]]) {
  const page = await browser.newPage({ viewport: vp, deviceScaleFactor: 1, locale: 'ko-KR' });
  const errs = [];
  page.on('pageerror', (e) => errs.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  for (const t of (label === 'pc' ? TABS : ['mentions', 'complete'])) {
    // 캐시를 피하려고 매번 새 주소
    await page.goto(`${SITE}?t=${Date.now()}#${t}`, { waitUntil: 'networkidle' });
    await sleep(1500);
    const info = await page.evaluate(() => {
      const v = document.getElementById('view');
      const txt = (v?.innerText || '').replace(/\s+/g, ' ');
      return {
        rows: v ? v.querySelectorAll('tr').length : -1,
        links: v ? v.querySelectorAll('a[href^="https"]').length : -1,
        head: txt.slice(0, 400),
      };
    });
    lines.push(`[${label}:${t}] 표 줄 ${info.rows} · 링크 ${info.links}\n  ${info.head}`);
    await page.screenshot({ path: `${out}/site-${label}-${t}.png`, fullPage: false });
  }
  if (errs.length) lines.push(`[${label}] 페이지 오류 ${errs.length}건: ${errs.slice(0, 5).join(' | ')}`);
  await page.close();
}
// 배포된 데이터 갱신 시각
for (const f of ['data/report.json', 'data/mentions.json']) {
  try {
    const r = await fetch(`${SITE}${f}?t=${Date.now()}`);
    const j = await r.json();
    lines.push(`${f}: ${r.status} · updated=${j.updated ?? ''} generated=${j.generated ?? ''}`);
  } catch (e) { lines.push(`${f}: 읽기 실패 ${e}`); }
}
await browser.close();
writeFileSync(`${out}/site.txt`, lines.join('\n') + '\n');
console.log(lines.join('\n'));
