"""줄임말 ↔ 정식 제목 조합 일치 (노벨피아 순위 누적 목록 + 사전 작품 제목)

줄임말을 2글자 이상 조각으로 나눠, 각 조각이 제목의 서로 다른 단어의 '앞부분'과 맞으면 일치로 본다.
순서는 따지지 않는다.  임신황녀·황녀임신 → '임신시켰더니 황녀였다' (임신←임신시켰더니, 황녀←황녀였다)
기존 사전 줄임말 약 2,000개로 시험: 정답 작품 복원 65%, 그중 99%가 후보 1개로 좁혀짐 (초성·영문 줄임말은 못 잡음).

여기서는 '후보'만 만든다. 등록 여부는 지금처럼 갤 실제 사용 예시(90% 기준)로 판정한다.
- find(word, titles)    : 일치하는 제목들
- write_conflicts()     : 사전에 이미 있는 줄임말이 '다른' 랭킹 제목과도 맞는 경우를 data/ranking_conflicts.json 에 기록
"""
import re

from .common import ALIASES, DATA, WORKS, now_kst, norm_key, read_json, write_json

HISTORY = DATA / "ranking_history.json"
CONFLICTS = DATA / "ranking_conflicts.json"
_WORD = re.compile(r"[가-힣a-z0-9]+")


def _words(title):
    return _WORD.findall((title or "").lower())


def match(alias, title):
    alias = norm_key(alias)
    if len(alias) < 3:
        return False
    tw = _words(title)

    def rec(s, used):
        if not s:
            return True
        for n in range(2, len(s) + 1):
            piece = s[:n]
            for i, w in enumerate(tw):
                if i not in used and w.startswith(piece) and rec(s[n:], used | {i}):
                    return True
        return False

    return rec(alias, frozenset())


def find(word, titles):
    return [t for t in titles if match(word, t)]


def ranking_titles():
    return list(read_json(HISTORY, {}))


def write_conflicts():
    """이미 등록된 줄임말이 다른 랭킹 제목과도 맞으면 기록 (같은 작품이면 제외)"""
    works, aliases, rk = read_json(WORKS, {}), read_json(ALIASES, {}), ranking_titles()
    rk_keys = {norm_key(t): t for t in rk}
    out = {}
    for alias, wid in aliases.items():
        cur = works.get(wid, {}).get("title", wid)
        cur_key = norm_key(cur)
        others = [t for k, t in rk_keys.items() if k != cur_key and match(alias, t)]
        if others:
            out[alias] = {"현재": cur, "랭킹에서도 일치": others[:5]}
    write_json(CONFLICTS, {"checked": now_kst().strftime("%Y-%m-%d %H:%M"), "n": len(out), "items": out})
    print(f"줄임말 충돌 후보 {len(out)}개 → {CONFLICTS.name}")
    return out
