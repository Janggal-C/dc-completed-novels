"""대량 검색 (Serper 무료 2,500회 소진용). 매일 실행과 별개로 필요할 때만 돌린다.

처리 순서 (언급 많은 것부터)
  A. 이미 등록된 작품 중 연재처 상태(완결/연재중)를 모르는 것 → 상태 확인
  B. 사전에 없는 작품명(미확인) → 정식 제목 찾기
한 번 실행에 bulk.per_run 회까지, 누적 bulk.total_limit 회를 넘지 않는다.
구글 결과는 haiku가 10개씩 묶어서 읽는다 (호출 수 절약).
"""
import sys
from collections import defaultdict

from . import ai, google
from .common import (AI_DIR, ALIASES, AUTHORS, POSTS_DIR, SEARCH_CACHE, WORKS, checkpoint, load_config,
                     load_monthly, norm_key, now_kst, read_json, write_json)
from .judge import add_work, save_alias_dates, set_status
from .resolve import decide, load_reviews, not_a_work, resolve_id, work_name


def collect():
    """작품별·미확인 이름별 언급 작성자 수"""
    posts = load_monthly(POSTS_DIR)
    results = load_monthly(AI_DIR)
    ov = load_reviews()
    aliases = read_json(ALIASES, {})
    known = defaultdict(set)
    unknown = {}
    for p in posts.values():
        r = results.get(p["no"])
        if decide(p, r, ov.get(p["no"]))["label"] not in ("complete", "not"):
            continue
        name, guess = work_name(p, r, ov.get(p["no"]))
        if not norm_key(name) or not_a_work(name):
            continue
        wid = resolve_id(name, guess, aliases)
        if wid:
            known[wid].add(p["writer"])
        else:
            u = unknown.setdefault(norm_key(name), {"alias": name, "titles": [], "writers": set()})
            u["writers"].add(p["writer"])
            if len(u["titles"]) < 3:
                u["titles"].append(p["title"])
    return known, unknown


def run():
    cfg = load_config()
    bc = cfg["bulk"]
    model = cfg["judge"]["model"]
    if not google.serper_available():
        print("SERPER_API_KEY 없음 → 대량 검색 건너뜀")
        return {}
    budget = min(bc["per_run"], google.serper_remaining(bc["total_limit"]))
    works = read_json(WORKS, {})
    aliases = read_json(ALIASES, {})
    cache = read_json(SEARCH_CACHE, {})
    authors = read_json(AUTHORS, [])
    known, unknown = collect()

    # 작업 목록: (종류, 이름, 예시 제목) — 언급 작성자 많은 순
    tasks = []
    for wid, ws in sorted(known.items(), key=lambda kv: -len(kv[1])):
        w = works.get(wid)
        if w and not w.get("status") and not w.get("status_checked"):
            tasks.append(("status", w["title"], [], wid))
    for k, u in sorted(unknown.items(), key=lambda kv: -len(kv[1]["writers"])):
        if cache.get(k, {}).get("via") == "serper" or len(u["writers"]) < bc.get("min_writers", 2):
            continue
        tasks.append(("alias", u["alias"], u["titles"], k))
    tasks = tasks[:budget]
    print(f"대량 검색: 이번 {len(tasks)}건 (상태 확인 {sum(t[0] == 'status' for t in tasks)}, "
          f"미확인 {sum(t[0] == 'alias' for t in tasks)}), Serper 남은 {google.serper_remaining(bc['total_limit'])}회",
          flush=True)

    stats = {"searched": 0, "found": 0, "status": 0, "authors": 0}
    today = now_kst().strftime("%Y-%m-%d")
    for i in range(0, len(tasks), bc["batch"]):
        batch = tasks[i:i + bc["batch"]]
        items = []
        for kind, name, ex, _ in batch:
            q = f"{name} 웹소설"
            try:
                items.append((name, ex, google.serper_search(q)))
                stats["searched"] += 1
            except Exception as e:
                print(f"  검색 실패 ({q}): {e}", file=sys.stderr)
                items.append((name, ex, []))
        try:
            res = ai.extract_from_results(items, model)
        except ai.AIError as e:
            print(f"⚠️ AI 오류: {e}", file=sys.stderr)
            if e.fatal:
                break
            continue
        for (kind, name, ex, key) in batch:
            r = res.get(name) or {}
            if kind == "status":
                works[key]["status_checked"] = today
                if r.get("status") in ("완결", "연재중"):
                    set_status(works, key, r["status"], "google-bulk")
                    stats["status"] += 1
                continue
            if r.get("is_author"):
                authors.append(name)
                stats["authors"] += 1
            elif r.get("found") and r.get("title"):
                wid = add_work(works, aliases, r["title"], alias=name, via="serper", author=r.get("author"),
                               platform=r.get("platform"), source=r.get("url"))
                if wid:
                    if r.get("confidence") != "high":
                        works[wid]["needs_review"] = True
                    set_status(works, wid, r.get("status"), "google-bulk")
                    stats["found"] += 1
                    cache.pop(key, None)
            else:
                cache[key] = {"alias": name, "checked": today, "examples": ex, "via": "serper"}
        write_json(WORKS, works)
        write_json(ALIASES, aliases)
        write_json(SEARCH_CACHE, cache)
        write_json(AUTHORS, sorted(set(authors)))
        save_alias_dates("serper")
        print(f"  {i + len(batch)}/{len(tasks)} 처리 · 찾음 {stats['found']} · 상태 {stats['status']} · 작가 {stats['authors']}",
              flush=True)
        checkpoint(f"대량 검색 중간 저장 {i + len(batch)}건")
    print(f"대량 검색 완료: {stats}")
    return stats


if __name__ == "__main__":
    run()
