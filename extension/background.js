// 사전: 설치 파일에 내장(dict.json). 빌드 다음 날부터 하루 한 번 GitHub Pages에서 새 사전을 받는다.
// - 빌드 당일(아래 시각 전)에는 받지 않음 → 처음 배포한 날 한꺼번에 몰리지 않게
// - 매일 확인 시각은 사람마다 최대 1시간 랜덤하게 늦춤
const DICT_URL = "https://janggal-c.github.io/dc-completed-novels/api/dict.json";
const NO_CHECK_UNTIL = Date.parse("__NO_CHECK_UNTIL__") || 0;   // 빌드 다음 날 0시(한국시간)

async function refresh() {
  if (Date.now() < NO_CHECK_UNTIL) return;
  try {
    const r = await fetch(DICT_URL, {cache: "no-cache"});
    if (!r.ok) throw new Error(r.status);
    const dict = await r.json();
    if (!dict.aliases || !dict.works) throw new Error("형식 오류");
    await chrome.storage.local.set({dict, fetchedAt: Date.now()});
  } catch (e) {
    console.warn("사전 갱신 실패:", e);
  }
}

function schedule() {
  // 빌드 다음 날 이후 설치면 바로 첫 확인, 그 전이면 다음 날 0시 + 랜덤(최대 1시간)
  const jitter = Math.random() * 60 * 60 * 1000;
  const first = Math.max(Date.now() + 60 * 1000, NO_CHECK_UNTIL + jitter);
  chrome.alarms.create("refresh", {when: first, periodInMinutes: 24 * 60});
}
chrome.runtime.onInstalled.addListener(() => { schedule(); if (Date.now() >= NO_CHECK_UNTIL) refresh(); });
chrome.runtime.onStartup.addListener(async () => {
  if (!(await chrome.alarms.get("refresh"))) schedule();
  const {fetchedAt} = await chrome.storage.local.get("fetchedAt");
  if (!fetchedAt || Date.now() - fetchedAt > 24 * 60 * 60 * 1000) setTimeout(refresh, Math.random() * 60 * 60 * 1000);
});
chrome.alarms.onAlarm.addListener(a => { if (a.name === "refresh") refresh(); });

// 팝업의 ⚑ → 작은 신고 창 (확장 설정 페이지의 신고 화면)
chrome.runtime.onMessage.addListener(msg => {
  if (msg && msg.type === "report") {
    const q = new URLSearchParams({w: msg.alias || "", t: msg.title || "", u: msg.url || ""});
    chrome.windows.create({url: chrome.runtime.getURL("options.html?" + q), type: "popup", width: 380, height: 360});
  }
});
