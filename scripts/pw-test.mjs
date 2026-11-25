// Playwright(실제 크롬) 테스트: 디시 로그인 글쓰기 1건 + 구글 검색 몇 건
// 대상 갤러리: trifoliumdubiumsibth 한 곳만
import { chromium } from 'playwright';
import { randomBytes } from 'node:crypto';

const GALLERY = 'trifoliumdubiumsibth';
const { DC_ID, DC_PW } = process.env;
const CHOSUNG = 'ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ';
const ALNUM = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
const pick = (s) => s[randomBytes(1)[0] % s.length];
const TITLE = Array.from({ length: 8 }, () => (randomBytes(1)[0] % 4 === 0 ? pick('12') : pick(CHOSUNG))).join('');
const BODY = Array.from({ length: 10 }, () => pick(ALNUM)).join('');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({
  locale: 'ko-KR',
  viewport: { width: 412, height: 915 },
  isMobile: true,
  hasTouch: true,
  userAgent:
    'Mozilla/5.0 (Linux; Android 14; SM-S921N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36',
});
const page = await ctx.newPage();
const dialogs = [];
page.on('dialog', async (d) => { dialogs.push(d.message()); console.log('[알림창]', d.message()); await d.accept(); });

async function dumpForm(label) {
  const info = await page.evaluate(() =>
    [...document.querySelectorAll('input,textarea,button,[contenteditable="true"]')]
      .filter((e) => e.offsetParent !== null)
      .slice(0, 40)
      .map((e) => `${e.tagName.toLowerCase()} type=${e.type || ''} id=${e.id} name=${e.name || ''} text=${(e.innerText || e.value || '').slice(0, 20).replace(/\s+/g, ' ')}`));
  console.log(`--- ${label} (${page.url()}) ---\n` + info.join('\n'));
}

let writeOk = false;
try {
  // 1) 로그인
  await page.goto(`https://m.dcinside.com/auth/login?r_url=${encodeURIComponent('https://m.dcinside.com/board/' + GALLERY)}`, { waitUntil: 'domcontentloaded' });
  await sleep(1500);
  const pw = page.locator('input[type="password"]:visible').first();
  if (!(await pw.count())) { await dumpForm('로그인 페이지'); throw new Error('비밀번호 칸을 못 찾음'); }
  const idBox = page.locator('input[type="text"]:visible, input[type="email"]:visible, input:not([type]):visible').first();
  await idBox.fill(DC_ID);
  await pw.fill(DC_PW);
  await Promise.all([page.waitForLoadState('domcontentloaded').catch(() => {}), pw.press('Enter')]);
  await sleep(3000);
  console.log('로그인 후 URL:', page.url());
  if (/auth\/login/.test(page.url())) { await dumpForm('로그인 실패 화면'); throw new Error('로그인 페이지에 머묾'); }
  console.log('로그인 성공');

  // 2) 글쓰기
  await page.goto(`https://m.dcinside.com/write/${GALLERY}`, { waitUntil: 'domcontentloaded' });
  await sleep(2500);
  const subj = page.locator('input[name="subject"]:visible, #subject:visible, input[placeholder*="제목"]:visible').first();
  if (!(await subj.count())) { await dumpForm('글쓰기 페이지'); throw new Error('제목 칸을 못 찾음'); }
  await subj.click();
  await subj.type(TITLE, { delay: 80 });
  let body = page.locator('textarea:visible').first();
  if (!(await body.count())) body = page.locator('[contenteditable="true"]:visible').first();
  if (!(await body.count())) { await dumpForm('글쓰기 페이지(본문)'); throw new Error('본문 칸을 못 찾음'); }
  await body.click();
  await page.keyboard.type(BODY, { delay: 80 });
  console.log('입력:', TITLE, '/', BODY);
  await sleep(2000);

  const submit = page.locator('button:visible, a:visible, input[type="submit"]:visible').filter({ hasText: /^\s*(등록|작성|완료)\s*$/ }).first();
  if (!(await submit.count())) { await dumpForm('등록 버튼 탐색'); throw new Error('등록 버튼을 못 찾음'); }
  for (let i = 1; i <= 3; i++) {
    await submit.click();
    await sleep(4000);
    const url = page.url();
    console.log(`등록 시도 ${i} 후 URL:`, url);
    if (new RegExp(`/board/${GALLERY}/\\d+`).test(url)) { writeOk = true; console.log('글쓰기 성공:', url); break; }
    if (!/보안 확인/.test(dialogs.at(-1) ?? '')) break;
  }
  if (!writeOk) await dumpForm('등록 후 화면');
} catch (e) {
  console.error('디시 단계 오류:', e.message);
}

// 3) 구글 검색 테스트
const queries = ['전독시 웹소설', '화산귀환 웹소설', '나혼렙 웹소설'];
let googleBlocked = false;
for (const q of queries) {
  await page.goto(`https://www.google.com/search?q=${encodeURIComponent(q)}&hl=ko`, { waitUntil: 'domcontentloaded' });
  await sleep(2500);
  if (/\/sorry\//.test(page.url()) || (await page.locator('#captcha-form, iframe[src*="recaptcha"]').count())) {
    console.log(`[구글] "${q}" → 로봇 확인 화면 (차단)`); googleBlocked = true; break;
  }
  const titles = await page.locator('h3').allInnerTexts();
  console.log(`[구글] "${q}" → ${titles.slice(0, 3).join(' | ') || '(결과 제목 없음)'}`);
  await sleep(4000);
}

await browser.close();
console.log(`\n===== 요약 =====\n디시 글쓰기: ${writeOk ? '성공' : '실패'}\n구글 검색: ${googleBlocked ? '로봇 확인으로 막힘' : '정상'}`);
process.exit(writeOk ? 0 : 3);
