"""SerpApi로 구글 검색 결과 받아오기 (월 무료 한도 안에서만).

SERPAPI_KEY 비밀값이 있을 때만 동작한다. 월 사용량은 dict/search_usage.json에 기록.
"""
import os

import requests

from .common import DICT, now_kst, read_json, write_json

USAGE = DICT / "search_usage.json"


def available():
    return bool(os.environ.get("SERPAPI_KEY"))


def remaining(monthly_limit, daily_limit):
    """이번 달·오늘 남은 검색 횟수 중 작은 쪽"""
    now = now_kst()
    u = read_json(USAGE, {})
    month_left = monthly_limit - u.get(now.strftime("%Y-%m"), 0)
    day_left = daily_limit - u.get(now.strftime("%Y-%m-%d"), 0)
    return max(0, min(month_left, day_left))


def _count():
    now = now_kst()
    u = read_json(USAGE, {})
    for k in (now.strftime("%Y-%m"), now.strftime("%Y-%m-%d")):
        u[k] = u.get(k, 0) + 1
    # 일별 기록은 최근 40일만 보관
    days = sorted(k for k in u if len(k) == 10)
    for k in days[:-40]:
        u.pop(k)
    write_json(USAGE, u)


def search(query, num=8):
    """→ [{"title", "snippet", "link"}]. 실패하면 RuntimeError"""
    r = requests.get("https://serpapi.com/search.json", timeout=30, params={
        "engine": "google", "q": query, "hl": "ko", "gl": "kr", "num": num,
        "api_key": os.environ["SERPAPI_KEY"]})
    _count()   # 실패해도 사용량에 잡힐 수 있으므로 보수적으로 센다
    if r.status_code != 200:
        raise RuntimeError(f"SerpApi HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    if data.get("error"):
        raise RuntimeError(f"SerpApi 오류: {data['error']}")
    out = []
    kg = data.get("knowledge_graph") or {}
    if kg.get("title"):
        out.append({"title": kg["title"], "snippet": kg.get("description", ""), "link": kg.get("website", "")})
    for o in data.get("organic_results", [])[:num]:
        out.append({"title": o.get("title", ""), "snippet": o.get("snippet", ""), "link": o.get("link", "")})
    return out
