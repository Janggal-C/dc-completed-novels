"""디시 갤러리 '완결' 제목 검색 크롤러.

- 증분: 최신 글부터 내려가다 마지막으로 저장한 글번호를 만나면 멈춘다.
- 초기수집(backfill): 기준일까지 거슬러 올라간다. 페이지마다 진행 위치를 저장해
  중간에 끊겨도 다음 실행 때 이어간다.

디시 검색은 글번호 1만 개 단위 '블록'으로 나뉜다. 블록 안에서는 page=1,2,..로,
다음 블록은 '다음 검색' 링크의 search_pos 값으로 이동한다.
"""
import hashlib
import os
import random
import re
import sys
import time
from datetime import timedelta

import requests
from bs4 import BeautifulSoup

from .common import (POSTS_DIR, STATE, load_config, merge_monthly, now_kst,
                     read_json, write_json)

BASE = "https://gall.dcinside.com/mgallery/board/lists/"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://gall.dcinside.com/",
}
MAX_PAGES_PER_BLOCK = 50


class Blocked(Exception):
    """디시가 요청을 막았을 때 (403/429/캡차)."""


# ---------- 파싱 ----------

def _writer_hash(key):
    salt = os.environ.get("WRITER_SALT", "dc-completed-novels-default-salt")
    return hashlib.sha256((salt + "|" + key).encode()).hexdigest()[:10] if key else ""


def _int(text):
    t = re.sub(r"[^\d]", "", text or "")
    return int(t) if t else 0


def _parse_date(td, today):
    """title 속성(전체 날짜) 우선. 없으면 화면 표기('13:11', '11.23', '25.11.23')로 추정."""
    if td is None:
        return ""
    full = td.get("title")
    if full and re.match(r"\d{4}-\d{2}-\d{2}", full):
        return full[:19]
    t = td.get_text(strip=True)
    if re.fullmatch(r"\d{1,2}:\d{2}", t):
        return f"{today:%Y-%m-%d} {t}:00"
    m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{2})", t)
    if m:
        return f"20{m.group(1)}-{m.group(2)}-{m.group(3)} 00:00:00"
    m = re.fullmatch(r"(\d{2})\.(\d{2})", t)
    if m:
        return f"{today:%Y}-{m.group(1)}-{m.group(2)} 00:00:00"
    return ""


def parse_list(html, today=None):
    """목록 HTML → (글 목록, 다음 검색 search_pos)"""
    today = today or now_kst()
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("tr.ub-content"):
        num = tr.select_one("td.gall_num")
        no = num.get_text(strip=True) if num else ""
        if not no.isdigit():
            continue  # 공지·AD·설문
        a = tr.select_one("td.gall_tit a")
        if a is None:
            continue
        for em in a.select("em"):
            em.decompose()
        writer = tr.select_one("td.gall_writer")
        wkey = ""
        if writer is not None:
            wkey = writer.get("data-uid") or writer.get("data-ip") or writer.get("data-nick") or ""
        reply = tr.select_one("td.gall_tit .reply_num")
        date = _parse_date(tr.select_one("td.gall_date"), today)
        if not date:
            continue
        rows.append({
            "no": int(no),
            "title": a.get_text(" ", strip=True),
            "date": date,
            "writer": _writer_hash(wkey),
            "replies": _int(reply.get_text() if reply else ""),
        })
    nxt = soup.select_one("a.search_next")
    m = re.search(r"search_pos=(-?\d+)", nxt.get("href", "")) if nxt else None
    return rows, (m.group(1) if m else None)


# ---------- 요청 ----------

class Client:
    def __init__(self, cfg):
        self.cfg = cfg
        self.s = requests.Session()
        self.s.headers.update(HEADERS)
        self.requests = 0

    def page(self, search_pos, page):
        params = {"id": self.cfg["gallery_id"], "s_type": "search_subject",
                  "s_keyword": self.cfg["keyword"], "page": page}
        if search_pos:
            params["search_pos"] = search_pos
        lo, hi = self.cfg["crawl"]["delay_seconds"]
        for attempt in range(self.cfg["crawl"]["max_retries"] + 1):
            if self.requests:
                time.sleep(random.uniform(lo, hi) * (2 ** attempt))
            self.requests += 1
            try:
                r = self.s.get(BASE, params=params, timeout=20)
            except requests.RequestException as e:
                print(f"  요청 오류: {e}", file=sys.stderr)
                continue
            if r.status_code in (403, 429):
                raise Blocked(f"HTTP {r.status_code}")
            if "captcha" in r.text[:5000].lower() and "ub-content" not in r.text:
                raise Blocked("캡차 페이지")
            if r.ok:
                return parse_list(r.text)
            print(f"  HTTP {r.status_code}, 재시도", file=sys.stderr)
        raise RuntimeError("요청 재시도 초과")


def walk(client, search_pos, page):
    """(search_pos, page)부터 아래로 내려가며 (pos, page, rows)를 차례로 내놓는다."""
    while True:
        first_no = None
        next_pos = None
        for p in range(page, page + MAX_PAGES_PER_BLOCK):
            rows, nxt = client.page(search_pos, p)
            next_pos = next_pos or nxt
            if not rows or rows[0]["no"] == first_no:
                break  # 블록 끝
            first_no = rows[0]["no"]
            yield search_pos, p, rows
        if not next_pos:
            return
        search_pos, page = next_pos, 1


# ---------- 실행 ----------

def run(cfg=None):
    cfg = cfg or load_config()
    state = read_json(STATE, {})
    today = now_kst()
    if "backfill" not in state:
        cutoff = (today - timedelta(days=int(cfg["crawl"]["backfill_months"] * 30.5))).strftime("%Y-%m-%d")
        state = {"newest_no": None,
                 "backfill": {"done": False, "search_pos": None, "page": 1, "cutoff": cutoff}}
    client = Client(cfg)
    collected = []
    stats = {"new": 0, "backfill": 0}

    # 1) 증분: 최신 → 마지막 저장 글번호까지
    newest = state["newest_no"]
    top = newest
    if newest is not None:
        done = False
        for _, _, rows in walk(client, None, 1):
            for r in rows:
                if r["no"] <= newest:
                    done = True
                    break
                collected.append(r)
                stats["new"] += 1
            top = max(top, rows[0]["no"])
            if done or rows[-1]["date"][:10] < state["backfill"]["cutoff"]:
                break
    merge_monthly(POSTS_DIR, collected)

    # 2) 초기수집: 진행 위치부터 기준일까지
    bf = state["backfill"]
    if not bf["done"]:
        deadline = time.time() + cfg["crawl"]["backfill_minutes_per_run"] * 60
        buf = []
        finished = True
        for pos, p, rows in walk(client, bf["search_pos"], bf["page"]):
            top = max(top or 0, rows[0]["no"])
            keep = [r for r in rows if r["date"][:10] >= bf["cutoff"]]
            buf += keep
            stats["backfill"] += len(keep)
            # 최신 블록은 새 글이 올라오면 페이지가 뒤로 밀리지만, 그러면 이미 본 글을 다시 볼 뿐 건너뛰지는 않는다
            # (중복은 글번호로 제거)
            bf["search_pos"], bf["page"] = pos, p + 1
            if len(keep) < len(rows):
                break  # 기준일 도달
            if len(buf) >= 200:
                merge_monthly(POSTS_DIR, buf)
                buf = []
                state["newest_no"] = state["newest_no"] or top
                write_json(STATE, state)
            if time.time() > deadline:
                finished = False
                break
        merge_monthly(POSTS_DIR, buf)
        bf["done"] = finished

    if top:
        state["newest_no"] = max(top, state["newest_no"] or 0)
    state["last_run"] = today.strftime("%Y-%m-%d %H:%M:%S")
    write_json(STATE, state)
    print(f"크롤링 완료: 신규 {stats['new']}건, 초기수집 {stats['backfill']}건, "
          f"요청 {client.requests}회, 초기수집 {'완료' if bf['done'] else '진행 중'}")
    return stats


if __name__ == "__main__":
    try:
        run()
    except Blocked as e:
        print(f"❌ 디시가 요청을 차단했습니다: {e}", file=sys.stderr)
        sys.exit(2)
