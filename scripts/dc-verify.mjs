// 글 확인: 테스트 갤러리 글 하나를 앱 API로 읽어 제목/작성자/본문 출력
import { DCInside } from '@green-1052/dcinside.js';
const no = Number(process.env.POST_NO);
const dc = new DCInside();
const v = await dc.articles.read('trifoliumdubiumsibth', no);
const s = JSON.stringify(v);
console.log('읽기 결과(앞부분):', s.slice(0, 1500));
