"""매일 자동 실행 (사람 개입 없이). 각 단계는 실패해도 다음 단계로 넘어가고, 단계마다 저장한다.

1) 수집      : 새 글 제목 이어서 수집 + 빈 구간 메우기
2) 완결 판정 : 새 '완결' 제목 → 규칙 + haiku, 엇갈리면 sonnet
   순위      : 노벨피아 24시간 순위 제목을 누적 (줄임말 후보·충돌 확인용, data/ranking_history.json)
3) 새 단어   : 작성자 10명·3일 이상 쓰인 새 단어 → haiku 분류 (하루 최대 300개)
4) 구글 검색 : 하루 한도를 우선순위로 — 새 작품 단어(정식 제목) / 연재처 링크 없는 작품, 최근 언급 많은 순
5) AI 검수   : 새 줄임말·확인 필요 → 중구난방 검사 + sonnet 판정
6) 오류 신고 : 확장 신고 → sonnet 판단 → 자동 반영
7) 소설넷    : 새 작품 평점·연재처 + 기존 1/7 갱신 (최대 40분)
보고서·확장 사전은 이 작업이 끝나면 '보고서 페이지 배포'가 만들어 올린다.
결과 요약: data/daily_log.jsonl
"""
import json
import sys
import time
import traceback

from .common import DATA, checkpoint, now_kst

STEPS = []


def step(name):
    def deco(fn):
        STEPS.append((name, fn))
        return fn
    return deco


@step("수집")
def s_crawl():
    from . import fullcrawl
    fullcrawl.run(max_minutes=30)
    fullcrawl.fill_gaps()


@step("완결 판정")
def s_complete():
    from . import backfill
    backfill.do_import()
    backfill.judge()
    backfill.review()


@step("순위")
def s_ranking():
    from . import ranking_fetch
    ranking_fetch.run()


@step("새 단어")
def s_discover():
    from . import discover
    discover.run(max_minutes=20, limit=300)


@step("구글 검색")
def s_google():
    # 하루 검색 한도를 새 작품 단어(정식 제목)·연재처 링크 중 언급 많은 순으로 나눠 씀
    from . import googleplan
    googleplan.run()


@step("AI 검수")
def s_audit():
    from . import autoreview
    autoreview.audit()


@step("오류 신고")
def s_reports():
    from . import autoreview
    autoreview.reports()


@step("소설넷")
def s_ssn():
    from . import aggregate, ssn
    aggregate.run()          # 작품별 완결 상태(data/statuses.json) 최신화 → 갱신 주기 판단에 씀
    ssn.run(max_minutes=40)


def main(only=None):
    log = {"date": now_kst().strftime("%Y-%m-%d %H:%M"), "steps": {}}
    for name, fn in STEPS:
        if only and name not in only:
            continue
        t0 = time.time()
        print(f"\n===== {name} =====", flush=True)
        try:
            fn()
            log["steps"][name] = {"ok": True, "sec": round(time.time() - t0)}
        except Exception as e:
            traceback.print_exc()
            log["steps"][name] = {"ok": False, "sec": round(time.time() - t0), "error": f"{type(e).__name__}: {e}"[:300]}
        checkpoint(f"매일 실행: {name}", force=True)
    with open(DATA / "daily_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log, ensure_ascii=False) + "\n")
    checkpoint("매일 실행 완료", force=True)
    bad = [k for k, v in log["steps"].items() if not v["ok"]]
    print("\n실패한 단계:", bad or "없음")


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
