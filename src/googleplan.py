"""하루 구글 검색(SerpApi 30회 + Serper 남은 무료분)을 우선순위대로 나눠 쓴다.

검색이 필요한 두 종류를 한 줄로 세워 '가치'가 큰 것부터:
  A. 새 작품 단어(정식 제목 모름) → 검색 1회로 정식 제목 찾기  (words.py)
  B. 연재처 링크가 없는 작품(소설넷에 없거나 링크 없음) → 검색 1회로 연재처 작품 페이지 찾기
가치 = 최근 한 달 예상 언급 수 (A: 단어를 쓴 작성자 수의 월평균, B: 최근 30일 언급 수)
B는 AI 없이: 검색 결과 주소가 연재처 작품 페이지 형식인지 + 그 페이지 제목에 작품명이 있는지 확인될 때만 저장.
"""
import sys
from datetime import timedelta

from . import google
from .common import DATA, DICT, WORKS, load_config, now_kst, read_json, write_json
from .linkfind import LINKS, targets as link_targets, verify

PLATFORM_Q = "노벨피아 OR 문피아 OR 카카오페이지 OR 시리즈 OR 리디"


def plan(budget):
    from .mentions import compute
    from .words import todo as word_todo
    daily, _ = compute()
    since = str((now_kst() - timedelta(days=30)).date())
    recent = {w: sum(n for d, n in days.items() if d >= since) for w, days in daily.items()}
    queue = []
    for word, v in word_todo():
        queue.append((v.get("w", 0) / 11, "word", word))          # 11개월 작성자 수 → 월평균
    for wid in link_targets(10 ** 6):
        queue.append((recent.get(wid, 0), "link", wid))
    queue.sort(key=lambda x: -x[0])
    pick = [q for q in queue if q[0] > 0][:budget]
    print(f"[구글 검색 계획] 오늘 {budget}회 · 대기 {len(queue)}개 → 단어 {sum(q[1] == 'word' for q in pick)}, "
          f"링크 {sum(q[1] == 'link' for q in pick)}", flush=True)
    return pick


def find_links(wids, cfg):
    works = read_json(WORKS, {})
    links = read_json(LINKS, {})
    today = str(now_kst().date())
    found = 0
    for wid in wids:
        t = works[wid]["title"]
        try:
            res = google.web_search(f'"{t}" {PLATFORM_Q}', cfg)
        except RuntimeError as e:
            print(f"  검색 중단: {e}"); break
        ok = {}
        for r in res:
            v = verify(t, r.get("link", ""))
            if v and v[0] not in ok:
                ok[v[0]] = v[1]
        links[wid] = ({"links": ok, "checked": today, "via": "google"} if ok else {"miss": True, "checked": today})
        found += bool(ok)
        print(f"  {t} → {ok or '없음'}", flush=True)
        write_json(LINKS, links)
    print(f"[링크] {len(wids)}개 중 {found}개 찾음")


def run():
    cfg = load_config()
    budget = google.web_left(cfg)
    if not budget:
        print("오늘 검색 한도 없음"); return
    pick = plan(budget)
    words = {x[2] for x in pick if x[1] == "word"}
    if words:
        from . import words as W
        W.only(words)
    find_links([x[2] for x in pick if x[1] == "link"], cfg)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "plan":
        for v, kind, k in plan(int(sys.argv[2]) if len(sys.argv) > 2 else 30):
            print(f"  {v:7.1f} {kind} {k}")
    else:
        run()
