// DC 앱 API 방식 로그인 글쓰기 테스트 (green1052/dcinside.js, Bun 실행)
// 대상: 마이너갤 trifoliumdubiumsibth 한 곳만 (마이너갤은 접두어 없이 id 그대로)
// 사람 확인(CaptchaRequiredError)이 나오면 그 자리에서 멈춘다.
import { DCInside, CaptchaRequiredError, OtpRequiredError } from '@green-1052/dcinside.js';
import { randomBytes } from 'node:crypto';

const GALLERY = 'trifoliumdubiumsibth';
const { DC_ID, DC_PW } = process.env;
if (!DC_ID || !DC_PW) { console.error('DC_ID / DC_PW 시크릿이 없습니다.'); process.exit(1); }

const CHOSUNG = 'ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ';
const ALNUM = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
const pick = (s) => s[randomBytes(1)[0] % s.length];
const title = Array.from({ length: 8 }, () => (randomBytes(1)[0] % 4 === 0 ? pick('12') : pick(CHOSUNG))).join('');
const body = Array.from({ length: 10 }, () => pick(ALNUM)).join('');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const errName = (e) => e?.constructor?.name ?? 'Error';

const dc = new DCInside();

// 1) 앱 기기 등록 (구글 GCM 등록이 가끔 실패하므로 간격을 두고 재시도)
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

// 3) 글쓰기
console.log('제목:', title, '/ 본문:', body);
try {
  const res = await dc.articles.write({ gallery: GALLERY, subject: title, content: [body] });
  console.log('응답:', JSON.stringify(res));
  console.log(res?.result === false ? '결과: 글쓰기 거부됨' : '결과: 글쓰기 성공');
  process.exit(res?.result === false ? 4 : 0);
} catch (e) {
  console.error(`결과: 글쓰기 실패 - ${errName(e)} - ${e?.message}`);
  if (e instanceof CaptchaRequiredError) console.error('→ 앱 경로도 사람 확인 요구 (여기서 중단)');
  process.exit(4);
}
