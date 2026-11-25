"""구글 검색 결과 받아오기.

- SerpApi: 매일 실행용 (월 무료 250회, 일·월 한도 안에서만)
- Serper: 대량 처리용 (가입 시 1회 무료 2,500회, dict/serper_usage.json 으로 누적 관리)


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


SERPER_USAGE = DICT / "serper_usage.json"


def serper_available():
    return bool(os.environ.get("SERPER_API_KEY"))


def serper_remaining(total_limit):
    return max(0, total_limit - read_json(SERPER_USAGE, {}).get("total", 0))


def serper_search(query, num=8):
    """Serper(google.serper.dev)로 구글 검색 → [{"title", "snippet", "link"}]"""
    r = requests.post("https://google.serper.dev/search", timeout=30,
                      headers={"X-API-KEY": os.environ["SERPER_API_KEY"], "Content-Type": "application/json"},
                      json={"q": query, "gl": "kr", "hl": "ko", "num": num})
    u = read_json(SERPER_USAGE, {})
    u["total"] = u.get("total", 0) + 1
    u[now_kst().strftime("%Y-%m-%d")] = u.get(now_kst().strftime("%Y-%m-%d"), 0) + 1
    write_json(SERPER_USAGE, u)
    if r.status_code != 200:
        raise RuntimeError(f"Serper HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    out = []
    kg = data.get("knowledgeGraph") or {}
    if kg.get("title"):
        out.append({"title": kg["title"], "snippet": kg.get("description", ""), "link": kg.get("website", "")})
    for o in data.get("organic", [])[:num]:
        out.append({"title": o.get("title", ""), "snippet": o.get("snippet", ""), "link": o.get("link", "")})
    return out


def web_left(cfg):
    """오늘 쓸 수 있는 구글 검색 횟수 (Serper 남은 무료분 + SerpApi 하루 한도)"""
    jc, bc = cfg["judge"], cfg["bulk"]
    n = serper_remaining(bc["total_limit"]) if serper_available() else 0
    if available():
        n += remaining(jc.get("google_monthly_limit", 240), jc.get("google_daily_limit", 30))
    return n


def web_search(query, cfg):
    """Serper 무료분이 남았으면 Serper, 아니면 SerpApi(하루 한도 안에서). 둘 다 없으면 RuntimeError"""
    if serper_available() and serper_remaining(cfg["bulk"]["total_limit"]) > 0:
        return serper_search(query)
    jc = cfg["judge"]
    if available() and remaining(jc.get("google_monthly_limit", 240), jc.get("google_daily_limit", 30)) > 0:
        return search(query)
    raise RuntimeError("오늘 검색 한도 소진")
