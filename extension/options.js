const DEFAULTS = {popup: true, skin: "light", icon: true, order: DCNX_DEFAULT_ORDER, list: true, body: true, comment: true};

const info = async () => {
  const {dict, fetchedAt} = await chrome.storage.local.get(["dict", "fetchedAt"]);
  let d = dict;
  if (!d) d = await (await fetch(chrome.runtime.getURL("dict.json"))).json();
  document.getElementById("info").textContent =
    `작품 ${Object.keys(d.works).length}개 · 줄임말 ${Object.keys(d.aliases).length}개 · 사전 ${d.version}` +
    (fetchedAt ? "" : " (내장)") + " · 하루 한 번 자동 갱신";
};

const drawOrder = order => {
  const ul = document.getElementById("order");
  ul.textContent = "";
  order.forEach((k, i) => {
    const li = document.createElement("li");
    const n = document.createElement("span"); n.className = "n"; n.textContent = i + 1;
    const name = document.createElement("span"); name.className = "name"; name.textContent = DCNX_PLATFORMS[k].name;
    const up = document.createElement("button"); up.textContent = "▲"; up.disabled = i === 0;
    const down = document.createElement("button"); down.textContent = "▼"; down.disabled = i === order.length - 1;
    const move = d => {
      const o = order.slice(); [o[i], o[i + d]] = [o[i + d], o[i]];
      chrome.storage.sync.set({order: o}); drawOrder(o);
    };
    up.onclick = () => move(-1); down.onclick = () => move(1);
    li.append(n, dcnxIcon(k), name, up, down);
    ul.append(li);
  });
};

chrome.storage.sync.get(DEFAULTS).then(o => {
  // 나중에 연재처가 추가돼도 순서 목록에 빠지지 않게
  const order = o.order.filter(k => DCNX_PLATFORMS[k]).concat(DCNX_DEFAULT_ORDER.filter(k => !o.order.includes(k)));
  drawOrder(order);
  for (const k in DEFAULTS) {
    const el = document.getElementById(k);
    if (!el || k === "order") continue;
    const box = el.type === "checkbox";
    box ? (el.checked = o[k]) : (el.value = o[k]);
    el.onchange = () => chrome.storage.sync.set({[k]: box ? el.checked : el.value});
  }
});
info();

// 오류 신고
const sendWith = async (btn, msgEl, data, after) => {
  btn.disabled = true; msgEl.textContent = "보내는 중…";
  try { await dcnxSendReport(data); msgEl.textContent = "신고했어요. 고마워요!"; after && after(); }
  catch (e) { msgEl.textContent = "보내지 못했어요. 인터넷 연결을 확인해 주세요."; btn.disabled = false; return; }
  setTimeout(() => { btn.disabled = false; }, 5000);   // 연달아 보내기 방지
};
const qp = new URLSearchParams(location.search);
if (qp.has("w")) {   // 팝업 ⚑ 로 열린 작은 신고 창
  document.getElementById("settings").hidden = true;
  document.getElementById("reportOnly").hidden = false;
  document.getElementById("rw").textContent = qp.get("w");
  document.getElementById("rc").focus();
  document.getElementById("rs").onclick = e => {
    const c = document.getElementById("rc").value.trim();
    if (!c) { document.getElementById("rm").textContent = "코멘트를 적어 주세요."; return; }
    sendWith(e.target, document.getElementById("rm"), {alias: qp.get("w"), title: qp.get("t"), url: qp.get("u"), comment: c},
      () => setTimeout(() => window.close(), 1200));
  };
}
document.getElementById("fs").onclick = e => {
  const t = document.getElementById("fr").value.trim();
  if (!t) { document.getElementById("fm").textContent = "내용을 적어 주세요."; return; }
  sendWith(e.target, document.getElementById("fm"), {comment: t}, () => { document.getElementById("fr").value = ""; });
};
