// 연재처 아이콘: 각 사이트의 파비콘(북마크에 뜨는 아이콘). 못 불러오면 글자 아이콘으로 대체
const DCNX_PLATFORMS = {
  novelpia: {name: "노벨피아", domain: "novelpia.com", ch: "노", bg: "#6A4CF0", fg: "#fff", re: /노벨피아/},
  naver:    {name: "네이버", domain: "naver.com",   ch: "네", bg: "#03C75A", fg: "#fff", re: /네이버|시리즈/},
  kakao:    {name: "카카오", domain: "page.kakao.com",   ch: "카", bg: "#FEE500", fg: "#191919", re: /카카오/},
  munpia:   {name: "문피아", domain: "munpia.com",   ch: "문", bg: "#E8532D", fg: "#fff", re: /문피아/},
  ridi:     {name: "리디", domain: "ridibooks.com",     ch: "리", bg: "#1F8CE6", fg: "#fff", re: /리디/},
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
  img.src = `https://www.google.com/s2/favicons?domain=${p.domain}&sz=${size * 2}`;
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
