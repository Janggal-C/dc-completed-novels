"""연재처 링크 찾기 (소설넷에 없거나 링크가 없는 작품) — AI 웹검색, 구글 검색 한도 안 씀

1) 정식 제목·작가로 AI(Claude 웹검색)에게 연재처 작품 페이지 주소를 찾게 함
2) 주소가 연재처 작품 페이지 형식인지 검사 (export_dict.WORK_URL)
3) 그 페이지를 직접 열어 제목(og:title/title)에 작품명이 들어 있는지 확인 → 맞을 때만 저장
저장: dict/links.json {작품ID: {"links": {연재처: 주소}, "checked": 날짜} | {"miss": True, "checked": 날짜}}
못 찾으면 14일 뒤 다시.
"""
import html
import re
import sys
import time
from datetime import timedelta

import requests

from . import ai
from .common import ALIASES, DICT, WORKS, load_config, norm_key, now_kst, read_json, write_json
from .export_dict import google_link

LINKS = DICT / "links.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}

PROMPT = """아래 한국 웹소설들의 연재처 작품 페이지 주소를 웹검색으로 찾아라.
연재처: 노벨피아(novelpia.com/novel/숫자), 문피아(novel.munpia.com/숫자), 카카오페이지(page.kakao.com/content/숫자),
네이버 시리즈(series.naver.com/novel/detail.series?productNo=숫자), 리디(ridibooks.com/books/숫자).
- 검색 결과에서 실제로 본 주소만 적어라. 추측하거나 만들어내지 마라. 못 찾으면 빈 객체.
- 같은 제목의 다른 작품(작가가 다름)과 헷갈리지 마라.
아래 JSON 배열만 출력: [{"id": 번호, "links": {"novelpia": "주소", "munpia": "주소", ...}}]

"""


def _page_title(url):
    r = requests.get(url, headers=UA, timeout=20)
    if r.status_code != 200:
        return ""
    t = r.text
    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', t) or \
        re.search(r"<title[^>]*>(.*?)</title>", t, re.S)
    return html.unescape(m.group(1)).strip() if m else ""


def verify(title, url):
    """주소 형식 + 실제 페이지 제목 확인 → (연재처, 주소) 또는 None"""
    g = google_link(url)
    if not g:
        return None
    try:
        pt = _page_title(g[1])
    except requests.RequestException:
        return None
    k = norm_key(title)
    pk = norm_key(pt)
    # 페이지 제목에 작품명(띄어쓰기·기호 무시)이 들어 있으면 통과. 아주 긴 제목은 앞 12글자만 비교
    if pk and (k in pk or (len(k) > 12 and k[:12] in pk)):
        return g
    return None


def targets(limit):
    works = read_json(WORKS, {})
    aliases = read_json(ALIASES, {})
    ssn = read_json(DICT / "ssn.json", {})
    links = read_json(LINKS, {})
    used = set(aliases.values())
    retry = str((now_kst() - timedelta(days=14)).date())
    out = []
    for wid in used:
        w = works.get(wid)
        if not w or w.get("excluded"):
            continue
        if ssn.get(wid, {}).get("links"):            # 소설넷에서 링크를 이미 얻음
            continue
        if google_link(w.get("source", "")):         # 예전 구글 링크가 형식 검사 통과
            continue
        l = links.get(wid)
        if l and (l.get("links") or l.get("checked", "") > retry):
            continue
        out.append(wid)
    try:
        from .mentions import compute
        daily, _ = compute()
        out.sort(key=lambda w: -sum(daily.get(w, {}).values()))
    except Exception:
        pass
    return out[:limit]


def find(wids, model, save=True, batch=5):
    works = read_json(WORKS, {})
    links = read_json(LINKS, {})
    today = str(now_kst().date())
    stat = {"found": 0, "miss": 0, "rejected": 0}
    for i in range(0, len(wids), batch):
        part = wids[i:i + batch]
        lines = "\n".join(f"[{n}] {works[w]['title']}" + (f" (작가 {works[w]['author']})" if works[w].get("author") else "")
                          for n, w in enumerate(part))
        try:
            res = ai._json_from(ai._call(PROMPT + lines, model, allow_search=True, max_turns=4 + 3 * len(part)))
        except ai.AIError as e:
            print(f"⚠️ {e}", file=sys.stderr)
            if e.fatal:
                break
            continue
        got = {}
        for r in res:
            try:
                got[int(r.get("id"))] = r.get("links") or {}
            except (TypeError, ValueError):
                continue
        for n, w in enumerate(part):
            ok = {}
            for _, url in (got.get(n) or {}).items():
                v = verify(works[w]["title"], url)
                if v:
                    ok[v[0]] = v[1]
                elif url:
                    stat["rejected"] += 1
                    print(f"    ✗ 확인 실패: {works[w]['title']} ← {url}")
                time.sleep(1)
            if ok:
                links[w] = {"links": ok, "checked": today, "via": "ai-search"}
                stat["found"] += 1
            else:
                links[w] = {"miss": True, "checked": today}
                stat["miss"] += 1
            print(f"  {works[w]['title']} → {ok or '없음'}", flush=True)
        if save:
            write_json(LINKS, links)
    print(f"링크 찾기: {stat} · AI 사용량 {ai.USAGE}")
    return stat


def run(limit=30):
    model = load_config()["judge"].get("review_model", "sonnet")
    find(targets(limit), model)


def test(n=5):
    model = load_config()["judge"].get("review_model", "sonnet")
    find(targets(n), model, save=False)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else None
    {"run": lambda: run(n or 30), "test": lambda: test(n or 5)}[cmd]()
