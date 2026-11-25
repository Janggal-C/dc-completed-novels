"""완결 데이터 1~5월 보강: 전체 제목 수집에서 '완결'이 들어간 제목을 완결 글 목록으로 가져와 AI(haiku)로 판정.

(예전엔 5월 말부터 '완결' 검색 크롤링만 있었음 → 이제 전체 제목에서 뽑으므로 1월부터 완결 판정 가능)
import: data/titles 의 '완결' 제목 중 data/posts 에 없는 것 → data/posts
judge : AI 판정 없는 완결 글 → data/ai  (묶음 60개, 묶음마다 저장)
"""
import sys

from . import ai
from .common import AI_DIR, POSTS_DIR, checkpoint, load_config, load_monthly, merge_monthly
from .fullcrawl import load_titles


def do_import():
    posts = load_monthly(POSTS_DIR)
    have = {int(k) for k in posts}
    rows = [{"date": r["date"], "no": int(r["no"]), "replies": r.get("replies", 0), "title": r["title"],
             "writer": r.get("writer", "")}
            for r in load_titles().values() if "완결" in r["title"] and int(r["no"]) not in have]
    merge_monthly(POSTS_DIR, rows)
    print(f"완결 글 {len(rows)}개 추가 (기존 {len(posts)}개)", flush=True)


def judge():
    jc = load_config()["judge"]
    posts = load_monthly(POSTS_DIR)
    done = {int(k) for k in load_monthly(AI_DIR)}
    todo = sorted((p for p in posts.values() if int(p["no"]) not in done), key=lambda p: p["no"])
    print(f"AI 판정 대상 {len(todo)}개", flush=True)
    n = 0
    for i in range(0, len(todo), jc["batch_size"]):
        batch = todo[i:i + jc["batch_size"]]
        try:
            res = ai.classify_titles([{"no": p["no"], "title": p["title"]} for p in batch], jc["model"])
        except ai.AIError as e:
            print(f"⚠️ {e}", file=sys.stderr)
            if e.fatal:
                break
            continue
        rows = [{**res[p["no"]], "no": p["no"], "date": p["date"]} for p in batch if p["no"] in res]
        merge_monthly(AI_DIR, rows)
        n += len(rows)
        print(f"  {n}/{len(todo)}", flush=True)
        checkpoint(f"완결 1~5월 AI 판정 {n}/{len(todo)}", every_seconds=300)


if __name__ == "__main__":
    {"import": do_import, "judge": judge}[sys.argv[1]]()
