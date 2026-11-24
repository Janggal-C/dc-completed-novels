// 사전을 하루 한 번 GitHub Pages에서 받아 저장한다. 실패하면 동봉된 dict.json을 쓴다.
const DICT_URL = "https://answhdtjr736-spec.github.io/dc-completed-novels/api/dict.json";

async function refresh() {
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

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("refresh", {periodInMinutes: 24 * 60});
  refresh();
});
chrome.runtime.onStartup.addListener(refresh);
chrome.alarms.onAlarm.addListener(a => { if (a.name === "refresh") refresh(); });
chrome.runtime.onMessage.addListener((msg, _s, reply) => {
  if (msg === "refresh") { refresh().then(() => reply(true)); return true; }
});
