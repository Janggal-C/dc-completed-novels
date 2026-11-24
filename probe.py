"""디시 장르소설 갤러리 접속 테스트.

GitHub Actions 서버에서 디시에 접속되는지, 제목 검색 결과를 파싱할 수 있는지 확인한다.
결과는 로그와 Actions 실행 요약(Summary)에 표시된다.
"""
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

GALLERY_ID = "genrenovel"
BASE = "https://gall.dcinside.com/mgallery/board/lists/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://gall.dcinside.com/",
}


def fetch(params):
    r = requests.get(BASE, params=params, headers=HEADERS, timeout=20)
    return r


def parse_rows(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("tr.ub-content"):
        num = tr.select_one("td.gall_num")
        tit = tr.select_one("td.gall_tit a")
        date = tr.select_one("td.gall_date")
        writer = tr.select_one("td.gall_writer")
        num_txt = num.get_text(strip=True) if num else ""
        if not num_txt.isdigit():
            continue  # 공지·AD·설문 제외
        rows.append({
            "no": int(num_txt),
            "title": tit.get_text(" ", strip=True) if tit else "",
            "date": (date.get("title") or date.get_text(strip=True)) if date else "",
            "writer_kind": (
                "고닉" if writer is not None and writer.get("data-uid") else
                "유동" if writer is not None and writer.get("data-ip") else "?"
            ),
        })
    next_pos = None
    m = re.search(r"search_pos=(-?\d+)", str(soup.select_one(".search_next") or ""))
    if not m:
        m = re.search(r"search_pos=(-?\d+)", html)
    if m:
        next_pos = m.group(1)
    return rows, next_pos


def main():
    lines = ["## 디시 접속 테스트 결과", ""]
    ok = True
    tests = [
        ("검색 1페이지", {"id": GALLERY_ID, "s_type": "search_subject", "s_keyword": "완결"}),
        ("검색 2페이지", {"id": GALLERY_ID, "s_type": "search_subject", "s_keyword": "완결", "page": 2}),
    ]
    next_pos = None
    for i, (name, params) in enumerate(tests):
        if i:
            time.sleep(2)
        try:
            r = fetch(params)
        except Exception as e:  # 네트워크 오류
            lines.append(f"- ❌ {name}: 접속 실패 ({e})")
            ok = False
            continue
        rows, pos = parse_rows(r.text) if r.ok else ([], None)
        next_pos = next_pos or pos
        status = "✅" if r.ok and rows else "❌"
        if not (r.ok and rows):
            ok = False
        lines.append(f"- {status} {name}: HTTP {r.status_code}, 글 {len(rows)}개, 응답 {len(r.text):,}자")
        for row in rows[:5]:
            lines.append(f"    - #{row['no']} [{row['date']}] {row['title']} ({row['writer_kind']})")
        if r.ok and not rows:
            snippet = re.sub(r"\s+", " ", r.text[:300])
            lines.append(f"    - 응답 앞부분: `{snippet}`")

    if next_pos:
        time.sleep(2)
        r = fetch({"id": GALLERY_ID, "s_type": "search_subject", "s_keyword": "완결", "search_pos": next_pos})
        rows, _ = parse_rows(r.text) if r.ok else ([], None)
        lines.append(f"- {'✅' if rows else '⚠️'} 다음 검색 블록(search_pos={next_pos}): HTTP {r.status_code}, 글 {len(rows)}개")
        if rows:
            lines.append(f"    - 가장 오래된 글: #{rows[-1]['no']} [{rows[-1]['date']}]")
    else:
        lines.append("- ⚠️ 다음 검색 링크(search_pos)를 찾지 못함")

    lines += ["", "**결론: " + ("접속·파싱 모두 정상 → GitHub Actions로 진행 가능" if ok else "접속 차단 또는 파싱 실패 → 로그 확인 필요") + "**"]
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report + "\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
