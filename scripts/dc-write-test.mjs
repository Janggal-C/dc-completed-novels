// DC 로그인 글쓰기 테스트 (GitHub Actions 전용)
// 대상 갤러리: trifoliumdubiumsibth (마이너갤) — 이 갤러리 외에는 쓰지 않음
import * as dcModule from '@gurumnyang/dcinside.js';
import { randomBytes } from 'node:crypto';

const dc = dcModule.default ?? dcModule;
const GALLERY_ID = 'trifoliumdubiumsibth';
const { DC_ID, DC_PW } = process.env;

if (!DC_ID || !DC_PW) {
  console.error('DC_ID / DC_PW 시크릿이 없습니다.');
  process.exit(1);
}

// 제목: 초성 + 숫자(1, 2만) 조합, 예: ㅁㄴㅂ2ㅈㄱ1ㄹ
const CHOSUNG = 'ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ';
const pick = (s) => s[randomBytes(1)[0] % s.length];
function makeTitle(len = 8) {
  return Array.from({ length: len }, () => (randomBytes(1)[0] % 4 === 0 ? pick('12') : pick(CHOSUNG))).join('');
}
// 본문: 랜덤 영문+숫자 10글자
const ALNUM = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
const makeBody = () => Array.from({ length: 10 }, () => pick(ALNUM)).join('');

// 라이브러리 export 목록 출력 (함수명 확인용)
const names = Object.keys(dc).filter((k) => typeof dc[k] === 'function');
console.log('exports:', names.join(', '));

const login = await dc.mobileLogin({ code: DC_ID, password: DC_PW });
if (!login?.success) {
  console.error('로그인 실패:', login?.reason ?? '(사유 없음)', '— 캡차 가능성');
  process.exit(2);
}
console.log('로그인 성공');

const subject = makeTitle();
const content = makeBody();
console.log('제목:', subject, '/ 본문:', content);

const res = await dc.createPost({ galleryId: GALLERY_ID, subject, content, jar: login.jar });
console.log('write result:', JSON.stringify({ ...res, jar: undefined }));
if (!res?.success) {
  console.error('글쓰기 실패:', res?.message ?? '(사유 없음)', '— 캡차/IP 제한 가능성');
  process.exit(3);
}
console.log('성공! 글번호:', res.postId, 'URL:', res.redirectUrl);
