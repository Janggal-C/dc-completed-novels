// 월초 카드뉴스 글쓰기 (디시 앱 API, green1052/dcinside.js, Bun 실행)
// 본문: 결산 카드 5장 → 홍보 카드 → 📊 결산 사이트 링크 → 🧩 줄임말 사전 확장 릴리즈 링크 (사이트.md "게시글 틀")
// 이미지: CARD_DIR 안의 card-1.png … card-5.png, promo.png
// TEST=1 이면 테스트 갤(trifoliumdubiumsibth)에 제목을 한글 초성 난수로 올린다.
// 사람 확인(CaptchaRequiredError)이 나오면 그 자리에서 멈춘다 (우회하지 않음).
import { DCInside, CaptchaRequiredError, OtpRequiredError } from '@green-1052/dcinside.js';
import { randomBytes } from 'node:crypto';
import { readFileSync, appendFileSync } from 'node:fs';

const { DC_ID, DC_PW, CARD_DIR = 'cardnews', MONTH = '', TEST = '1' } = process.env;
if (!DC_ID || !DC_PW) { console.error('DC_ID / DC_PW 시크릿이 없습니다.'); process.exit(1); }
const isTest = TEST !== '0';
const GALLERY = isTest ? 'trifoliumdubiumsibth' : 'genrenovel';

const CHOSUNG = 'ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ';
const pick = (s) => s[randomBytes(1)[0] % s.length];
const monthNum = Number(MONTH.split('-')[1] || 0);
const title = isTest ? Array.from({ length: 8 }, () => pick(CHOSUNG)).join('') : `장갤 ${monthNum}월 결산) 언급 TOP 10`;

const SITE = 'https://janggal-c.github.io/dc-completed-novels/';
const RELEASE = 'https://github.com/Janggal-C/dc-completed-novels/releases/latest';
const img = (f) => ({ type: 'image', file: new Blob([readFileSync(`${CARD_DIR}/${f}`)], { type: 'image/png' }) });
const link = (label, url) => ({ type: 'html', html: `<div>${label}</div><div><a href="${url}" target="_blank">${url}</a></div>` });
const content = [
  ...[1, 2, 3, 4, 5].map((i) => img(`card-${i}.png`)),
  img('promo.png'),
  link('📊 결산 사이트', SITE),
  link('🧩 줄임말 사전 확장', RELEASE),
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const errName = (e) => e?.constructor?.name ?? 'Error';
const dc = new DCInside();

// 1) 앱 기기 등록 (GCM 등록이 가끔 실패해서 간격을 두고 재시도)
let ok = false;
for (const [i, wait] of [0, 5000, 15000, 30000, 60000].entries()) {
  if (wait) { console.log(`기기 등록 재시도 대기 ${wait / 1000}초`); await sleep(wait); }
  try { await dc.auth.appId(); ok = true; console.log(`기기 등록 성공 (시도 ${i + 1})`); break; }
  catch (e) { console.log(`기기 등록 실패 (시도 ${i + 1}): ${errName(e)} - ${e?.message}`); }
}
if (!ok) { console.error('결과: 기기 등록 단계에서 실패'); process.exit(2); }

// 2) 로그인
try { await dc.login(DC_ID, DC_PW); console.log('로그인 성공'); }
catch (e) {
  console.error(`결과: 로그인 실패 - ${errName(e)} - ${e?.message}`);
  if (e instanceof OtpRequiredError) console.error('→ OTP 필요');
  if (e instanceof CaptchaRequiredError) console.error('→ 로그인에 사람 확인 필요 (여기서 중단)');
  process.exit(3);
}

// 3) 글쓰기 (새 기기 직후는 "잠시후 다시"가 나오므로 기다렸다가, 최대 3번)
console.log(`갤러리: ${GALLERY} / 제목: ${title} / 블록 ${content.length}개`);
for (const [i, wait] of [30000, 90000, 180000].entries()) {
  console.log(`글쓰기 전 대기 ${wait / 1000}초`);
  await sleep(wait);
  try {
    const res = await dc.articles.write({ gallery: GALLERY, subject: title, content });
    console.log('응답:', JSON.stringify(res));
    const no = res?.cause ?? res?.no ?? '';
    console.log(`결과: 글쓰기 성공 ${no}`);
    if (process.env.GITHUB_OUTPUT) appendFileSync(process.env.GITHUB_OUTPUT, `post_no=${no}\ngallery=${GALLERY}\n`);
    process.exit(0);
  } catch (e) {
    console.error(`글쓰기 실패 (시도 ${i + 1}) - ${errName(e)} - ${e?.message}`);
    console.error('원본 응답:', JSON.stringify(e?.response ?? null));
    if (e instanceof CaptchaRequiredError) { console.error('결과: 사람 확인 요구 (여기서 중단)'); process.exit(5); }
    if (!/잠시/.test(e?.message ?? '')) { console.error('결과: 글쓰기 거부됨'); process.exit(4); }
  }
}
console.error('결과: 계속 "잠시후 다시" 응답');
process.exit(4);
