const DEFAULTS = {popup: true, skin: "light", list: true, body: true, comment: true};
const info = async () => {
  const {dict, fetchedAt} = await chrome.storage.local.get(["dict", "fetchedAt"]);
  let d = dict;
  if (!d) d = await (await fetch(chrome.runtime.getURL("dict.json"))).json();
  document.getElementById("info").textContent =
    `작품 ${Object.keys(d.works).length}개 · 줄임말 ${Object.keys(d.aliases).length}개 · 사전 ${d.version}` +
    (fetchedAt ? "" : " (내장)") + " · 하루 한 번 자동 갱신";
};
chrome.storage.sync.get(DEFAULTS).then(o => {
  for (const k in DEFAULTS) {
    const el = document.getElementById(k);
    const box = el.type === "checkbox";
    box ? (el.checked = o[k]) : (el.value = o[k]);
    el.onchange = () => chrome.storage.sync.set({[k]: box ? el.checked : el.value});
  }
});
info();
