// 글 확인: 갤러리 글 하나를 앱 API로 읽어 제목/작성자/본문 출력 (로그인 불필요)
import { DCInside } from '@green-1052/dcinside.js';
const gallery = process.env.GALLERY || 'trifoliumdubiumsibth';
const no = Number(process.env.POST_NO);
const dc = new DCInside();
const v = await dc.articles.read(gallery, no);
console.log('읽기 결과:', JSON.stringify(v).slice(0, 6000));
