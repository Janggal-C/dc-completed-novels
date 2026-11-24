"""AI 판정 + 줄임말 사전 갱신.

1) AI 판정이 필요한데 아직 없는 글을 모아 묶음으로 판정 (같은 제목은 캐시 재사용)
2) 완결로 판정된 글의 작품명 중 사전에 없는 것을 모아 웹 검색 → 사전에 추가
한도(사용량)에 걸리면 그 자리에서 멈추고, 남은 건 다음 실행 때 처리한다.
"""
import sys
from datetime import datetime, timedelta

from . import ai
from .common import (AI_DIR, ALIASES, POSTS_DIR, REVIEW_DIR, SEARCH_CACHE, WORKS, checkpoint, load_config,
                     load_monthly, merge_monthly, norm_key, now_kst, read_json, write_json)
from .resolve import decide, load_overrides, load_reviews, needs_ai, resolve_id, work_name


def add_work(works, aliases, title, alias=None, **info):
    wid = norm_key(title)
    if not wid:
        return None
    w = works.setdefault(wid, {"title": title, "added": now_kst().strftime("%Y-%m-%d")})
    for k, v in info.items():
        if v and not w.get(k):
            w[k] = v
    aliases.setdefault(wid, wid)
    if alias and norm_key(alias):
        aliases.setdefault(norm_key(alias), wid)
    return wid


def run(cfg=None):
    cfg = cfg or load_config()
    jc = cfg["judge"]
    posts = load_monthly(POSTS_DIR)
    results = load_monthly(AI_DIR)
    overrides = load_overrides()
    works = read_json(WORKS, {})
    aliases = read_json(ALIASES, {})
    cache = read_json(SEARCH_CACHE, {})
    stats = {"ai_judged": 0, "ai_cached": 0, "searched": 0, "found": 0, "stopped": ""}

    # ---- 1) AI 판정 ----
    by_title = {}
    for r in results.values():
        p = posts.get(r["no"])
        if p:
            by_title.setdefault(norm_key(p["title"]), r)
    todo, reuse = [], []
    for p in sorted(posts.values(), key=lambda p: -p["no"]):   # 최신 글 우선
        if p["no"] in results or not needs_ai(p, jc["mode"], jc["economy_sample_rate"]):
            continue
        hit = by_title.get(norm_key(p["title"]))
        if hit:
            reuse.append({**{k: hit[k] for k in ("label", "work", "guess")},
                          "no": p["no"], "date": p["date"], "cached": True})
        else:
            todo.append(p)
    todo = todo[: jc["max_titles_per_run"]]
    new_rows = reuse
    stats["ai_cached"] = len(reuse)
    for i in range(0, len(todo), jc["batch_size"]):
        batch = todo[i:i + jc["batch_size"]]
        try:
            res = ai.classify_titles([{"no": p["no"], "title": p["title"]} for p in batch], jc["model"])
        except ai.AIError as e:
            stats["stopped"] = str(e)
            print(f"⚠️ AI 판정 중단 (다음 실행 때 이어감): {e}", file=sys.stderr)
            break
        for p in batch:
            if p["no"] in res:
                new_rows.append({**res[p["no"]], "no": p["no"], "date": p["date"]})
                stats["ai_judged"] += 1
        merge_monthly(AI_DIR, new_rows)   # 묶음마다 저장 → 중간에 멈춰도 손실 없음
        new_rows = []
        print(f"  AI 판정 {stats['ai_judged']}/{len(todo)}건", flush=True)
        checkpoint(f"AI 판정 중간 저장 {stats['ai_judged']}건")
    merge_monthly(AI_DIR, new_rows)
    results = load_monthly(AI_DIR)

    # ---- 1.5) 규칙·AI 불일치 → 상위 모델로 AI 검수 ----
    stats["reviewed"] = 0
    if not stats["stopped"]:
        done = load_monthly(REVIEW_DIR)
        todo = []
        for p in sorted(posts.values(), key=lambda p: -p["no"]):
            if p["no"] in done or p["no"] in overrides:
                continue
            d = decide(p, results.get(p["no"]), None)
            if d["disagree"]:
                todo.append({"no": p["no"], "title": p["title"], "rule": d["rule"], "ai": d["ai"], "date": p["date"]})
        todo = todo[: jc["review_per_run"]]
        for i in range(0, len(todo), 30):
            batch = todo[i:i + 30]
            try:
                res = ai.review_titles(batch, jc["review_model"])
            except ai.AIError as e:
                stats["stopped"] = str(e)
                print(f"⚠️ AI 검수 중단: {e}", file=sys.stderr)
                break
            merge_monthly(REVIEW_DIR, [{**res[b["no"]], "no": b["no"], "date": b["date"]} for b in batch if b["no"] in res])
            stats["reviewed"] += sum(b["no"] in res for b in batch)
        print(f"  AI 검수 {stats['reviewed']}건", flush=True)
    overrides = load_reviews()

    # ---- 2) 사전 갱신 ----
    for no, ov in overrides.items():          # 검수에서 적은 정식 제목은 바로 사전에
        if ov.get("work_title"):
            add_work(works, aliases, ov["work_title"], source="검수")
    unknown = {}
    for p in posts.values():
        r = results.get(p["no"])
        d = decide(p, r, overrides.get(p["no"]))
        if d["label"] != "complete":
            continue
        name, guess = work_name(p, r, overrides.get(p["no"]))
        if not norm_key(name) or resolve_id(name, guess, aliases):
            continue
        if guess and norm_key(guess) in aliases:
            aliases[norm_key(name)] = aliases[norm_key(guess)]
            continue
        u = unknown.setdefault(norm_key(name), {"alias": name, "titles": [], "n": 0})
        u["n"] += 1
        if len(u["titles"]) < 3:
            u["titles"].append(p["title"])

    today = now_kst()
    retry = timedelta(days=jc["search_retry_days"])
    queue = []
    for key, u in sorted(unknown.items(), key=lambda kv: -kv[1]["n"]):
        c = cache.get(key)
        if c and today - datetime.fromisoformat(c["checked"]).replace(tzinfo=today.tzinfo) < retry:
            continue
        queue.append(u)
    queue = queue[: jc["search_per_run"]]
    sb = jc["search_batch_size"]
    for i in range(0, len(queue), sb):
        batch = queue[i:i + sb]
        try:
            res = ai.search_aliases([(u["alias"], u["titles"]) for u in batch], jc["model"])
        except ai.AIError as e:
            stats["stopped"] = stats["stopped"] or str(e)
            print(f"⚠️ 줄임말 검색 중단: {e}", file=sys.stderr)
            break
        for u in batch:
            stats["searched"] += 1
            r = res.get(u["alias"]) or {}
            key = norm_key(u["alias"])
            if r.get("found") and r.get("title"):
                wid = add_work(works, aliases, r["title"], alias=u["alias"], author=r.get("author"),
                               platform=r.get("platform"), source=r.get("url"))
                if r.get("confidence") != "high" and wid:
                    works[wid]["needs_review"] = True
                stats["found"] += 1
                cache.pop(key, None)
            else:
                cache[key] = {"alias": u["alias"], "checked": today.strftime("%Y-%m-%d"),
                              "examples": u["titles"]}

    write_json(WORKS, works)
    write_json(ALIASES, aliases)
    write_json(SEARCH_CACHE, cache)
    print(f"판정 완료: AI {stats['ai_judged']}건 (캐시 재사용 {stats['ai_cached']}건), "
          f"줄임말 검색 {stats['searched']}건 중 {stats['found']}건 찾음")
    return stats


if __name__ == "__main__":
    run()
