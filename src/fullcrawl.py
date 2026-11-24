"""갤러리 전체 글 제목 수집 (본문 X, AI X).

- 초기 수집: 최신 글(1페이지)부터 목록을 100개씩 넘기며 기준일(cutoff)까지 거슬러 올라간다.
- 페이지 밀림: 새 글이 올라오면 기존 글이 뒤 페이지로 밀려 '중복'만 생긴다.
  '지금까지 본 가장 작은 글번호(cursor)'보다 작은 글만 새로 받고, 페이지 전체가 이미 본 글이면 건너뛴다.
  (삭제로 앞당겨져 경계에서 몇 개 놓치는 경우는 새 글 유입보다 훨씬 드물어 무시할 수준)
- 이어받기: 페이지마다 진행 상태 저장, 10분마다 저장소에 커밋. 시간 제한·차단 시 그 자리에서 멈추고 다음 실행 때 계속.
- 매일 증분(초기 수집 완료 후): 1페이지부터 지난번 가장 최신 글번호를 만날 때까지만.

저장: data/titles/YYYY-MM-DD.jsonl.gz  (no, title, date, writer해시)
"""
import gzip
import json
import sys
import time
from pathlib import Path

from .common import FULL_STATE, TITLES_DIR, checkpoint, load_config, now_kst, read_json, write_json
from .crawl import Blocked, Client


def _path(day):
    return TITLES_DIR / f"{day}.jsonl.gz"


def _read_day(day):
    p = _path(day)
    if not p.exists():
        return {}
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return {r["no"]: r for r in (json.loads(l) for l in f if l.strip())}


def save_rows(rows):
    """날짜별 파일에 글번호 기준 병합 저장"""
    by_day = {}
    for r in rows:
        by_day.setdefault(r["date"][:10], []).append(
            {"no": r["no"], "title": r["title"], "date": r["date"], "writer": r["writer"]})
    TITLES_DIR.mkdir(parents=True, exist_ok=True)
    for day, new in by_day.items():
        cur = _read_day(day)
        for r in new:
            cur[r["no"]] = r
        tmp = _path(day).with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=9) as f:
            for r in sorted(cur.values(), key=lambda r: -r["no"]):
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
        tmp.replace(_path(day))


def load_titles():
    """전체 제목 → {no: row}"""
    out = {}
    for p in sorted(Path(TITLES_DIR).glob("*.jsonl.gz")):
        out.update(_read_day(p.name[:10]))
    return out


class Lister:
    def __init__(self, cfg):
        self.client = Client(cfg)
        self.gid = cfg["gallery_id"]

    def page(self, n):
        rows, _ = self.client.fetch({"id": self.gid, "list_num": 100, "page": n})
        if len(rows) >= 10:
            # 고정글 등 번호가 동떨어진 글 제거 (한 페이지 글번호는 보통 수백 안쪽으로 붙어 있음)
            mid = sorted(r["no"] for r in rows)[len(rows) // 2]
            rows = [r for r in rows if abs(r["no"] - mid) < 20000]
        return rows


def run(max_minutes=None):
    cfg = load_config()
    fc = cfg["fullcrawl"]
    max_minutes = max_minutes or fc["minutes_per_run"]
    deadline = time.time() + max_minutes * 60
    st = read_json(FULL_STATE, {})
    if not st:
        st = {"cutoff": fc["cutoff"], "page": 1, "cursor": None, "newest": None, "done": False, "pages_done": 0}
    L = Lister(cfg)
    stats = {"pages": 0, "rows": 0, "new": 0}
    buf = []

    try:
        # 1) 초기 수집 이후라면: 최신 글 증분
        if st["done"]:
            buf, n = [], 1
            while time.time() < deadline:
                rows = L.page(n)
                fresh = [r for r in rows if r["no"] > (st["newest"] or 0)]
                buf += fresh
                stats["pages"] += 1
                if len(fresh) < len(rows) or not rows:
                    break
                n += 1
            if buf:
                save_rows(buf)
                st["newest"] = max(r["no"] for r in buf)
                stats["new"] = len(buf)
            write_json(FULL_STATE, st)
            print(f"전체 제목 증분: 새 글 {stats['new']}개, {stats['pages']}페이지")
            return stats

        # 2) 초기 수집: cursor(지금까지 본 가장 작은 글번호) 아래로 계속
        n = st["page"]
        while time.time() < deadline:
            rows = L.page(n)
            stats["pages"] += 1
            if not rows:
                print(f"  {n}페이지가 비어 있음 → 끝으로 판단", flush=True)
                st["done"] = True
                break
            if st["newest"] is None:
                st["newest"] = rows[0]["no"]
                print(f"  시작: 1페이지 #{rows[0]['no']} {rows[0]['date']} ~ #{rows[-1]['no']} {rows[-1]['date']}", flush=True)
            bottom = rows[-1]["no"]
            cur = st["cursor"]
            if cur is not None and bottom >= cur:
                # 새 글 때문에 밀려서 이미 본 구간 → 다음 페이지로 (밀린 만큼 건너뛰기)
                n += max(1, (sum(1 for r in rows if r["no"] >= cur)) // 100)
                continue
            new = [r for r in rows if cur is None or r["no"] < cur]
            keep = [r for r in new if r["date"][:10] >= st["cutoff"]]
            buf += keep
            stats["rows"] += len(keep)
            st["cursor"] = min(r["no"] for r in rows) if cur is None else min(cur, min(r["no"] for r in rows))
            st["page"] = n + 1
            st["pages_done"] = st.get("pages_done", 0) + 1
            st["oldest_date"] = rows[-1]["date"][:10]
            if len(keep) < len(new):
                st["done"] = True
                print(f"  기준일 {st['cutoff']} 도달 → 초기 수집 완료", flush=True)
                break
            if len(buf) >= 2000:
                save_rows(buf)
                buf = []
                write_json(FULL_STATE, st)
            if stats["pages"] % 20 == 0:
                print(f"  {n}페이지 · 현재 {st['oldest_date']} (목표 {st['cutoff']}) · 이번 실행 {stats['rows']:,}개", flush=True)
            checkpoint(f"전체 제목 수집 ~{st['oldest_date']}", report=False)
            n += 1
    except Blocked as e:
        print(f"❌ 디시 차단 신호: {e} → 저장 후 중단", file=sys.stderr)
        stats["blocked"] = str(e)
    except RuntimeError as e:
        print(f"⚠️ 접속 실패: {e} → 저장 후 중단", file=sys.stderr)
        stats["error"] = str(e)
    finally:
        if buf:
            save_rows(buf)
        st["last_run"] = now_kst().strftime("%Y-%m-%d %H:%M")
        write_json(FULL_STATE, st)
    print(f"전체 제목 수집: 이번 {stats['pages']}페이지 {stats['rows']:,}개 · 진행 {st.get('oldest_date')} · "
          f"{'완료' if st['done'] else '진행 중'}")
    return stats


def probe(depth_pages):
    """깊은 페이지 접근 테스트: 1페이지와 depth 페이지를 받아 비교"""
    L = Lister(load_config())
    a = L.page(1)
    b = L.page(depth_pages)
    print(f"1페이지: {len(a)}개 #{a[0]['no'] if a else '-'} {a[0]['date'] if a else ''}")
    print(f"{depth_pages}페이지: {len(b)}개 #{b[0]['no'] if b else '-'} {b[0]['date'] if b else ''}")
    ok = bool(a and b and b[0]["no"] < a[-1]["no"])
    print("✅ 깊은 페이지 접근 가능" if ok else "❌ 깊은 페이지 접근 불가")
    return ok


def quick_test():
    """2페이지만 받아서 그대로 출력 + 수집 로직 1분만 실행 (저장소에 커밋 안 함)"""
    import os
    os.environ.pop("GITHUB_ACTIONS", None)   # checkpoint 커밋 끔
    L = Lister(load_config())
    for n in (1, 2):
        t = time.time()
        rows = L.page(n)
        print(f"[{n}페이지] {len(rows)}개, {time.time() - t:.1f}초")
        for r in rows[:3] + rows[-2:]:
            print(f"   #{r['no']} {r['date']} {r['title'][:30]}")
    print("--- 수집 로직 1분 실행 ---")
    st = run(max_minutes=1)
    print(st, read_json(FULL_STATE, {}))
    print("저장된 날짜 파일:", sorted(p.name for p in Path(TITLES_DIR).glob("*.gz"))[:5])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        quick_test()
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "probe":
        sys.exit(0 if probe(int(sys.argv[2]) if len(sys.argv) > 2 else 15000) else 1)
    run()
