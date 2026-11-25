"""순위 페이지 한 장에서 작품 제목 목록 가져오기 (Secrets의 RANKING_URL 한 주소만).

원칙
- 주소는 저장소 Secrets `RANKING_URL`에서만 읽는다 (코드·결과 파일에 주소·도메인을 남기지 않는다).
- 실행할 때마다 그 사이트의 robots.txt를 먼저 읽는다. 허용되지 않거나 확인할 수 없으면 가져오지 않고 멈춘다.
- 요청은 그 한 페이지 1번뿐. 재시도·우회·로그인·차단 화면 통과 시도를 하지 않는다.
- 브라우저인 척하지 않고 정체와 연락처가 보이는 User-Agent를 쓴다.
- 결과 파일에는 제목 목록(최대 100개)과 구조 정보만 남긴다. 원본 HTML은 저장하지 않는다.

python -m src.ranking_fetch
결과: data/ranking_titles.json
"""
import json
import os
import re
import urllib.robotparser
from collections import Counter
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .common import DATA, now_kst, write_json

UA = "dc-completed-novels-research (personal, low-volume; +https://github.com/answhdtjr736-spec/dc-completed-novels)"
OUT = DATA / "ranking_titles.json"
MAX_TITLES = 100


def robots_allows(url):
    """→ (허용 여부, 이유). 확인할 수 없으면 허용하지 않는다."""
    u = urlparse(url)
    try:
        r = requests.get(f"{u.scheme}://{u.netloc}/robots.txt", headers={"User-Agent": UA}, timeout=20)
    except Exception as e:
        return False, f"robots.txt 확인 실패: {type(e).__name__}"
    if r.status_code == 404:
        return True, "robots.txt 없음"
    if r.status_code != 200:
        return False, f"robots.txt 응답 {r.status_code}"
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(r.text.splitlines())
    if rp.can_fetch(UA, url):
        return True, "robots.txt 허용"
    return False, "robots.txt가 이 경로를 허용하지 않음"


def _sig(a):
    """링크 주변 구조 서명: 부모·조부모의 태그와 클래스 (같은 목록 항목끼리 같은 값이 된다)"""
    parts = []
    for p in list(a.parents)[:3]:
        if p.name in ("[document]", "html", "body"):
            break
        parts.append(p.name + ("." + ".".join(p.get("class", [])) if p.get("class") else ""))
    return " < ".join(parts)


def extract(html):
    """반복되는 링크 묶음 중 목록처럼 보이는 가장 큰 묶음의 링크 글자를 제목으로 본다."""
    soup = BeautifulSoup(html, "html.parser")
    groups = {}
    for a in soup.find_all("a"):
        text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        if not (2 <= len(text) <= 60) or re.fullmatch(r"[\d,.\s]+", text):
            continue
        groups.setdefault(_sig(a), []).append(text)
    cands = [(sig, items) for sig, items in groups.items() if 10 <= len(items) <= 400]
    cands.sort(key=lambda x: -len(x[1]))
    hints = [{"signature": s, "count": len(i), "sample": i[:3]} for s, i in cands[:4]]
    if not cands:
        return [], "", hints
    sig, items = cands[0]
    seen, titles = set(), []
    for t in items:
        if t not in seen:
            seen.add(t)
            titles.append(t)
    return titles[:MAX_TITLES], sig, hints


def main():
    res = {"checked": now_kst().strftime("%Y-%m-%d %H:%M")}
    url = os.environ.get("RANKING_URL", "").strip()
    if not url:
        res["stage"] = "no_url"
        write_json(OUT, res)
        print("Secrets에 RANKING_URL이 없습니다. 저장소 Settings → Secrets → Actions에 등록하세요.")
        return
    if urlparse(url).scheme not in ("http", "https"):
        res["stage"] = "bad_url"
        write_json(OUT, res)
        print("RANKING_URL은 http(s) 주소여야 합니다.")
        return
    ok, why = robots_allows(url)
    res["robots"] = why
    if not ok:
        res["stage"] = "stopped_by_robots"
        write_json(OUT, res)
        print(f"가져오지 않고 멈춥니다: {why}")
        return
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "ko"}, timeout=30)
    res.update(status=r.status_code, length=len(r.text))
    if r.status_code != 200 or re.search(r"just a moment|captcha|cloudflare|사람인지", r.text[:5000], re.I):
        res["stage"] = "blocked_or_challenge"
        write_json(OUT, res)
        print(f"차단·확인 화면으로 보여 멈춥니다 (응답 {r.status_code}).")
        return
    titles, sig, hints = extract(r.text)
    res.update(stage="ok", count=len(titles), signature=sig, titles=titles, hints=hints)
    write_json(OUT, res)
    print(f"제목 {len(titles)}개 추출 (구조: {sig or '없음'}) / robots: {why}")
    if not titles:
        print("목록 구조를 못 찾았습니다. hints를 보고 파서를 맞춰야 합니다.")


if __name__ == "__main__":
    main()
