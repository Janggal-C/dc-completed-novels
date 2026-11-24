"""전체 제목 수집 테스트: 수집 도중 새 글이 계속 올라와 페이지가 밀려도 빠짐·중복 없이 받는지
실행: python tests/test_fullcrawl.py"""
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent


def main():
    tmp = Path(tempfile.mkdtemp()) / "repo"
    shutil.copytree(SRC, tmp, ignore=shutil.ignore_patterns(".git", "data", "__pycache__"))
    sys.path.insert(0, str(tmp))
    os.chdir(tmp)
    import yaml
    c = yaml.safe_load(open("config.yaml"))
    c["fullcrawl"]["cutoff"] = "2026-01-01"
    yaml.safe_dump(c, open("config.yaml", "w"), allow_unicode=True)
    from src import fullcrawl, crawl

    base = datetime(2026, 11, 24, 12)
    # 2025-12-20 ~ 2026-11-24, 시간당 1글 (테스트용 축소)
    posts = [{"no": 100000 + i, "title": f"글{i}", "date": (base - timedelta(hours=(8000 - i))).strftime("%Y-%m-%d %H:%M:%S"),
              "writer": "w"} for i in range(8000)]
    live = list(reversed(posts))      # 최신 글이 앞
    nxt = [108000]

    def fake_page(self, n):
        # 요청마다 새 글 3개가 올라와 기존 글이 밀린다
        for _ in range(3):
            nxt[0] += 1
            live.insert(0, {"no": nxt[0], "title": "새글", "date": "2026-11-24 13:00:00", "writer": "n"})
        return [dict(r) for r in live[(n - 1) * 100: n * 100]]

    fullcrawl.Lister.page = fake_page
    fullcrawl.Lister.__init__ = lambda self, cfg: None
    st = None
    for _ in range(30):                 # 실행을 여러 번 끊어서(이어받기) 돌려본다
        fullcrawl.run(max_minutes=0.0005)
        st = fullcrawl.read_json(fullcrawl.FULL_STATE, {})
        if st["done"]:
            break
    got = fullcrawl.load_titles()
    expect = {p["no"] for p in posts if p["date"][:10] >= "2026-01-01" and p["no"] <= 108000}
    missing = expect - set(got)
    print(f"기대 {len(expect)} · 받음(초기분) {len(expect & set(got))} · 빠짐 {len(missing)} · 완료 {st['done']}")
    assert st["done"] and not missing, sorted(missing)[:10]
    print("✅ 페이지가 밀려도 빠짐 없이 수집")


if __name__ == "__main__":
    main()


def segments():
    """3개 구간 동시 수집 흉내: 번갈아 조금씩 돌려도 빠짐 없이 받는지"""
    tmp = Path(tempfile.mkdtemp()) / "repo"
    shutil.copytree(SRC, tmp, ignore=shutil.ignore_patterns(".git", "data", "__pycache__"))
    for m in [m for m in list(sys.modules) if m.startswith("src")]:
        del sys.modules[m]
    sys.path.insert(0, str(tmp))
    os.chdir(tmp)
    from src import fullcrawl
    base = datetime(2026, 11, 24, 12)
    posts = [{"no": 100000 + i, "title": f"글{i}", "date": (base - timedelta(hours=(8000 - i))).strftime("%Y-%m-%d %H:%M:%S"),
              "writer": "w"} for i in range(8000)]
    live = list(reversed(posts))
    nxt = [108000]

    def fake_page(self, n):
        nxt[0] += 1
        live.insert(0, {"no": nxt[0], "title": "새글", "date": "2026-11-24 13:00:00", "writer": "n"})
        return [dict(r) for r in live[(n - 1) * 100: n * 100]]
    fullcrawl.Lister.page = fake_page
    fullcrawl.Lister.__init__ = lambda self, cfg: None
    fullcrawl.init_segments(3)
    for _ in range(200):
        for k in range(3):
            fullcrawl.run_segment(k, max_minutes=0.0003)
        if fullcrawl.read_json(fullcrawl.FULL_STATE, {}).get("done"):
            break
    got = fullcrawl.load_titles()
    expect = {p["no"] for p in posts if p["date"][:10] >= "2026-01-01"}
    missing = expect - set(got)
    print(f"[구간 3개] 기대 {len(expect)} · 빠짐 {len(missing)} · 완료 {fullcrawl.read_json(fullcrawl.FULL_STATE, {}).get('done')}")
    assert not missing, sorted(missing)[:10]
    print("✅ 구간 3개 동시 수집도 빠짐 없음")


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "seg":
    segments()
