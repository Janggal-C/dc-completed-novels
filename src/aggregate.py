"""전체 데이터로 보고서 JSON(docs/data/report.json)을 만든다. 매번 처음부터 다시 계산."""
from collections import defaultdict

from .common import (DATA, AI_DIR, ALIAS_DATES, ALIASES, AUTHORS, DICT, METRICS, POSTS_DIR, SEARCH_CACHE, SITE_DATA, STATE,
                     WORKS, load_config, load_monthly, norm_key, now_kst, quarter_of,
                     read_json, read_jsonl, write_json)
from .resolve import decide, load_reviews, resolve_id, work_name
from .rules import RULES_VERSION
from .status import COUNTED, judge as judge_status
from .matcher import Matcher


def _link(wid):
    """연재처 링크가 있으면 {"url", "plat"} (사이트에서 작품명을 링크로)"""
    from .export_dict import link_of
    m = link_of(wid)
    return {"url": m["u"], "plat": m["p"]} if m else {}


def run(cfg=None, run_stats=None, partial=False):
    cfg = cfg or load_config()
    rc = cfg["report"]
    posts = load_monthly(POSTS_DIR)
    results = load_monthly(AI_DIR)
    overrides = load_reviews()
    works = read_json(WORKS, {})
    aliases = read_json(ALIASES, {})
    state = read_json(STATE, {})

    matcher = Matcher(aliases)
    mentions = defaultdict(lambda: defaultdict(list))   # wid → month → [post]  (완결 글)
    against = defaultdict(list)                         # wid → ['완결 아님' 글] (반대 증거)
    review, pending = [], 0
    m = {"total": len(posts), "rule_decisive": 0, "both": 0, "agree": 0,
         "gold": 0, "rule_ok": 0, "ai_ok": 0, "ai_done": 0}
    unresolved = defaultdict(lambda: {"n": 0, "titles": []})

    for p in posts.values():
        r = results.get(p["no"])
        ov = overrides.get(p["no"])
        d = decide(p, r, ov)
        m["ai_done"] += bool(r)
        if d["rule"] != "ambiguous":
            m["rule_decisive"] += 1
            if r:
                m["both"] += 1
                m["agree"] += not d["disagree"]
        if d["disagree"]:
            item = {"no": p["no"], "title": p["title"], "date": p["date"][:10], "rule": d["rule"], "ai": d["ai"]}
            if ov and ov.get("label"):
                m["gold"] += 1
                m["rule_ok"] += d["rule"] == ov["label"]
                m["ai_ok"] += r["label"] == ov["label"]
                item.update(final=ov["label"], by=ov.get("by", "사람"), reason=ov.get("reason", ""))
            review.append(item)
        if d["label"] is None:
            pending += 1
        if d["label"] not in ("complete", "not"):
            continue
        # 한 제목에 여러 작품이 나오면 전부 센다: 사전 대조(matcher) + AI가 뽑은 이름
        wids = set(matcher.find(p["title"]))
        name, guess = work_name(p, r, ov)
        ai_wid = resolve_id(name, guess, aliases) if norm_key(name) else None
        if ai_wid:
            wids.add(ai_wid)
        elif norm_key(name) and not wids:
            key = norm_key(name)
            wids.add("?" + key)
            if d["label"] == "complete":
                u = unresolved[key]
                u["alias"] = name
                u["n"] += 1
                if len(u["titles"]) < 3:
                    u["titles"].append(p["title"])
        if d["label"] == "not":
            for wid in wids:
                against[wid].append(p)
            continue
        if not wids:
            m["no_work"] = m.get("no_work", 0) + 1   # 작품을 특정할 수 없는 완결 글 → 순위에서 제외
            continue
        for wid in wids:
            mentions[wid][p["date"][:7]].append(p)

    def title_of(wid):
        if wid.startswith("?"):
            return unresolved[wid[1:]]["alias"] + " (미확인)"
        return works.get(wid, {}).get("title", wid)

    first_day = min((p["date"][:10] for p in posts.values()), default=None)
    first_month = first_day[:7] if first_day else None

    # 작품별 완결 상태·완결일 (status.py)
    statuses = {}
    for wid in set(mentions) | set(against):
        c = [p for per in mentions.get(wid, {}).values() for p in per]
        if not c:
            continue
        statuses[wid] = judge_status(c, against.get(wid, []), works.get(wid, {}).get("status"),
                                     first_day, cfg.get("status", {}))
    # 완결작만, 완결일 이후의 언급만 센다.
    # 언급 = 전체 글 제목에서 사전 대조로 찾은 하루 단위 작성자 수 (언급 탭과 같은 기준).
    # 완결 글(C)은 완결 여부·완결일 판정에만 쓴다.
    # 작품별 완결 상태·완결일 저장 (소설넷 갱신 주기 등 다른 단계가 씀)
    write_json(DATA / "statuses.json", {w: {"status": st["status"], "date": st["date"]}
                                         for w, st in statuses.items() if not w.startswith("?")})
    from .mentions import compute as mention_daily
    daily, _ = mention_daily()
    counted = defaultdict(lambda: defaultdict(int))     # wid → month → 언급 수
    for wid, st in statuses.items():
        if wid.startswith("?") or st["status"] not in COUNTED:
            continue
        # 예전 완결(데이터 시작 전에 이미 완결) → 데이터 첫날부터 센다
        start = first_day if st["status"] == "예전 완결" else st["date"]
        if st["status"] == "예전 완결":
            st["date"] = first_day
        for day, n in daily.get(wid, {}).items():
            if day >= start:
                counted[wid][day[:7]] += n
    all_mentions = mentions
    months = sorted({mo for per in counted.values() for mo in per})
    completion = {wid: statuses[wid]["date"] for wid in counted}

    def entry(wid, n, period):
        w = works.get(wid, {})
        c_after = [p for per in all_mentions.get(wid, {}).values() for p in per if p["date"][:10] >= completion[wid]]
        best = sorted(c_after, key=lambda p: -p.get("replies", 0))[:3]
        return {"id": wid, "title": title_of(wid), "author": w.get("author", ""),
                "mentions": n, "writers": n,
                # 이 기간에 새로 완결 (데이터 이전에 완결된 '예전 완결'은 해당 없음)
                "new": statuses[wid]["status"] != "예전 완결" and (
                    (quarter_of(completion[wid][:7]) == period) if "Q" in period else (completion[wid][:7] == period)),
                "completion_date": completion[wid], "completion_month": completion[wid][:7],
                "status": statuses[wid]["status"], "status_reason": statuses[wid]["reason"],
                "before_start": bool(statuses[wid].get("before_start")),
                "unresolved": False, "needs_review": bool(w.get("needs_review")),
                "samples": [{"no": p["no"], "title": p["title"]} for p in best],
                "series": [counted[wid].get(mo, 0) for mo in months], **_link(wid)}

    def ranking(period_of):
        groups = defaultdict(lambda: defaultdict(int))
        for wid, per in counted.items():
            for mo, n in per.items():
                groups[period_of(mo)][wid] += n
        out = {}
        for period, by_work in groups.items():
            rows = [entry(wid, n, period) for wid, n in by_work.items()]
            rows.sort(key=lambda e: (-e["mentions"], e["title"]))
            # 상위 N개 + 그 기간에 새로 완결된 작품은 순위 밖이어도 전부 (필터용)
            out[period] = rows[: rc["top_n"]] + [e for e in rows[rc["top_n"]:] if e["new"]]
        return dict(sorted(out.items(), reverse=True))

    monthly = ranking(lambda mo: mo)
    quarterly = ranking(quarter_of)

    totals = sorted(counted, key=lambda w: -sum(counted[w].values()))
    trend = [{"id": w, "title": title_of(w), "series": [counted[w].get(mo, 0) for mo in months]}
             for w in totals][: rc["trend_top_n"]]

    pct = lambda a, b: round(100 * a / b, 1) if b else None
    metrics = {
        "total_posts": m["total"], "ai_done": m["ai_done"], "pending": pending,
        "rule_coverage": pct(m["rule_decisive"], m["total"]),
        "agreement": pct(m["agree"], m["both"]), "compared": m["both"],
        "gold": m["gold"], "rule_accuracy": pct(m["rule_ok"], m["gold"]),
        "ai_accuracy": pct(m["ai_ok"], m["gold"]), "review_open": sum("final" not in x for x in review), "no_work": m.get("no_work", 0),
        "rules_version": RULES_VERSION, "mode": cfg["judge"]["mode"],
    }
    history = read_jsonl(METRICS)
    if run_stats is not None:
        history.append({"date": now_kst().strftime("%Y-%m-%d %H:%M"), **metrics, **run_stats})
        with open(METRICS, "a", encoding="utf-8") as f:
            import json
            f.write(json.dumps(history[-1], ensure_ascii=False) + "\n")

    cache = read_json(SEARCH_CACHE, {})
    dictionary = sorted(
        [{"alias": a, "title": works.get(w, {}).get("title", w), "author": works.get(w, {}).get("author", ""),
          "needs_review": bool(works.get(w, {}).get("needs_review")), **_link(w)}
         for a, w in aliases.items() if a != w],
        key=lambda d: d["alias"])
    # 줄임말 사전·구글 검색 지표
    from datetime import timedelta as _td
    now = now_kst()
    dates = read_json(ALIAS_DATES, {})
    week_ago = (now - _td(days=7)).strftime("%Y-%m-%d")
    recent = sorted(((k, v) for k, v in dates.items() if k in aliases), key=lambda kv: kv[1]["date"], reverse=True)
    usage = read_json(DICT / "search_usage.json", {})
    jc = cfg["judge"]
    dict_stats = {
        "aliases": sum(1 for a, w in aliases.items() if a != w),
        "works": len(works),
        "authors": len(read_json(AUTHORS, [])),
        "unresolved": len(unresolved),
        "unresolved_ranked": sum(1 for u in unresolved.values() if u["n"] >= 2),
        "new_today": sum(1 for _, v in recent if v["date"] == now.strftime("%Y-%m-%d")),
        "new_week": sum(1 for _, v in recent if v["date"] >= week_ago),
        "needs_review": sum(1 for w in works.values() if w.get("needs_review")),
        "recent": [{"alias": k, "title": works.get(aliases[k], {}).get("title", ""), "date": v["date"], "via": v["via"]}
                   for k, v in recent[:30]],
    }
    google_stats = {
        "month": usage.get(now.strftime("%Y-%m"), 0), "today": usage.get(now.strftime("%Y-%m-%d"), 0),
        "month_limit": jc.get("google_monthly_limit", 0), "day_limit": jc.get("google_daily_limit", 0),
        "free_quota": 250,
        "daily": sorted([[k, v] for k, v in usage.items() if len(k) == 10])[-14:],
    }
    # 완결 목록에서 빠진 작품 (연재중·보류) — 확인용
    excluded = sorted(
        [{"title": title_of(w) if not w.startswith("?") else w[1:] + " (미확인)", "status": st["status"], "reason": st["reason"],
          "writers": st["writers"], "c": st["c"], "q": st["q"]}
         for w, st in statuses.items() if st["status"] not in COUNTED and st["writers"] >= 2],
        key=lambda x: (-x["writers"], x["title"]))
    status_counts = defaultdict(int)
    for st in statuses.values():
        if st["writers"] >= 2:
            status_counts[st["status"]] += 1
    report = {
        "updated": now_kst().strftime("%Y-%m-%d %H:%M"),
        "status_counts": dict(status_counts), "excluded": excluded[:150],
        "dict_stats": dict_stats, "google": google_stats,
        "repo": "Janggal-C/dc-completed-novels",
        "gallery": cfg["gallery_id"],
        "data_start": first_month,
        "reports_done": read_json(DICT / "reports_done.json", []),
        "backfill_done": state.get("backfill", {}).get("done", False),
        "backfill_cutoff": state.get("backfill", {}).get("cutoff"),
        "in_progress": partial,
        "months": months, "monthly": monthly, "quarterly": quarterly, "trend": trend,
        "metrics": metrics, "history": history[-60:],
        "review": sorted(review, key=lambda r: -r["no"])[:300],
        "unresolved": sorted([{"key": k, **v} for k, v in unresolved.items()], key=lambda u: -u["n"])[:200],
        "not_found": sorted(cache.values(), key=lambda c: c["checked"], reverse=True)[:200],
        "dictionary": dictionary,
    }
    write_json(SITE_DATA / "report.json", report)
    try:
        from . import export_dict
        export_dict.run()          # 확장 프로그램용 사전 (docs/api/dict.json)
    except Exception as e:
        print(f"사전 공개 파일 생성 실패: {e}")
    print(f"보고서 생성: {len(months)}개월, 작품 {len(mentions)}개, AI 검수 대기 {sum("final" not in x for x in review)}건")
    return report


if __name__ == "__main__":
    run()
