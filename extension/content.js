(async () => {
  const isGenre = location.hostname.startsWith("m.")
    ? location.pathname.startsWith("/board/genrenovel")
    : new URLSearchParams(location.search).get("id") === "genrenovel";
  if (!isGenre) return;

  const DEFAULTS = {popup: true, expand: false, list: true, body: true, comment: true};
  const opt = Object.assign({}, DEFAULTS, await chrome.storage.sync.get(DEFAULTS));
  if (!opt.popup && !opt.expand) return;

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
  tip.className = "dcnx-tip";
  document.documentElement.appendChild(tip);
  const show = el => {
    tip.textContent = M.label(el.dataset.wid);
    tip.style.display = "block";
    const r = el.getBoundingClientRect();
    const top = r.top - tip.offsetHeight - 6;
    tip.style.top = (top < 4 ? r.bottom + 6 : top) + "px";
    tip.style.left = Math.max(4, Math.min(r.left, innerWidth - tip.offsetWidth - 4)) + "px";
  };
  const hide = () => { tip.style.display = "none"; };
  document.addEventListener("mouseover", e => {
    const el = e.target.closest && e.target.closest(".dcnx");
    el ? show(el) : hide();
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
      span.className = opt.popup ? "dcnx" : "dcnx dcnx-plain";
      span.dataset.wid = h.wid;
      const orig = text.slice(h.start, h.end);
      const title = (M.works[h.wid] || {}).t || orig;
      span.textContent = opt.expand && title.replace(/\s/g, "") !== orig.replace(/\s/g, "") ? `${title}(${orig})` : orig;
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
