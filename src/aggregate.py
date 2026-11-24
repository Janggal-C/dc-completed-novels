"""전체 데이터로 보고서 JSON(docs/data/report.json)을 만든다. 매번 처음부터 다시 계산."""
from collections import defaultdict

from .common import (AI_DIR, ALIASES, METRICS, POSTS_DIR, SEARCH_CACHE, SITE_DATA, STATE,
                     WORKS, load_config, load_monthly, norm_key, now_kst, quarter_of,
                     read_json, read_jsonl, write_json)
from .resolve import decide, load_reviews, resolve_id, work_name
from .rules import RULES_VERSION


def run(cfg=None, run_stats=None, partial=False):
    cfg = cfg or load_config()
    rc = cfg["report"]
    posts = load_monthly(POSTS_DIR)
    results = load_monthly(AI_DIR)
    overrides = load_reviews()
    works = read_json(WORKS, {})
    aliases = read_json(ALIASES, {})
    state = read_json(STATE, {})

    mentions = defaultdict(lambda: defaultdict(list))   # wid → month → [post]
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
        if d["label"] != "complete":
            continue
        name, guess = work_name(p, r, ov)
        if not norm_key(name):
            m["no_work"] = m.get("no_work", 0) + 1   # 작품을 특정할 수 없는 완결 글 → 순위에서 제외
            continue
        wid = resolve_id(name, guess, aliases)
        if not wid:
            key = norm_key(name)
            wid = "?" + key
            u = unresolved[key]
            u["alias"] = name
            u["n"] += 1
            if len(u["titles"]) < 3:
                u["titles"].append(p["title"])
        mentions[wid][p["date"][:7]].append(p)

    def title_of(wid):
        if wid.startswith("?"):
            return unresolved[wid[1:]]["alias"] + " (미확인)"
        return works.get(wid, {}).get("title", wid)

    months = sorted({mo for per in mentions.values() for mo in per})
    first_month = min((p["date"][:7] for p in posts.values()), default=None)

    # 완결 추정 월: 고유 작성자 수가 기준 이상인 첫 달 (없으면 첫 언급 달)
    completion = {}
    for wid, per in mentions.items():
        cands = [mo for mo in sorted(per) if len({p["writer"] for p in per[mo]}) >= rc["min_writers_for_completion"]]
        completion[wid] = cands[0] if cands else min(per)

    def entry(wid, plist, period):
        writers = {p["writer"] for p in plist}
        best = sorted(plist, key=lambda p: -p.get("replies", 0))[:3]
        w = works.get(wid, {})
        return {"id": wid, "title": title_of(wid), "author": w.get("author", ""),
                "mentions": len(plist), "writers": len(writers),
                "new": completion[wid][:7] == period if len(period) == 7 else quarter_of(completion[wid]) == period,
                "completion_month": completion[wid],
                "unresolved": wid.startswith("?"), "needs_review": bool(w.get("needs_review")),
                "samples": [{"no": p["no"], "title": p["title"]} for p in best],
                # 이 작품의 월별 언급 작성자 수 (R.months 순서) → 순위 목록에서 펼쳐 보는 그래프용
                "series": [len({p["writer"] for p in mentions[wid].get(mo, [])}) for mo in months]}

    def ranking(period_of):
        groups = defaultdict(lambda: defaultdict(list))
        for wid, per in mentions.items():
            for mo, plist in per.items():
                groups[period_of(mo)][wid] += plist
        out = {}
        for period, by_work in groups.items():
            rows = [entry(wid, pl, period) for wid, pl in by_work.items()]
            rows.sort(key=lambda e: (-e["writers"], -e["mentions"], e["title"]))
            out[period] = rows[: rc["top_n"]]
        return dict(sorted(out.items(), reverse=True))

    monthly = ranking(lambda mo: mo)
    quarterly = ranking(quarter_of)

    totals = sorted(mentions, key=lambda w: -sum(len({p["writer"] for p in pl}) for pl in mentions[w].values()))
    trend = [{"id": w, "title": title_of(w),
              "series": [len({p["writer"] for p in mentions[w].get(mo, [])}) for mo in months]}
             for w in totals if not w.startswith("?")][: rc["trend_top_n"]]

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
          "needs_review": bool(works.get(w, {}).get("needs_review"))}
         for a, w in aliases.items() if a != w],
        key=lambda d: d["alias"])
    report = {
        "updated": now_kst().strftime("%Y-%m-%d %H:%M"),
        "gallery": cfg["gallery_id"],
        "data_start": first_month,
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
    print(f"보고서 생성: {len(months)}개월, 작품 {len(mentions)}개, AI 검수 대기 {sum("final" not in x for x in review)}건")
    return report


if __name__ == "__main__":
    run()
