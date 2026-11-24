"""작품별 완결 상태와 완결일 판정 (AI·검색 없이 계산만).

근거
- 완결 글(C): '완결됐다'로 판정된 제목
- 반대 증거(Q): 같은 작품의 '완결 아님' 제목 ("언제 완결?", "완결나면 볼거임" 등)
- 공식 상태: 구글 검색 결과에서 뽑은 연재처 표시(완결/연재중). 있으면 최우선

판정
1) 완결 버스트: 3일 안에 서로 다른 작성자 3명 이상이 '완결'을 언급한 구간.
   여러 번이면 가장 큰 버스트의 30% 이상인 것 중 가장 이른 것 (외전 완결이 본편을 덮지 않게)
   → 버스트 뒤 30일 동안 반대 증거가 적으면 '완결', 많으면 '보류'
2) 버스트 없음: 완결 글 비율이 60% 이상이고 작성자 3명 이상 → '예전 완결' (데이터 이전에 완결된 작품)
3) 반대 증거가 압도적 → '연재중'
4) 그 외(근거 2명 이하 등) → '보류'
'완결'·'예전 완결'만 완결작 순위에 들어가고, 완결일 이후 글만 센다.
"""
from datetime import date

COUNTED = ("완결", "예전 완결")


def _d(s):
    return date.fromisoformat(s[:10])


def judge(c_posts, q_posts, official=None, data_start=None, cfg=None):
    cfg = cfg or {}
    win = cfg.get("burst_days", 3)
    min_w = cfg.get("burst_min_writers", 3)
    rel = cfg.get("burst_relative", 0.3)
    after_days = cfg.get("after_days", 30)
    after_ratio = cfg.get("after_q_ratio", 0.3)
    old_ratio = cfg.get("old_complete_ratio", 0.6)

    c = sorted(c_posts, key=lambda p: p["date"])
    writers = {p["writer"] for p in c}
    out = {"status": "보류", "date": c[0]["date"][:10] if c else None, "reason": "",
           "writers": len(writers), "c": len(c), "q": len(q_posts), "official": official or ""}

    # 버스트 찾기
    sizes = []
    for p in c:
        d0 = _d(p["date"])
        ws = {x["writer"] for x in c if 0 <= (_d(x["date"]) - d0).days < win}
        sizes.append((d0, len(ws)))
    peak = max((n for _, n in sizes), default=0)
    sig = sorted(d0 for d0, n in sizes if n >= min_w and n >= rel * peak)

    if sig:
        bd = sig[0]
        out["date"] = bd.isoformat()
        out["burst"] = max(n for d0, n in sizes if d0 == bd)
        a_c = sum(1 for p in c if 0 <= (_d(p["date"]) - bd).days < after_days)
        a_q = sum(1 for p in q_posts if 0 <= (_d(p["date"]) - bd).days < after_days)
        if a_q <= max(2, after_ratio * a_c):
            out["status"], out["reason"] = "완결", f"{bd:%m/%d}부터 3일간 {out['burst']}명이 완결 언급"
        else:
            out["status"], out["reason"] = "보류", f"완결 언급이 몰렸지만 이후에도 '언제 완결' 글 {a_q}개"
    else:
        ratio = len(c) / max(1, len(c) + len(q_posts))
        if len(writers) >= 3 and ratio >= old_ratio:
            out["status"], out["reason"] = "예전 완결", f"완결 글 비율 {ratio:.0%}, 몰린 시점 없음"
        elif ratio < 0.4 and len(q_posts) >= 3:
            out["status"], out["reason"] = "연재중", f"완결 글 비율 {ratio:.0%} ('언제 완결' 글 {len(q_posts)}개)"
        else:
            out["reason"] = f"근거 부족 (작성자 {len(writers)}명, 완결 글 비율 {ratio:.0%})"

    # 공식 상태(연재처 표시)가 있으면 우선
    if official == "연재중":
        out["status"], out["reason"] = "연재중", "연재처 표시: 연재중"
    elif official == "완결" and out["status"] not in COUNTED:
        out["status"] = "완결" if sig else "예전 완결"
        out["reason"] = "연재처 표시: 완결"

    # 데이터 시작 직후의 완결은 그 전에 이미 완결됐을 수 있음
    if data_start and out["date"] and out["status"] in COUNTED and (_d(out["date"]) - _d(data_start)).days < 7:
        out["before_start"] = True
    return out
