// 연재처 아이콘: 내장된 각 사이트 파비콘 (icons/*.png). 파일이 없으면 글자 아이콘으로 대체
const DCNX_PLATFORMS = {
  novelpia: {name: "노벨피아", ch: "노", bg: "#6A4CF0", fg: "#fff", re: /노벨피아/},
  naver:    {name: "네이버",   ch: "네", bg: "#03C75A", fg: "#fff", re: /네이버|시리즈/},
  kakao:    {name: "카카오",   ch: "카", bg: "#FEE500", fg: "#191919", re: /카카오/},
  munpia:   {name: "문피아",   ch: "문", bg: "#E8532D", fg: "#fff", re: /문피아/},
  ridi:     {name: "리디",     ch: "리", bg: "#1F8CE6", fg: "#fff", re: /리디/},
};
const DCNX_DEFAULT_ORDER = ["novelpia", "naver", "kakao", "munpia", "ridi"];

// "문피아, 네이버 시리즈" → ["munpia", "naver"]
function dcnxPlatforms(text) {
  if (!text) return [];
  return Object.keys(DCNX_PLATFORMS).filter(k => DCNX_PLATFORMS[k].re.test(text));
}

// 설정한 우선순위에서 가장 앞에 있는 연재처 하나
function dcnxPickPlatform(text, order) {
  const has = dcnxPlatforms(text);
  return (order || DCNX_DEFAULT_ORDER).find(k => has.includes(k)) || null;
}

function dcnxIcon(key, size = 16) {
  const p = DCNX_PLATFORMS[key];
  const img = document.createElement("img");
  img.className = "dcnx-icon dcnx-fav";
  img.alt = img.title = p.name;
  img.width = img.height = size;
  img.src = chrome.runtime.getURL(`icons/${key}.png`);   // 확장에 내장된 파비콘 (32px)
  img.onerror = () => img.replaceWith(dcnxLetterIcon(key, size));
  return img;
}

function dcnxLetterIcon(key, size = 16) {
  const p = DCNX_PLATFORMS[key];
  const el = document.createElement("span");
  el.className = "dcnx-icon";
  el.title = p.name;
  el.textContent = p.ch;
  el.style.cssText = `width:${size}px;height:${size}px;font-size:${Math.round(size * 0.62)}px;background:${p.bg};color:${p.fg}`;
  return el;
}

// 별 하나에 평점(0~5) 비율만큼 왼쪽부터 노랗게 채운다
let dcnxStarSeq = 0;
function dcnxStar(rating, size = 14) {
  const id = "dcnx-star-" + (++dcnxStarSeq);
  const pct = Math.max(0, Math.min(1, rating / 5));
  const path = "M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3 6.1 20.6l1.3-6.6L2.5 9.4l6.6-.8z";
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", size); svg.setAttribute("height", size);
  svg.setAttribute("class", "dcnx-star");
  svg.innerHTML =
    `<defs><clipPath id="${id}"><rect x="2.5" y="0" width="${(19 * pct).toFixed(2)}" height="24"/></clipPath></defs>` +
    `<path d="${path}" fill="#D9D9D9"/>` +
    `<path d="${path}" fill="#FFC21A" clip-path="url(#${id})"/>`;
  return svg;
}

// 임시 평점: 작품마다 고정된 가짜 값 (1.0~5.0)
function dcnxFakeRating(wid) {
  let h = 2166136261;
  for (const c of String(wid)) h = Math.imul(h ^ c.charCodeAt(0), 16777619) >>> 0;
  h = Math.imul(h ^ (h >>> 15), 2246822507) >>> 0;
  return 1 + (h % 41) / 10;
}
