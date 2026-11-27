"""확장 프로그램용 사전 공개 파일: docs/api/dict.json

{
  "version": "2026-11-25T01:10",
  "rules": {"min_len": 3, "full_from": 6, "ambiguous": [...]},   # 대조 규칙 (src/matcher.py 와 동일)
  "works": {"id": {"t": 정식 제목, "a": 작가, "p": 연재처, "s": "완결|연재중|", "u": 링크}},
  "aliases": {"정규화된 줄임말": "작품 id"}
}
"""
import json
import re

from .common import ALIASES, DICT, ROOT, WORKS, now_kst, read_json
from .matcher import excluded


# 구글에서 얻은 링크는 연재처 작품 페이지 형식일 때만 쓴다 (리뷰·블로그·검색 결과 등은 버림)
WORK_URL = {
    "novelpia": re.compile(r"^https?://(www\.)?novelpia\.com/novel/\d+/?$"),
    "naver": re.compile(r"^https?://(m\.)?series\.naver\.com/novel/detail\.(series|nhn)\?productNo=\d+"),
    "kakao": re.compile(r"^https?://page\.kakao\.com/(content/\d+|landing/series/\d+|home\?seriesId=\d+)"),
    "munpia": re.compile(r"^https?://(novel\.munpia\.com/\d+/?$|(www\.)?munpia\.com/novel/detail/\d+)"),
    "ridi": re.compile(r"^https?://(www\.)?ridibooks\.com/books/\d+"),
}


def google_link(url):
    """구글 결과 링크 → (연재처, 주소) 또는 None"""
    m = re.match(r"^https?://m\.munpia\.com/novel/detail/(\d+)", url or "")
    if m:
        return "munpia", f"https://novel.munpia.com/{m.group(1)}"
    for k, rx in WORK_URL.items():
        if url and rx.match(url):
            return k, url
    return None


def work_links(w, sn, ai):
    """작품 하나의 연재처 링크 {연재처: 주소}. 소설넷 것은 그대로, AI 웹검색으로 찾은 것, 구글 것은 작품 페이지 형식만"""
    links = dict((sn or {}).get("links", {}))
    for k2, u2 in ((ai or {}).get("links") or {}).items():   # AI 웹검색으로 찾고 페이지까지 확인한 링크
        links.setdefault(k2, u2)
    g = google_link((w or {}).get("source", ""))
    if g and g[0] not in links:
        links[g[0]] = g[1]
    links.pop("joara", None)
    return links


# 연재처 이름(works.json platform 글) → 링크 키. 대표 링크는 platform 글에 먼저 나온 연재처를 고른다
PLAT_NAMES = [("novelpia", "노벨피아"), ("munpia", "문피아"), ("naver", "시리즈"), ("naver", "네이버"),
              ("kakao", "카카오"), ("ridi", "리디")]
PLAT_LABEL = {"novelpia": "노벨피아", "munpia": "문피아", "naver": "네이버 시리즈", "kakao": "카카오페이지", "ridi": "리디"}


def main_link(links, platform=""):
    """대표 링크 (키, 주소) 또는 None"""
    if not links:
        return None
    hits = sorted((platform.find(name), key) for key, name in PLAT_NAMES if name in (platform or "") and key in links)
    if hits:
        return hits[0][1], links[hits[0][1]]
    for key in PLAT_LABEL:
        if key in links:
            return key, links[key]
    k = next(iter(links))
    return k, links[k]


_LINK_CACHE = {}


def link_of(wid):
    """작품 id → {"u": 대표 주소, "p": 연재처 이름} 또는 None (사이트 집계 파일용)"""
    if "t" not in _LINK_CACHE:
        works = read_json(WORKS, {})
        ssn = read_json(DICT / "ssn.json", {})
        ai_links = read_json(DICT / "links.json", {})
        t = {}
        for k, w in works.items():
            m = main_link(work_links(w, ssn.get(k), ai_links.get(k)), w.get("platform", ""))
            if m:
                t[k] = {"u": m[1], "p": PLAT_LABEL.get(m[0], m[0])}
        _LINK_CACHE["t"] = t
    return _LINK_CACHE["t"].get(wid)


def run():
    works = read_json(WORKS, {})
    aliases = read_json(ALIASES, {})
    ssn = read_json(DICT / "ssn.json", {})
    ai_links = read_json(DICT / "links.json", {})
    used = set(aliases.values())
    out_works = {}
    for wid in used:
        w = works.get(wid)
        if not w:
            continue
        sn = ssn.get(wid, {})
        links = work_links(w, sn, ai_links.get(wid))
        e = {"t": w["title"], "a": w.get("author", ""), "p": w.get("platform", ""), "s": w.get("status", ""), "l": links}
        if sn.get("r") is not None:
            e["r"] = sn["r"]
            e["n"] = f"https://ssn.so/series/{sn['id']}/"
        out_works[wid] = {k: v for k, v in e.items() if v}
    data = {
        "version": now_kst().strftime("%Y-%m-%dT%H:%M"),
        "rules": {"min_len": 3, "full_from": 6, "ambiguous": sorted(excluded())},
        "works": out_works,
        "aliases": {k: v for k, v in aliases.items() if v in out_works},
    }
    path = ROOT / "docs" / "api" / "dict.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    print(f"사전 공개 파일: 작품 {len(out_works)}개, 이름 {len(data['aliases'])}개")
    return data


if __name__ == "__main__":
    run()
