"""공통 유틸: 경로, 설정, JSON/JSONL 입출력, 정규화."""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
POSTS_DIR = DATA / "posts"          # 월별 글 목록 (YYYY-MM.jsonl)
AI_DIR = DATA / "ai"                # 월별 AI 판정 결과 (YYYY-MM.jsonl)
STATE = DATA / "state.json"
METRICS = DATA / "metrics.jsonl"    # 실행별 지표 기록
DICT = ROOT / "dict"
WORKS = DICT / "works.json"         # 작품 ID → 정식 제목 등
ALIASES = DICT / "aliases.json"     # 정규화 키 → 작품 ID
SEARCH_CACHE = DICT / "search_cache.json"
OVERRIDES = ROOT / "review" / "overrides.csv"
SITE_DATA = ROOT / "docs" / "data"

KST = timezone(timedelta(hours=9))


def now_kst():
    return datetime.now(KST)


def load_config():
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_json(path, default):
    path = Path(path)
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(tmp, path)


def month_of(date_str):
    """'2026-11-24 13:11:02' → '2026-11'"""
    return date_str[:7]


def load_monthly(dirpath):
    """월별 JSONL 전부 → {no: row}"""
    out = {}
    for p in sorted(Path(dirpath).glob("*.jsonl")):
        for r in read_jsonl(p):
            out[r["no"]] = r
    return out


def merge_monthly(dirpath, rows):
    """rows를 월별 파일에 글번호 기준으로 병합 저장. 바뀐 달만 다시 쓴다."""
    by_month = {}
    for r in rows:
        by_month.setdefault(month_of(r["date"]), []).append(r)
    for month, new in by_month.items():
        path = Path(dirpath) / f"{month}.jsonl"
        cur = {r["no"]: r for r in read_jsonl(path)}
        for r in new:
            cur[r["no"]] = r
        write_jsonl(path, sorted(cur.values(), key=lambda r: -r["no"]))


_KEY_STRIP = re.compile(r"[\s\W_]+", re.UNICODE)


def norm_key(name):
    """작품명 비교용 키: 공백·기호 제거, 소문자. '전지적 독자 시점!' → '전지적독자시점'"""
    return _KEY_STRIP.sub("", (name or "").lower())


def quarter_of(month):
    y, m = month.split("-")
    return f"{y}-Q{(int(m) - 1) // 3 + 1}"
