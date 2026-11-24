// 연재처 아이콘: 같은 모양(둥근 사각형 + 한 글자)에 색만 다르게
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
  const el = document.createElement("span");
  el.className = "dcnx-icon";
  el.title = p.name;
  el.textContent = p.ch;
  el.style.cssText = `width:${size}px;height:${size}px;font-size:${Math.round(size * 0.62)}px;background:${p.bg};color:${p.fg}`;
  return el;
}
