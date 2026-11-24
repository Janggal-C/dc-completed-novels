"""소설넷 구조 확인용 (저장 없음, 요청 간격 10초)"""
import re
import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}
S = requests.Session(); S.headers.update(UA)


def get(url):
    r = S.get(url, timeout=20)
    print(f"\n=== {r.status_code} {r.url} ({len(r.text)}자)")
    time.sleep(10)
    return r


def main():
    r = get("https://ssn.so/")
    soup = BeautifulSoup(r.text, "html.parser")
    for f in soup.find_all("form"):
        print("FORM", f.get("action"), f.get("method"), [(i.get("name"), i.get("type")) for i in f.find_all("input")])
    for s in re.findall(r"[\"'](/[a-z\-/]*search[^\"']*)[\"']", r.text)[:10]:
        print("search 경로 후보:", s)
    q = quote("약먹는 천재마법사")
    for u in [f"https://ssn.so/series/search/?q={q}", f"https://ssn.so/series/?search={q}", f"https://ssn.so/series/?keyword={q}"]:
        r = get(u)
        if r.ok:
            soup = BeautifulSoup(r.text, "html.parser")
            links = [(a.get("href"), a.get_text(" ", strip=True)[:50]) for a in soup.select("a[href^='/series/']") if re.match(r"^/series/\d+/$", a.get("href", ""))]
            print("작품 링크", len(links), links[:8])
    # 상세 페이지 구조
    r = get("https://ssn.so/series/101394/")
    soup = BeautifulSoup(r.text, "html.parser")
    for m in soup.find_all("meta"):
        if m.get("property", "").startswith(("og:", "book")) or m.get("name", "") in ("description",):
            print("META", m.get("property") or m.get("name"), (m.get("content") or "")[:100])
    for sc in soup.find_all("script", type="application/ld+json"):
        print("LDJSON", sc.string[:800] if sc.string else "")
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if any(k in h for k in ("novelpia", "naver", "kakao", "munpia", "ridibooks", "joara")):
            print("PLATFORM", a.get("class"), h, a.get_text(" ", strip=True)[:30])
    txt = soup.get_text(" ", strip=True)
    for k in ("평점", "완결", "연재"):
        i = txt.find(k); print("TEXT", k, txt[max(0, i - 60): i + 80] if i >= 0 else None)


if __name__ == "__main__":
    main()
