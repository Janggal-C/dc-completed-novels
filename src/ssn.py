"""소설넷(ssn.so) — 사전 작품의 평점·연재처 링크 (완결 표시는 있을 때만 참고)

- 처음: 정식 제목으로 검색(/series/?keyword=) → 제목(+작가)이 맞는 작품 → 상세 페이지
- 이후: 소설넷 주소를 알고 있으니 상세 페이지만. 전체를 7등분해 하루 1/7씩 갱신
- 소설넷에서 못 찾은 작품은 miss 로 기록, 7일마다 다시 검색 (그 사이 구글로 연재처만 채움)
- 소설넷 규칙(robots.txt Crawl-delay: 10)대로 요청 간격 10초

검색 규칙 (다음에 구현 — 못 찾은 작품 분석 결과, 2026-11-25 확정):
  1) 전체 제목 그대로 검색
  2) 제목 정리 후 검색: [ ] ( ) ~ ~ 안 부분과 "현 제목:" 같은 메모 제거. 괄호 안이 다른 제목이면 그것도 검색.
     → 제목(정규화)이 정확히 같을 때만 인정
  3) 앞 1~2단어 키워드로 검색 → 제목이 같거나 거의 같고 작가도 맞을 때만 인정
  4) 구글 "제목 웹소설" 1회: 소설넷 페이지 있으면 그걸로 평점까지, 없으면 연재처 작품 페이지 링크만 (주소 형식 검사, 하루 한도 지킴)
  - 작가 이름은 표기가 달라 매칭 필수 조건으로 쓰지 않음 (예: philceta = 똥필). 애매할 때 확인용만.
  - 연재처가 만화·웹툰·출판이면 소설넷·구글 건너뜀
  - 다 실패하면 7일 뒤 다시
  - 소설넷 완결 표시는 있을 때만 참고, 없으면 무시. 평점은 평가 수 상관없이 표시.
저장: dict/ssn.json {작품ID: {id, r, rc, done, links, checked} | {miss, checked}}
"""
import json
import re
import sys
import time
from datetime import timedelta
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from .common import DICT, WORKS, checkpoint, norm_key, now_kst, read_json, write_json

SSN = DICT / "ssn.json"
BASE = "https://ssn.so"
DELAY = 10
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}
# 소설넷 배지 이름 → 확장의 연재처 키
PLATFORM = {"novelpia": "novelpia", "naver": "naver", "kakao": "kakao", "kakaopage": "kakao",
            "munpia": "munpia", "ridibooks": "ridi", "ridi": "ridi", "joara": "joara"}
DONE_RE = re.compile(r"\s*완결\s*$")


class Client:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(UA)
        self.last = 0

    def get(self, path):
        wait = self.last + DELAY - time.time()
        if wait > 0:
            time.sleep(wait)
        for n in range(3):
            self.last = time.time()
            try:
                r = self.s.get(BASE + path, timeout=30)
                if r.status_code == 404:
                    return None
                if r.status_code in (429, 503):
                    time.sleep(60 * (n + 1)); continue
                r.raise_for_status()
                return BeautifulSoup(r.text, "html.parser")
            except requests.RequestException as e:
                print(f"  요청 실패 {path}: {e}")
                time.sleep(30 * (n + 1))
        return None


def search(c, title):
    """검색 결과 → [{id, title, done, author}]"""
    soup = c.get(f"/series/?keyword={quote(title)}")
    if not soup:
        return []
    out = {}
    for a in soup.select("a[href]"):
        m = re.fullmatch(r"/series/(\d+)/", a["href"])
        if not m:
            continue
        text = a.get_text(" ", strip=True)
        if not text:
            continue
        sid = int(m.group(1))
        # 같은 카드 안의 작가 링크 찾기
        author, box = "", a
        for _ in range(6):
            box = box.parent
            if box is None:
                break
            au = box.select_one("a[href*='/series/author/']")
            if au:
                author = au.get_text(" ", strip=True)
                break
        out.setdefault(sid, {"id": sid, "title": DONE_RE.sub("", text), "done": bool(DONE_RE.search(text)), "author": author})
    return list(out.values())


def pick(cands, title, author=""):
    key = norm_key(title)
    same = [x for x in cands if norm_key(x["title"]) == key]
    if author and len(same) > 1:
        same = [x for x in same if norm_key(x["author"]) == norm_key(author)] or same
    return same[0] if same else None


def detail(c, sid):
    soup = c.get(f"/series/{sid}/")
    if not soup:
        return None
    info = {"id": sid}
    for sc in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(sc.string or "")
        except ValueError:
            continue
        for node in data.get("@graph", [data]) if isinstance(data, dict) else []:
            if node.get("@type") == "Book":
                info["title"] = node.get("name", "")
                au = node.get("author") or {}
                info["author"] = au.get("name", "") if isinstance(au, dict) else ""
                ar = node.get("aggregateRating") or {}
                if ar.get("ratingCount"):
                    info["r"] = round(float(ar["ratingValue"]), 2)
                    info["rc"] = int(ar["ratingCount"])
    links = {}
    for a in soup.select("a.link-series[href]"):
        for cls in a.get("class", []):
            if cls.startswith("badge-") and cls[6:] in PLATFORM:
                links.setdefault(PLATFORM[cls[6:]], a["href"])
    info["links"] = links
    h1 = soup.find("h1")
    head = h1.parent.get_text(" ", strip=True) if h1 else ""
    info["done"] = "완결" in head[: len(info.get("title", "")) + 40]
    return info


def clean(d):
    """저장용: 완결 표시가 없으면 done 키 자체를 남기지 않는다"""
    if not d.get("done"):
        d.pop("done", None)
    return d


def lookup(c, w):
    """사전 작품 하나 → 소설넷 정보 또는 {"miss": True}"""
    hit = pick(search(c, w["title"]), w["title"], w.get("author", ""))
    if not hit:
        return {"miss": True}
    d = detail(c, hit["id"])
    if not d:
        return {"miss": True}
    # 소설넷 완결 표시는 있을 때만 참고 (없다고 연재중은 아님 — 표시 없는 완결작이 많음)
    if d.pop("done") or hit["done"]:
        d["done"] = True
    return d


BIG_RATINGS = 100        # 평가가 이만큼 이상이면 평점이 거의 안 바뀜
REFRESH_DAYS_BIG = 30
REFRESH_DAYS = 7


def run(max_minutes=180):
    works = read_json(WORKS, {})
    ssn = read_json(SSN, {})
    c = Client()
    today = now_kst().date()
    # 1) 처음 보는 작품 / 못 찾은 지 7일 지난 작품
    # 2) 평점 갱신: 평가 100개 이상은 30일마다(거의 안 바뀜), 그 밖은 7일마다. 오래된 것부터
    new = [k for k in works if k not in ssn or (ssn[k].get("miss") and ssn[k].get("checked", "") <= str(today - timedelta(days=7)))]
    def due(k):
        v = ssn[k]
        days = REFRESH_DAYS_BIG if v.get("rc", 0) >= BIG_RATINGS else REFRESH_DAYS
        return v.get("checked", "") <= str(today - timedelta(days=days))
    turn = sorted((k for k in works if k in ssn and not ssn[k].get("miss") and due(k)),
                  key=lambda k: ssn[k].get("checked", ""))
    print(f"소설넷: 새 작품 {len(new)}개, 오늘 갱신 차례 {len(turn)}개")
    end = time.time() + max_minutes * 60
    stats = {"found": 0, "miss": 0, "refresh": 0}
    for k in new + turn:
        if time.time() > end:
            print("시간 제한, 다음에 이어서"); break
        w = works[k]
        if k in turn:
            d = detail(c, ssn[k]["id"])
            if not d:
                continue
            clean(d)
            stats["refresh"] += 1
        else:
            d = lookup(c, w)
            stats["miss" if d.get("miss") else "found"] += 1
        d["checked"] = str(today)
        ssn[k] = d
        msg = "없음" if d.get("miss") else f"{d.get('r', '-')} ({d.get('rc', 0)}) {list(d['links'])}"
        print(f"  {w['title']} → {msg}")
        write_json(SSN, ssn)
        checkpoint("소설넷 정보 갱신", every_seconds=300, report=False)
    print(f"소설넷 결과: {stats}")
    checkpoint("소설넷 정보 갱신", force=True, report=False)


def hash_day(k):
    h = 0
    for ch in k:
        h = (h * 131 + ord(ch)) % 1000003
    return h % 7


def test(n=5):
    """저장 없이 몇 작품만 시험"""
    works = read_json(WORKS, {})
    names = ["약먹는 천재마법사", "21세기 반로환동전", "6★ 가챠 캐릭터가 되었다", "판초우의의 마법사", "13년간 모신 악녀가 쓰러졌다"]
    by_title = {w["title"]: w for w in works.values()}
    picks = [by_title[t] for t in names if t in by_title][:n]
    c = Client()
    for w in picks:
        cands = search(c, w["title"])
        print(f"\n■ {w['title']} (작가 {w.get('author', '?')}) 검색 결과 {len(cands)}개")
        for x in cands[:6]:
            print("   ", x)
        hit = pick(cands, w["title"], w.get("author", ""))
        print("  선택:", hit)
        if hit:
            print("  상세:", detail(c, hit["id"]))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "test":
        test(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
    else:
        run()
