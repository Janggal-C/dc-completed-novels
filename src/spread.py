"""줄임말이 갤에서 '중구난방'으로 쓰이는지 검사 (AI 없음, 전체 제목 직접 검색)

A. 다른 작품 이름의 일부인 이름: 수선전 ⊂ 회귀수선전·탐식수선전·땅굴수선전 → 한 작품을 못 가리킴
B. 대부분 더 긴 다른 낱말 속에서 쓰이는 이름: 마법소 → 거의 '마법소녀'(일반어)로 쓰임
   제목에서 이름이 들어간 어절을 모아, 그 어절이 같은 작품의 다른 이름도 아니고 이름 그대로(+조사)도 아닌 비율
C. 같은 작품의 다른 이름과 한 제목에 자주 같이 쓰이는 이름 (cooccur): "저능버 짱햄", "괴담텔 호텔파티"
   → 작품 이름 뒤에 붙는 등장인물·작품 속 용어일 가능성이 높다 (AI 검수에 힌트로 줌, 바로 지우진 않음)
결과: data/spread.json {이름: {n, foreign, top, other_works}}
"""
import re
from collections import Counter, defaultdict

from .common import ALIASES, DATA, WORKS, norm_key, read_json, write_json
from .fullcrawl import load_titles
from .matcher import _PARTICLES, excluded

TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


def _in_order(tok, title_key):
    """tok 글자가 정식 제목(띄어쓰기 없앤 키)에 순서대로 다 들어 있나: 외신마도서 ⊂ 외신이쓴마도서를주웠다"""
    it = iter(title_key)
    return all(ch in it for ch in tok)


def run():
    aliases = read_json(ALIASES, {})
    works = read_json(WORKS, {})
    skip = excluded()
    targets = [k for k in aliases if 3 <= len(k) <= 5 and k not in skip]
    by_work = defaultdict(set)
    for k, w in aliases.items():
        by_work[w].add(k)
    # A. 다른 작품 이름 속에 들어 있음
    names = [(k, w) for k, w in aliases.items()] + [(norm_key(v["title"]), wid) for wid, v in works.items()]
    other = defaultdict(set)
    for k in targets:
        for n, w in names:
            if w != aliases[k] and k in n and n != k:
                other[k].add(works.get(w, {}).get("title", w))
    # B. 어절 분포
    first2 = defaultdict(list)
    for k in targets:
        first2[k[:2]].append(k)
    toks = defaultdict(Counter)
    for row in load_titles().values():
        for tok in TOKEN.findall(row["title"].lower()):
            for i in range(len(tok) - 2):
                for k in first2.get(tok[i:i + 2], ()):
                    if tok.startswith(k, i) and i == 0:
                        toks[k][tok] += 1
    out = {}
    for k in targets:
        c = toks[k]
        n = sum(c.values())
        own = by_work[aliases[k]]
        foreign = 0
        for tok, cnt in c.items():
            base = _PARTICLES.sub("", tok)
            if base == k or tok == k or any(o != k and tok.startswith(o) for o in own):
                continue
            if _in_order(base, aliases[k]):    # 정식 제목을 덜 줄인 꼴(외신마도서 ← 외신이 쓴 마도서)도 같은 작품
                continue
            foreign += cnt
        out[k] = {"title": works.get(aliases[k], {}).get("title", ""), "n": n,
                  "foreign": round(foreign / n, 2) if n else 0,
                  "top": [t for t, _ in c.most_common(4)], "other_works": sorted(other[k])[:4]}
    write_json(DATA / "spread.json", out)
    bad_a = [k for k in out if out[k]["other_works"]]
    bad_b = [k for k in out if out[k]["n"] >= 10 and out[k]["foreign"] >= 0.5]
    print(f"검사 {len(out)}개 · A(다른 작품 이름의 일부) {len(bad_a)} · B(주로 다른 낱말 속) {len(bad_b)}")
    return out


def cooccur(keys, aliases=None, titles=None):
    """이름들 → {이름: {"n": 잡힌 제목 수, "co": 같은 작품 다른 이름과 같이 쓰인 비율}}
    작품 제목 자체의 일부(예: 괴이왕국 + 패왕군주)는 띄어 쓴 제목 조각이라 같이 나와도 자연스러우므로 비율 0"""
    from .matcher import Matcher
    aliases = aliases if aliases is not None else read_json(ALIASES, {})
    wids = {aliases[k] for k in keys if k in aliases}
    sub = {k: k for k, w in aliases.items() if w in wids}
    if not sub:
        return {}
    m = Matcher(sub)
    m.long = sorted((k for k in sub if len(k) >= 3), key=len, reverse=True)
    m.short = {k for k in sub if len(k) < 3}
    m._rank = {a: i for i, a in enumerate(m.long)}
    hits, co = Counter(), Counter()
    rows = titles.values() if titles is not None else load_titles().values()
    for r in rows:
        found = list(m.find(r["title"]))
        for a in found:
            hits[a] += 1
            if any(b != a and aliases[b] == aliases[a] and a not in b and b not in a for b in found):
                co[a] += 1
    out = {}
    for k in keys:
        if k not in aliases or not hits[k]:
            continue
        part_of_title = k in aliases[k]
        out[k] = {"n": hits[k], "co": 0 if part_of_title else round(co[k] / hits[k], 2)}
    return out


if __name__ == "__main__":
    run()
