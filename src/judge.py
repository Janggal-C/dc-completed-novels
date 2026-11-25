"""AI 판정 + 줄임말 사전 갱신.

1) AI 판정이 필요한데 아직 없는 글을 모아 묶음으로 판정 (같은 제목은 캐시 재사용)
2) 완결로 판정된 글의 작품명 중 사전에 없는 것을 모아 웹 검색 → 사전에 추가
한도(사용량)에 걸리면 그 자리에서 멈추고, 남은 건 다음 실행 때 처리한다.
"""
import sys
from datetime import datetime, timedelta

from . import ai, google
from .common import (AI_DIR, ALIASES, AUTHORS, RESEARCH_REQ, POSTS_DIR, REVIEW_DIR, SEARCH_CACHE, WORKS, checkpoint, load_config,
                     load_monthly, merge_monthly, norm_key, now_kst, read_json, write_json)
from .resolve import (decide, load_overrides, load_reviews, needs_ai, not_a_work, reload_authors,
                      resolve_id, work_name)


NEW_ALIASES = {}   # 이번 실행에서 새로 생긴 줄임말 → 경로(구글/AI/직접 입력)


def save_alias_dates(via="검색"):
    """새 줄임말의 등록일·경로를 dict/alias_dates.json 에 남긴다 (지표 탭 '신규 줄임말'용)"""
    from .common import ALIAS_DATES
    d = read_json(ALIAS_DATES, {})
    today = now_kst().strftime("%Y-%m-%d")
    for k, v in NEW_ALIASES.items():
        d.setdefault(k, {"date": today, "via": v or via})
    write_json(ALIAS_DATES, d)
    NEW_ALIASES.clear()


def set_status(works, wid, status, source="google"):
    """연재처 표시(완결/연재중)를 작품에 기록. 완결은 되돌리지 않음"""
    if wid and status in ("완결", "연재중") and works.get(wid, {}).get("status") != "완결":
        works[wid]["status"] = status
        works[wid]["status_source"] = source
        works[wid]["status_checked"] = now_kst().strftime("%Y-%m-%d")


def add_work(works, aliases, title, alias=None, via=None, force=False, **info):
    """작품 등록 + 줄임말 연결. force=True면 기존 연결을 덮어씀(사용자 직접 입력)"""
    wid = norm_key(title)
    if not wid or wid in ("작가명", "작가", "작품명", "제목"):
        return None
    if alias and not force:
        from .resolve import removed
        if norm_key(alias) in removed():     # 검수 탭에서 '제거'한 단어
            return None
    src = info.get("source") or ""
    if src.startswith("http") and wid not in works:
        same = next((k for k, w in works.items() if w.get("source") == src), None)
        if same:            # 같은 작품 페이지 = 제목만 바뀐 같은 작품
            wid = same
    w = works.setdefault(wid, {"title": title, "added": now_kst().strftime("%Y-%m-%d")})
    for k, v in info.items():
        if v and not w.get(k):
            w[k] = v
    aliases.setdefault(wid, wid)
    if alias and norm_key(alias):
        k = norm_key(alias)
        if k not in aliases or (force and aliases[k] != wid):
            NEW_ALIASES[k] = via
        if force:
            aliases[k] = wid
        else:
            aliases.setdefault(k, wid)
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
            print(f"⚠️ AI 판정 오류: {e}", file=sys.stderr)
            if e.fatal:
                stats["stopped"] = str(e)
                break
            continue
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
                print(f"⚠️ AI 검수 오류: {e}", file=sys.stderr)
                if e.fatal:
                    stats["stopped"] = str(e)
                    break
                continue
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
        u = unknown.setdefault(norm_key(name), {"alias": name, "titles": [], "n": 0, "writers": set()})
        u["n"] += 1
        u["writers"].add(p.get("writer"))
        if len(u["titles"]) < 3:
            u["titles"].append(p["title"])

    authors_list = read_json(AUTHORS, [])
    today = now_kst()
    retry = timedelta(days=jc["search_retry_days"])

    # 집중 재검색 요청이 있으면: 언급 많은 미확인 N개를 검색어를 바꿔(노벨피아·작가) 구글로 다시 찾는다
    req = read_json(RESEARCH_REQ, None)
    if req and google.available():
        top = sorted(unknown.values(), key=lambda u: (-len(u["writers"]), -u["n"]))[: req.get("top", 10)]
        budget = google.remaining(jc["google_monthly_limit"], jc["google_daily_limit"])
        items = []
        for u in top[:budget]:                     # 이름당 1회, 오늘 남은 한도까지만
            q = f'{u["alias"]} 노벨피아 웹소설 작가'
            try:
                items.append((u["alias"], u["titles"], google.search(q, num=8)))
                stats["google"] = stats.get("google", 0) + 1
            except Exception as e:
                print(f"  구글 검색 실패 ({q}): {e}", file=sys.stderr)
        try:
            for i in range(0, len(items), 5):
                res = ai.extract_from_results(items[i:i + 5], jc.get("search_model", jc["model"]))
                for a, ex, _ in items[i:i + 5]:
                    r = res.get(a) or {}
                    key = norm_key(a)
                    stats["searched"] += 1
                    if r.get("is_author"):
                        if a not in authors_list:
                            authors_list.append(a)
                        unknown.pop(key, None)
                        print(f"  작가로 분류: {a}", flush=True)
                    elif r.get("found") and r.get("title"):
                        wid = add_work(works, aliases, r["title"], alias=a, via="google", author=r.get("author"),
                                       platform=r.get("platform"), source=r.get("url"))
                        set_status(works, wid, r.get("status"))
                        if r.get("confidence") != "high" and wid:
                            works[wid]["needs_review"] = True
                        stats["found"] += 1
                        unknown.pop(key, None)
                        print(f"  찾음: {a} → {r['title']}", flush=True)
                    else:
                        cache[key] = {"alias": a, "checked": today.strftime("%Y-%m-%d"), "examples": ex, "via": "google2"}
                        print(f"  못 찾음: {a}", flush=True)
            RESEARCH_REQ.unlink(missing_ok=True)
        except ai.AIError as e:
            print(f"⚠️ 집중 재검색 오류: {e}", file=sys.stderr)
        write_json(AUTHORS, sorted(set(authors_list)))
        reload_authors()
        unknown = {k: u for k, u in unknown.items() if not not_a_work(u["alias"])}
    queue = []
    for key, u in sorted(unknown.items(), key=lambda kv: -kv[1]["n"]):
        c = cache.get(key)
        recent = c and today - datetime.fromisoformat(c["checked"]).replace(tzinfo=today.tzinfo) < retry
        # AI 검색으로 못 찾은 이름도 구글이 생기면 다시 시도
        if recent and (c.get("via") in ("google", "google2") or not google.available() or len(u["writers"]) < jc["google_min_writers"]):
            continue
        queue.append(u)
    # 구글(SerpApi): 순위에 영향을 주는 이름(작성자 여러 명)부터, 월 무료 한도 안에서만
    google_q, rest = [], []
    if google.available() and not req:
        budget = google.remaining(jc["google_monthly_limit"], jc["google_daily_limit"])
        for u in queue:
            if len(google_q) < budget and len(u["writers"]) >= jc["google_min_writers"]:
                google_q.append(u)
            else:
                rest.append(u)
    elif not google.available():
        rest = queue
    if google.available() and not jc.get("ai_search_fallback", False):
        rest = []   # 오늘 구글 한도에 못 든 이름은 그냥 미확인으로 두고 다음 날 다시 (토큰 절약)
    batches = []
    for i in range(0, len(google_q), 5):
        batches.append(("google", google_q[i:i + 5]))
    rest = rest[: max(0, jc["search_per_run"] - len(google_q))]
    sb = jc["search_batch_size"]
    for i in range(0, len(rest), sb):
        batches.append(("ai", rest[i:i + sb]))
    stats.setdefault("google", 0)
    for kind, batch in batches:
        try:
            if kind == "google":
                items = []
                for u in batch:
                    try:
                        items.append((u["alias"], u["titles"], google.search(f'{u["alias"]} 웹소설')))
                        stats["google"] += 1
                    except Exception as e:   # 구글 검색 실패 → 결과 없이 넘김
                        print(f"  구글 검색 실패 ({u['alias']}): {e}", file=sys.stderr)
                        items.append((u["alias"], u["titles"], []))
                res = ai.extract_from_results(items, jc["model"])
                print(f"  구글 검색 {len(batch)}개 → 찾음 {sum(bool(r.get('found')) for r in res.values())}개", flush=True)
            else:
                res = ai.search_aliases([(u["alias"], u["titles"]) for u in batch], jc.get("search_model", jc["model"]))
        except ai.AIError as e:
            print(f"⚠️ 줄임말 검색 오류: {e}", file=sys.stderr)
            if e.fatal:
                stats["stopped"] = stats["stopped"] or str(e)
                break
            continue
        for u in batch:
            stats["searched"] += 1
            r = res.get(u["alias"]) or {}
            key = norm_key(u["alias"])
            if r.get("is_author"):
                authors_list.append(u["alias"])
                continue
            if r.get("found") and r.get("title"):
                wid = add_work(works, aliases, r["title"], alias=u["alias"], via=kind, author=r.get("author"),
                               platform=r.get("platform"), source=r.get("url"))
                if kind == "google":
                    set_status(works, wid, r.get("status"))
                if r.get("confidence") != "high" and wid:
                    works[wid]["needs_review"] = True
                stats["found"] += 1
                cache.pop(key, None)
            else:
                cache[key] = {"alias": u["alias"], "checked": today.strftime("%Y-%m-%d"),
                              "examples": u["titles"], "via": kind}
        write_json(WORKS, works)            # 검색 묶음마다 저장 → 중간에 오류가 나도 찾은 건 남음
        write_json(ALIASES, aliases)
        write_json(SEARCH_CACHE, cache)

    write_json(WORKS, works)
    write_json(ALIASES, aliases)
    write_json(SEARCH_CACHE, cache)
    write_json(AUTHORS, sorted(set(authors_list)))
    reload_authors()
    save_alias_dates()
    print(f"판정 완료: AI {stats['ai_judged']}건 (캐시 재사용 {stats['ai_cached']}건), "
          f"줄임말 검색 {stats['searched']}건 중 {stats['found']}건 찾음")
    return stats


if __name__ == "__main__":
    run()
