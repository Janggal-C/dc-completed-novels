"""가짜 디시 페이지 + 가짜 AI(AI_MOCK=1)로 전체 파이프라인을 돌려보는 테스트.

실행: python tests/test_pipeline.py   (저장소를 임시 폴더에 복사해서 돌리므로 실제 데이터는 안 건드림)
"""
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent

TITLES = ["{w} 완결되었네", "{w}완결", "야 벌써 {w}완결이네", "{w} 언제 완결됨?", "{w}완결 예상",
          "드디어 {w} 완결났다 ㅠㅠ", "{w} 완결 후기", "{w} 완결까지 몇화 남음?", "완결작 추천좀", "{w} 왜 완결임?"]
WORKS = ["전독시", "화산귀환", "나혼렙", "데못죽", "검술명가 막내아들", "튜토리얼이 너무 어렵다"]

FAKE_PAGE = '''<table>{rows}</table>{nxt}'''
ROW = ('<tr class="ub-content us-post"><td class="gall_num">{no}</td><td class="gall_tit"><a>{title}</a>'
       '<a class="reply_numbox"><span class="reply_num">[{rep}]</span></a></td>'
       '<td class="gall_writer" data-uid="" data-ip="{ip}"></td><td class="gall_date" title="{date}">x</td>'
       '<td class="gall_count">{views}</td><td class="gall_recommend">{recs}</td></tr>')


def make_posts(n, end, seed=1):
    rnd = random.Random(seed)
    posts = []
    for i in range(n):
        d = end - timedelta(hours=i * 7)
        posts.append({"no": 1_000_000 - i * 37, "title": rnd.choice(TITLES).format(w=rnd.choice(WORKS)),
                      "date": d.strftime("%Y-%m-%d %H:%M:%S"), "ip": f"1.{rnd.randint(1, 30)}"})
    return posts


def fake_server(posts, block=10000, per_page=20):
    """search_pos 블록 + 페이지를 흉내 내는 page 함수"""
    top = posts[0]["no"]

    def page(self, search_pos, p):
        self.requests += 1
        start = int(search_pos) if search_pos else top
        in_block = [x for x in posts if start - block < x["no"] <= start]
        chunk = in_block[(p - 1) * per_page: p * per_page]
        from src.crawl import parse_list
        html = FAKE_PAGE.format(
            rows="".join(ROW.format(rep=1, views=10, recs=1, **x) for x in chunk),
            nxt=f'<a class="search_next" href="?search_pos={start - block}">다음</a>' if start - block > posts[-1]["no"] - block else "")
        return parse_list(html)
    return page


def main():
    tmp = Path(tempfile.mkdtemp())
    repo = tmp / "repo"
    shutil.copytree(SRC, repo, ignore=shutil.ignore_patterns(".git", "data", "__pycache__"))
    sys.path.insert(0, str(repo))
    os.environ["AI_MOCK"] = "1"
    os.chdir(repo)
    from src import crawl, main as M
    from src.common import load_monthly, POSTS_DIR, read_json, STATE

    now = datetime.now()
    posts = make_posts(900, now)   # 900개 × 7시간 ≈ 262일 (6개월 넘음)
    crawl.Client.page = fake_server(posts)
    crawl.time.sleep = lambda s: None

    # 1회차: 초기수집
    M.main("all")
    st = read_json(STATE, {})
    saved = load_monthly(POSTS_DIR)
    cutoff = st["backfill"]["cutoff"]
    expect = [p for p in posts if p["date"][:10] >= cutoff]
    assert st["backfill"]["done"], st
    assert len(saved) == len(expect), (len(saved), len(expect))
    print(f"✅ 초기수집: {len(saved)}건 저장 (기준일 {cutoff} 이후 전부)")

    # 2회차: 새 글 15개 추가 → 증분만 받아야 함
    newer = [{"no": 1_000_000 + 37 * (i + 1), "title": f"{WORKS[i % 6]} 완결되었네",
              "date": (now + timedelta(minutes=i + 1)).strftime("%Y-%m-%d %H:%M:%S"), "ip": f"9.{i}"} for i in range(15)]
    posts2 = sorted(newer, key=lambda p: -p["no"]) + posts
    crawl.Client.page = fake_server(posts2)
    M.main("all")
    saved = load_monthly(POSTS_DIR)
    assert len(saved) == len(expect) + 15, len(saved)
    print("✅ 증분: 새 글 15건만 추가")

    # 3회차: 변경 없음 → 중복 없음
    M.main("all")
    assert len(load_monthly(POSTS_DIR)) == len(expect) + 15
    print("✅ 재실행: 중복 저장 없음")

    # 언급 수는 전체 제목(data/titles, fullcrawl이 모음)에서 센다 → 가짜 글을 전체 제목으로도 넣고 보고서를 다시 만든다
    from src import fullcrawl, mentions, aggregate
    fullcrawl.save_rows([{**p, "writer": p["ip"]} for p in posts2 if p["date"][:10] >= cutoff])
    mentions._CACHE.clear()
    aggregate.run()

    rep =json.loads((repo / "docs/data/report.json").read_text())
    m = rep["months"]
    print(f"✅ 보고서: {len(m)}개월 ({m[0]}~{m[-1]}), 분기 {list(rep['quarterly'])}")
    top = rep["monthly"][m[-1]][:3]
    print("   최근 달 상위:", [(e["title"], e["writers"], e["mentions"]) for e in top])
    print("   지표:", {k: rep["metrics"][k] for k in ("total_posts", "agreement", "rule_coverage", "review_open")})
    print("   사전:", len(rep["dictionary"]), "개, 미확인:", len(rep["unresolved"]))
    assert rep["monthly"] and rep["trend"]
    print(f"\n테스트 폴더: {repo}")


if __name__ == "__main__":
    main()
