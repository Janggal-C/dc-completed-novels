"""AI가 '작품명'으로 분류한 단어(data/word_labels.json, t=work) → 사전에 등록

(앞부분 일치로 기존 작품에 바로 연결하는 방식은 '게임속→게임 속 바바리안', '나이트→나이트런' 같은 오연결이 많아 쓰지 않음)
Serper 검색 "{단어} 웹소설" → haiku가 10개씩 묶어 정식 제목 추출 (예시 갤 제목 2개 같이 줌)
   - 작가 이름이면 작가 목록에, 못 찾으면 '못 찾음'으로 기록, 확신 낮으면 검수 필요 표시
처리 기록: data/word_resolve.json {단어: {r: linked|found|author|none, title?, date}}
"""
import sys

from . import ai, google
from .common import (ALIASES, AUTHORS, DATA, WORKS, checkpoint, load_config, norm_key, now_kst, read_json,
                     write_json)
from .judge import add_work, save_alias_dates, set_status

LABELS = DATA / "word_labels.json"
DONE = DATA / "word_resolve.json"


def todo():
    labels = read_json(LABELS, {})
    aliases = read_json(ALIASES, {})
    authors = {norm_key(a) for a in read_json(AUTHORS, [])}
    done = read_json(DONE, {})
    from .resolve import removed
    gone = removed()
    out = [(k, v) for k, v in labels.items()
           if v.get("t") == "work" and k not in done and norm_key(k) not in aliases and norm_key(k) not in authors
           and norm_key(k) not in gone]
    return sorted(out, key=lambda kv: -kv[1].get("w", 0))


def prefix_pass(items, works, aliases, done, today):
    """기존 작품 제목의 앞부분과 같은 단어는 검색 없이 연결"""
    titles = {wid: norm_key(w["title"]) for wid, w in works.items()}
    rest = []
    for word, v in items:
        k = norm_key(word)
        hits = [wid for wid, t in titles.items() if len(k) >= 3 and t.startswith(k) and t != k]
        if len(hits) == 1:
            aliases[k] = hits[0]
            done[word] = {"r": "linked", "title": works[hits[0]]["title"], "date": today}
        else:
            rest.append((word, v))
    return rest


def run(limit=None):
    cfg = load_config()
    bc = cfg["bulk"]
    model = cfg["judge"]["model"]
    works = read_json(WORKS, {})
    aliases = read_json(ALIASES, {})
    authors = read_json(AUTHORS, [])
    done = read_json(DONE, {})
    today = now_kst().strftime("%Y-%m-%d")
    items = todo()
    n0 = len(items)
    linked = 0
    print(f"작품 단어 {n0}개 검색 대상", flush=True)

    if not google.serper_available():
        print("SERPER_API_KEY 없음 → 검색 건너뜀"); return
    budget = google.serper_remaining(bc["total_limit"])
    if limit:
        budget = min(budget, limit)
    items = items[:budget]
    print(f"이번 검색 {len(items)}개 (Serper 남은 {google.serper_remaining(bc['total_limit'])}회)", flush=True)

    st = {"found": 0, "low": 0, "author": 0, "none": 0}
    for i in range(0, len(items), bc["batch"]):
        batch = items[i:i + bc["batch"]]
        q = []
        for word, v in batch:
            try:
                q.append((word, v.get("ex", []), google.serper_search(f"{word} 웹소설")))
            except Exception as e:
                print(f"  검색 실패 {word}: {e}", file=sys.stderr)
                q.append((word, v.get("ex", []), []))
        try:
            res = ai.extract_from_results(q, model)
        except ai.AIError as e:
            print(f"⚠️ AI 오류: {e}", file=sys.stderr)
            if e.fatal:
                break
            continue
        for word, v in batch:
            r = res.get(word) or {}
            if r.get("is_author"):
                authors.append(word); st["author"] += 1
                done[word] = {"r": "author", "date": today}
            elif r.get("found") and r.get("title"):
                wid = add_work(works, aliases, r["title"], alias=word, via="serper-word", author=r.get("author"),
                               platform=r.get("platform"), source=r.get("url"))
                if wid:
                    if r.get("confidence") != "high":
                        works[wid]["needs_review"] = True; st["low"] += 1
                    set_status(works, wid, r.get("status"), "google-bulk")
                    st["found"] += 1
                    done[word] = {"r": "found", "title": works[wid]["title"], "date": today}
                else:
                    done[word] = {"r": "none", "date": today}; st["none"] += 1
            else:
                done[word] = {"r": "none", "date": today}; st["none"] += 1
        write_json(WORKS, works); write_json(ALIASES, aliases); write_json(DONE, done)
        write_json(AUTHORS, sorted(set(authors)))
        save_alias_dates("serper-word")
        print(f"  {i + len(batch)}/{len(items)} · 찾음 {st['found']}(확인 필요 {st['low']}) · 작가 {st['author']} · 못 찾음 {st['none']}",
              flush=True)
        checkpoint(f"작품 단어 사전 등록 {i + len(batch)}/{len(items)}", every_seconds=300)
    print(f"완료: 바로 연결 {linked}, {st}")


def only(names):
    """지정한 단어만 다시 처리 (word_resolve 에서 지워둔 것)"""
    global todo
    base = todo
    todo = lambda: [(k, v) for k, v in base() if k in names]
    run()


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "only":
        only(set(sys.argv[2:])); sys.exit()
    if len(sys.argv) > 1 and sys.argv[1] == "dry":
        works = read_json(WORKS, {}); aliases = read_json(ALIASES, {}); done = {}
        items = todo(); rest = prefix_pass(items, works, aliases, done, "dry")
        print(len(items), "→ 바로 연결", len(done), "검색", len(rest))
        for w, d in list(done.items())[:40]:
            print(" ", w, "→", d["title"])
    else:
        run(int(sys.argv[1]) if len(sys.argv) > 1 else None)
