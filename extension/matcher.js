// src/matcher.py 와 같은 규칙. 결과에 원문 위치(start, end)를 돌려준다.
const DCNX_WORD = /[\p{L}\p{N}]/u;
const DCNX_TOKEN = /[\p{L}\p{N}]+/gu;
const DCNX_PART = /(은|는|이|가|도|을|를|의|에|에서|이랑|랑|하고|까지|부터|만|이네|처럼|보다|임|이냐|냐|나|야)$/u;

class DcnxMatcher {
  constructor(dict) {
    const r = dict.rules || {};
    const minLen = r.min_len || 3;
    this.fullFrom = r.full_from || 6;
    const amb = new Set(r.ambiguous || []);
    this.aliases = dict.aliases;
    this.works = dict.works;
    const keys = Object.keys(dict.aliases).filter(k => !amb.has(k));
    this.long = keys.filter(k => [...k].length >= minLen).sort((a, b) => [...b].length - [...a].length);
    this.short = new Set(keys.filter(k => [...k].length < minLen));
  }

  // text → [{start, end, alias, wid}] (원문 UTF-16 위치, 겹치지 않음, 순서대로)
  find(text) {
    const lower = text.toLowerCase();
    const chars = [], pos = [], starts = [];
    let prev = false;
    for (let i = 0; i < lower.length;) {
      const cp = lower.codePointAt(i), ch = String.fromCodePoint(cp), w = DCNX_WORD.test(ch);
      if (w) { chars.push(ch); pos.push(i); starts.push(!prev); }
      prev = w; i += ch.length;
    }
    const key = chars.join("");
    // key 안의 UTF-16 위치 → chars 인덱스
    const idx = []; let off = 0;
    chars.forEach((c, n) => { idx[off] = n; off += c.length; });
    const used = new Array(chars.length).fill(false);
    const out = [];
    for (const a of this.long) {
      const alen = [...a].length;
      let s = key.indexOf(a);
      while (s !== -1) {
        const ci = idx[s], ce = ci + alen;
        if ((alen >= this.fullFrom || starts[ci]) && !used.slice(ci, ce).some(Boolean)) {
          for (let i = ci; i < ce; i++) used[i] = true;
          out.push({start: pos[ci], end: pos[ce - 1] + chars[ce - 1].length, alias: a, wid: this.aliases[a]});
        }
        s = key.indexOf(a, s + 1);
      }
    }
    for (const m of lower.matchAll(DCNX_TOKEN)) {
      const tok = m[0];
      for (const t of [tok, tok.replace(DCNX_PART, "")]) {
        if (t && this.short.has(t)) {
          const start = m.index, end = m.index + t.length;
          let clash = false;
          for (let i = 0; i < pos.length; i++) if (pos[i] >= start && pos[i] < end && used[i]) clash = true;
          if (!clash) out.push({start, end, alias: t, wid: this.aliases[t]});
          break;
        }
      }
    }
    return out.sort((x, y) => x.start - y.start);
  }

  label(wid) {
    const w = this.works[wid] || {};
    return (w.t || "") + (w.s === "완결" ? " · 완" : "");
  }
}
if (typeof module !== "undefined") module.exports = DcnxMatcher;
