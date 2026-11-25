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


def run():
    works = read_json(WORKS, {})
    aliases = read_json(ALIASES, {})
    ssn = read_json(DICT / "ssn.json", {})
    used = set(aliases.values())
    out_works = {}
    for wid in used:
        w = works.get(wid)
        if not w:
            continue
        sn = ssn.get(wid, {})
        # 연재처 링크: 소설넷 것은 그대로, 구글 것은 작품 페이지 형식만
        links = dict(sn.get("links", {}))
        g = google_link(w.get("source", ""))
        if g and g[0] not in links:
            links[g[0]] = g[1]
        links.pop("joara", None)
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
