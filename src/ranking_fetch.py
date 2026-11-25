"""순위 페이지 한 장에서 작품 제목만 가져오기 (Secrets의 SITE_URL 한 주소만).

- 제목 = 페이지 안의 <b class="cut_line_one"> 글자. 다른 판정은 하지 않는다.
- 주소는 Secrets에서만 읽고, 코드·결과 파일에 주소·도메인을 남기지 않는다.
- 요청 전에 robots.txt를 확인한다 (파이썬 표준 robotparser가 기계적으로 판정, AI 개입 없음).
  허용되지 않거나 읽을 수 없으면 가져오지 않고 멈춘다.
- 그 한 페이지를 1번만 요청한다. 재시도·우회·차단 화면 통과 시도 없음. 원본 HTML은 저장하지 않는다.

python -m src.ranking_fetch
결과: data/ranking_titles.json
"""
import json
import os
import re
import urllib.robotparser
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


def extract(html):
    """<b class="cut_line_one"> 안의 글자를 순서대로 (중복 제거)"""
    soup = BeautifulSoup(html, "html.parser")
    seen, titles = set(), []
    for b in soup.select("b.cut_line_one"):
        t = re.sub(r"\s+", " ", b.get_text(" ", strip=True))
        if t and t not in seen:
            seen.add(t)
            titles.append(t)
    return titles[:MAX_TITLES]


def redact(msg, url):
    """오류 문구에서 주소·도메인을 지운다 (결과 파일은 공개 저장소에 올라간다)"""
    host = urlparse(url).netloc
    for x in (url, host, host.split(":")[0]):
        if x:
            msg = msg.replace(x, "[주소]")
    return msg[:300]


def main():
    res = {"checked": now_kst().strftime("%Y-%m-%d %H:%M")}
    url = os.environ.get("RANKING_URL", "").strip().strip("\"'").strip()
    if url and not re.match(r"^[a-z][a-z0-9+.-]*://", url, re.I):
        url = "https://" + url.lstrip("/")          # https:// 를 빼고 등록한 경우
    if not url:
        res["stage"] = "no_url"
        write_json(OUT, res)
        print("Secrets에 RANKING_URL이 없습니다. 저장소 Settings → Secrets → Actions에 등록하세요.")
        return
    if urlparse(url).scheme not in ("http", "https") or not urlparse(url).netloc:
        res["stage"] = "bad_url"
        res["hint"] = "주소가 비었거나 형식이 이상함 (값 자체는 기록하지 않음)"
        write_json(OUT, res)
        print("주소 형식이 올바르지 않습니다. 값 앞뒤 공백·따옴표·여러 줄 여부를 확인하세요.")
        return
    ok, why = robots_allows(url)
    if "확인 실패" in why:
        try:
            requests.get(f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt", headers={"User-Agent": UA}, timeout=20)
        except Exception as e:
            res["error_detail"] = redact(f"{type(e).__name__}: {e}", url)
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
    titles = extract(r.text)
    res.update(stage="ok" if titles else "no_titles", count=len(titles), titles=titles,
               cut_line_one=len(re.findall(r"cut_line_one", r.text)))
    write_json(OUT, res)
    print(f"제목 {len(titles)}개 추출 / robots: {why}")
    if not titles:
        print("cut_line_one을 못 찾았습니다 (자바스크립트로 나중에 채워지는 페이지일 수 있음).")


if __name__ == "__main__":
    main()
