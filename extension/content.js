(async () => {
  const isGenre = location.hostname.startsWith("m.")
    ? location.pathname.startsWith("/board/genrenovel")
    : new URLSearchParams(location.search).get("id") === "genrenovel";
  if (!isGenre) return;

  const DEFAULTS = {popup: true, skin: "light", list: true, body: true, comment: true};
  const opt = Object.assign({}, DEFAULTS, await chrome.storage.sync.get(DEFAULTS));
  if (!opt.popup) return;

  let {dict} = await chrome.storage.local.get("dict");
  if (!dict) dict = await (await fetch(chrome.runtime.getURL("dict.json"))).json();
  const M = new DcnxMatcher(dict);

  const SEL = {
    list: "td.gall_tit > a:not(.reply_numbox), .gall-detail-lnktb .subjectin",
    body: ".title_subject, .write_div, .gallview-tit-box .tit, .thum-txtin",
    comment: ".comment_box .usertxt, .comment_box .comment_dccon ~ *, .all-comment-lst .txt",
  };
  const selector = Object.keys(SEL).filter(k => opt[k]).map(k => SEL[k]).join(", ");
  if (!selector) return;

  // 팝업
  const tip = document.createElement("div");
  tip.className = "dcnx-tip dcnx-" + (opt.skin === "dark" ? "dark" : "light");
  document.documentElement.appendChild(tip);
  const show = el => {
    const {title, done} = M.label(el.dataset.wid);
    tip.textContent = title;
    if (done) {
      const b = document.createElement("b");
      b.textContent = "완";
      tip.append(" · ", b);
    }
    tip.style.display = "block";
    const r = el.getBoundingClientRect();
    // 기본은 아래쪽, 화면 밑에 안 들어가면 위쪽
    const below = r.bottom + 6;
    tip.style.top = (below + tip.offsetHeight > innerHeight - 4 ? r.top - tip.offsetHeight - 6 : below) + "px";
    tip.style.left = Math.max(4, Math.min(r.left, innerWidth - tip.offsetWidth - 4)) + "px";
  };
  // 줄임말 → 팝업으로 마우스를 옮기는 동안 사라지지 않게 잠깐 기다렸다 닫는다
  let hideTimer = null, current = null;
  const hide = () => { clearTimeout(hideTimer); hideTimer = null; current = null; tip.style.display = "none"; };
  const hideSoon = () => { if (!hideTimer) hideTimer = setTimeout(hide, 300); };
  document.addEventListener("mouseover", e => {
    const t = e.target;
    if (!t.closest) return;
    if (t.closest(".dcnx-tip")) { clearTimeout(hideTimer); hideTimer = null; return; }
    const el = t.closest(".dcnx");
    if (el) {
      clearTimeout(hideTimer); hideTimer = null;
      if (el !== current) { current = el; show(el); }
    } else if (tip.style.display === "block") hideSoon();
  });
  addEventListener("scroll", hide, {passive: true});

  const processText = node => {
    const text = node.nodeValue;
    if (!text || text.trim().length < 2) return;
    const hits = M.find(text);
    if (!hits.length) return;
    const frag = document.createDocumentFragment();
    let last = 0;
    for (const h of hits) {
      if (h.start > last) frag.appendChild(document.createTextNode(text.slice(last, h.start)));
      const span = document.createElement("span");
      span.className = "dcnx";
      span.dataset.wid = h.wid;
      span.textContent = text.slice(h.start, h.end);
      frag.appendChild(span);
      last = h.end;
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    node.parentNode.replaceChild(frag, node);
  };

  const processEl = el => {
    if (el.dataset.dcnxDone) return;
    el.dataset.dcnxDone = "1";
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
      acceptNode: n => n.parentElement.closest(".dcnx, script, style, textarea, input") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(processText);
  };

  const scan = root => {
    if (root.matches && root.matches(selector)) processEl(root);
    root.querySelectorAll && root.querySelectorAll(selector).forEach(processEl);
  };
  scan(document);
  new MutationObserver(ms => {
    for (const m of ms) for (const n of m.addedNodes) if (n.nodeType === 1 && !n.classList.contains("dcnx")) scan(n);
  }).observe(document.body, {childList: true, subtree: true});
})();
