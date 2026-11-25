// DC 앱 API 방식 로그인 글쓰기 테스트 (green1052/dcinside.js, Bun 실행)
// 대상: 마이너갤 trifoliumdubiumsibth 한 곳만
import * as mod from '@green-1052/dcinside.js';
import { randomBytes } from 'node:crypto';

const { DC_ID, DC_PW } = process.env;
if (!DC_ID || !DC_PW) {
  console.error('DC_ID / DC_PW 시크릿이 없습니다.');
  process.exit(1);
}

const CHOSUNG = 'ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ';
const ALNUM = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
const pick = (s) => s[randomBytes(1)[0] % s.length];
const title = Array.from({ length: 8 }, () => (randomBytes(1)[0] % 4 === 0 ? pick('12') : pick(CHOSUNG))).join('');
const body = Array.from({ length: 10 }, () => pick(ALNUM)).join('');

console.log('exports:', Object.keys(mod).join(', '));
const Ctor = mod.DCInside ?? mod.DCInsideClient ?? mod.default;
const dc = new Ctor();

try {
  await dc.login(DC_ID, DC_PW);
  console.log('로그인 성공');
  console.log('제목:', title, '/ 본문:', body);
  const res = await dc.articles.write({
    gallery: 'mi$trifoliumdubiumsibth',
    subject: title,
    content: [body],
  });
  console.log('성공! 결과:', JSON.stringify(res));
} catch (e) {
  const name = e?.constructor?.name ?? 'Error';
  console.error(`실패: ${name} - ${e?.message ?? e}`);
  if (name === 'CaptchaRequiredError') console.error('→ 캡차 필요: 무인 자동화 불가');
  if (name === 'OtpRequiredError') console.error('→ OTP 필요');
  process.exit(name === 'CaptchaRequiredError' ? 3 : 2);
}
