"""언급 집계: 완결 여부와 상관없이 작품별 언급 수 (월별·분기별)

언급 수 = 하루 단위 작성자 수. 같은 사람이 같은 날 같은 작품을 여러 번 써도 1, 다음 날 또 쓰면 다시 1.
전체 제목(data/titles)에 줄임말 사전을 대조해서 센다 (AI·검색 없음).
결과: docs/data/mentions.json (배포 때 생성, 저장소에는 안 올림)
"""
import time
from collections import defaultdict

from .common import ALIASES, WORKS, DATA, quarter_of, read_json, write_json, SITE_DATA, now_kst
from .fullcrawl import load_titles
from .matcher import Matcher


_CACHE = {}


def _link(wid):
    """연재처 링크가 있으면 {"url", "plat"} (사이트에서 작품명을 링크로)"""
    from .export_dict import link_of
    m = link_of(wid)
    return {"url": m["u"], "plat": m["p"]} if m else {}


def compute():
    """→ (daily {작품: {날짜: 언급 수}}, 제목 수). 같은 실행 안에서는 한 번만 계산"""
    if "r" in _CACHE:
        return _CACHE["r"]
    aliases = read_json(ALIASES, {})
    m = Matcher(aliases)
    seen = set()                              # (작품, 날짜, 작성자)
    daily = defaultdict(lambda: defaultdict(int))   # 작품 → 날짜 → 언급 수
    titles = load_titles()
    for row in titles.values():
        day = row["date"][:10]
        who = row.get("writer") or row["no"]
        for wid in m.find(row["title"]):
            key = (wid, day, who)
            if key not in seen:
                seen.add(key)
                daily[wid][day] += 1
    _CACHE["r"] = (daily, len(titles))
    return _CACHE["r"]


def run(top_n=100, trend_n=6):
    t0 = time.time()
    works = read_json(WORKS, {})
    daily, n_titles = compute()
    # 월별·분기별
    periods = defaultdict(lambda: defaultdict(int))  # 기간 → 작품 → 수
    series = defaultdict(lambda: defaultdict(int))   # 작품 → 월 → 수
    for wid, days in daily.items():
        for day, n in days.items():
            mon = day[:7]
            periods[mon][wid] += n
            periods[quarter_of(mon)][wid] += n
            series[wid][mon] += n
    months = sorted({p for p in periods if "Q" not in p})
    out = {"generated": now_kst().strftime("%Y-%m-%d %H:%M"), "titles": n_titles, "months": months,
           "periods": {}}
    # 완결 여부·완결일은 완결 탭 판정(data/statuses.json, aggregate가 먼저 만듦)을 그대로 쓴다.
    # 완결 = 판정이 완결·예전 완결이거나 작품 정보가 완결. 이 기간 완결 = 판정 '완결'이고 완결일이 그 기간 안.
    statuses = read_json(DATA / "statuses.json", {})

    def done(wid):
        return statuses.get(wid, {}).get("status") in ("완결", "예전 완결") or works.get(wid, {}).get("status") == "완결"

    def cdate(wid):
        st = statuses.get(wid, {})
        return st.get("date") if st.get("status") == "완결" else None

    def in_period(wid, p):
        d = cdate(wid)
        return bool(d) and (quarter_of(d[:7]) == p if "Q" in p else d[:7] == p)

    for p, counts in periods.items():
        ranked = sorted(counts.items(), key=lambda x: -x[1])
        # 전체 상위 N + 완결작 상위 N + 이 기간 완결작 전부 (언급 탭 필터용)
        keep = {wid for wid, _ in ranked[:top_n]}
        keep |= {wid for wid, _ in [x for x in ranked if done(x[0])][:top_n]}
        keep |= {wid for wid, _ in ranked if in_period(wid, p)}
        out["periods"][p] = [{"id": wid, "title": works.get(wid, {}).get("title", wid), "n": n,
                              "status": "완결" if done(wid) else works.get(wid, {}).get("status", ""),
                              "done": done(wid), "cdate": cdate(wid), "new": in_period(wid, p),
                              "series": [series[wid].get(mm, 0) for mm in months], **_link(wid)}
                             for wid, n in ranked if wid in keep]
    # 추이: 전체 기간 언급 수 상위 작품의 월별 언급 수
    total = sorted(series.items(), key=lambda x: -sum(x[1].values()))[:trend_n]
    out["trend"] = [{"id": wid, "title": works.get(wid, {}).get("title", wid),
                     "series": [ser.get(mm, 0) for mm in months]} for wid, ser in total]
    write_json(SITE_DATA / "mentions.json", out)
    print(f"언급 집계: 제목 {n_titles:,}개, 작품 {len(daily)}개, {time.time() - t0:.0f}초")
    return out


if __name__ == "__main__":
    run()
