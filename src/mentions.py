"""언급 집계: 완결 여부와 상관없이 작품별 언급 수 (월별·분기별)

언급 수 = 하루 단위 작성자 수. 같은 사람이 같은 날 같은 작품을 여러 번 써도 1, 다음 날 또 쓰면 다시 1.
전체 제목(data/titles)에 줄임말 사전을 대조해서 센다 (AI·검색 없음).
결과: docs/data/mentions.json (배포 때 생성, 저장소에는 안 올림)
"""
import time
from collections import defaultdict

from .common import ALIASES, WORKS, quarter_of, read_json, write_json, SITE_DATA, now_kst
from .fullcrawl import load_titles
from .matcher import Matcher


def run(top_n=100, trend_n=6):
    t0 = time.time()
    works = read_json(WORKS, {})
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
    out = {"generated": now_kst().strftime("%Y-%m-%d %H:%M"), "titles": len(titles), "months": months,
           "periods": {}}
    for p, counts in periods.items():
        top = sorted(counts.items(), key=lambda x: -x[1])[:top_n]
        out["periods"][p] = [{"id": wid, "title": works.get(wid, {}).get("title", wid), "n": n,
                              "status": works.get(wid, {}).get("status", ""),
                              "series": [series[wid].get(mm, 0) for mm in months]} for wid, n in top]
    # 추이: 전체 기간 언급 수 상위 작품의 월별 언급 수
    total = sorted(series.items(), key=lambda x: -sum(x[1].values()))[:trend_n]
    out["trend"] = [{"id": wid, "title": works.get(wid, {}).get("title", wid),
                     "series": [ser.get(mm, 0) for mm in months]} for wid, ser in total]
    write_json(SITE_DATA / "mentions.json", out)
    print(f"언급 집계: 제목 {len(titles):,}개, 작품 {len(daily)}개, {time.time() - t0:.0f}초")
    return out


if __name__ == "__main__":
    run()
