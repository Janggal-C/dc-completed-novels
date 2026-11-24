"""실행 진입점.

python -m src.main all     # 전부 (로컬)
python -m src.main crawl   # 크롤링만 (Actions 1단계)
python -m src.main judge   # AI 판정 + 사전 + 보고서 (Actions 2단계)
python -m src.main report  # 보고서만 다시 만들기
"""
import json
import sys

from . import aggregate, crawl, judge
from .common import DATA, load_config

STATS_FILE = DATA / ".run_stats.json"   # 크롤링 단계 → 판정 단계로 넘기는 이번 실행 통계 (커밋 안 함)


def main(step="all"):
    cfg = load_config()
    if step in ("crawl", "all"):
        try:
            s = crawl.run(cfg)
        except crawl.Blocked as e:
            print(f"❌ 디시가 요청을 차단했습니다: {e}", file=sys.stderr)
            sys.exit(2)
        STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATS_FILE.write_text(json.dumps({"crawled_new": s["new"], "crawled_backfill": s["backfill"]}))
    if step in ("judge", "all"):
        stats = json.loads(STATS_FILE.read_text()) if STATS_FILE.exists() else {}
        s = judge.run(cfg)
        stats.update(ai_judged=s["ai_judged"], searched=s["searched"], ai_stopped=bool(s["stopped"]),
                     ai_usage={k: round(v, 4) for k, v in judge.ai.USAGE.items()})
        print(f"AI 사용량: {stats['ai_usage']}")
        aggregate.run(cfg, run_stats=stats)
        STATS_FILE.unlink(missing_ok=True)
    if step == "report":
        aggregate.run(cfg)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
