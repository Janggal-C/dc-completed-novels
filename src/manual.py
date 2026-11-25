"""사용자가 직접 입력한 줄임말 → 정식 제목 처리.

입력 예 (한 줄에 하나, '=' 또는 탭 또는 '→' 로 구분):
    미시회귀 = 웹소설로 꿈꾸는 세상! - 미연시 속 회귀하는 히로인이 되었다
    후프 = 후회안하는 프로듀서

처리:
1) 연재처 이름 같은 군더더기를 지운다 (노벨피아 페이지 제목 앞부분 등)
2) 이미 사전에 있는 작품이면(띄어쓰기·기호 무시하고 같으면) 그 작품의 정식 표기를 그대로 쓴다
3) 처음 보는 작품이면 AI가 띄어쓰기·표기를 다듬는다 (작품명 자체를 바꾸지는 않음)
4) 사용자 입력이 최우선: 기존에 다른 작품으로 잘못 연결돼 있었으면 덮어쓴다

사용: python -m src.manual "<입력 텍스트>"   (GitHub 이슈 본문)
"""
import json
import os
import re
import sys

from . import ai
from .common import ALIASES, AUTHORS, DICT, SEARCH_CACHE, WORKS, load_config, norm_key, read_json, write_json
from .judge import add_work, save_alias_dates

# 플랫폼 페이지 제목에 붙는 군더더기
_NOISE = [
    r"^\s*웹소설로 꿈꾸는 세상!?\s*[-–|:]\s*",
    r"^\s*(노벨피아|문피아|카카오페이지|네이버\s*시리즈|리디(북스)?|조아라|블라이스)\s*[-–|:]\s*",
    r"\s*[-–|:]\s*(노벨피아|문피아|카카오페이지|네이버\s*시리즈|네이버\s*웹소설|리디(북스)?|조아라|블라이스)\s*$",
    r"\s*[-–|]\s*웹소설로 꿈꾸는 세상!?\s*$",
    r"^\s*\[(독점|완결|연재|19금?|웹소설|단행본|외전)\]\s*",
]


def parse(text):
    """→ [(줄임말, 입력 제목, 작가여부)]"""
    out = []
    for line in (text or "").splitlines():
        line = line.strip().lstrip("-*•").strip()
        if not line or line.startswith(("#", "<!--")):
            continue
        m = re.match(r"^(.+?)\s*(?:=>|=|→|->|\t|:)\s*(.+)$", line)
        if not m:
            continue
        alias, title = m.group(1).strip(), m.group(2).strip()
        is_author = bool(re.match(r"^(작가|작가명|author)\s*$", title, re.I))
        if re.match(r"^(제거|삭제|아님|x)\s*$", title, re.I):
            is_author = "remove"
        out.append((alias, title, is_author))
    return out


def clean(title):
    t = title
    for _ in range(2):
        for p in _NOISE:
            t = re.sub(p, "", t)
    return re.sub(r"\s+", " ", t).strip(" \"'“”‘’「」『』<>《》")


NORMALIZE_PROMPT = """아래는 한국 웹소설 제목을 사람이 직접 입력한 것이다. 띄어쓰기·맞춤법 표기만 실제 정식 제목처럼 다듬어라.
- 제목의 단어를 바꾸거나 더하거나 빼지 마라. 띄어쓰기와 문장부호만 고친다.
- 네가 정식 표기를 확실히 알면 그 표기로 (예: 후회안하는 프로듀서 → 후회 안 하는 프로듀서)
- 모르면 한국어 맞춤법에 맞는 띄어쓰기로.
아래 JSON 배열만 출력해라. [{"input": "입력 그대로", "title": "다듬은 제목"}]

"""


def normalize(titles, model):
    if not titles:
        return {}
    if os.environ.get("AI_MOCK") == "1":
        return {t: t for t in titles}
    try:
        res = ai._json_from(ai._call(NORMALIZE_PROMPT + "\n".join(titles), model))
    except ai.AIError as e:
        print(f"⚠️ 띄어쓰기 다듬기 실패, 입력 그대로 저장: {e}", file=sys.stderr)
        return {t: t for t in titles}
    out = {}
    for r in res:
        src, dst = r.get("input", ""), (r.get("title") or "").strip()
        # 안전장치: 띄어쓰기·기호만 달라야 함 (글자가 바뀌었으면 입력 그대로)
        if src in titles and dst and norm_key(src) == norm_key(dst):
            out[src] = dst
    return {t: out.get(t, t) for t in titles}


def run(text):
    cfg = load_config()
    works = read_json(WORKS, {})
    aliases = read_json(ALIASES, {})
    cache = read_json(SEARCH_CACHE, {})
    authors = read_json(AUTHORS, [])
    items = parse(text)
    if not items:
        print("입력에서 '줄임말 = 제목' 형식의 줄을 찾지 못했습니다.")
        return []

    cleaned = [(a, clean(t), is_auth) for a, t, is_auth in items]
    # 이미 있는 작품(띄어쓰기 무시 일치)은 기존 정식 표기 사용, 없는 것만 AI로 다듬기
    unknown_titles = [t for a, t, is_auth in cleaned if not is_auth and norm_key(t) not in works]
    removed = read_json(DICT / "removed.json", [])
    fixed = normalize(unknown_titles, cfg["judge"]["model"])

    report = []
    for alias, title, is_auth in cleaned:
        k = norm_key(alias)
        if is_auth == "remove":
            # 작품이 아닌 단어: 줄임말 연결을 끊고, 그 단어 때문에 생긴 작품(다른 이름 없음)이면 작품도 지움
            wid = aliases.pop(k, None)
            if k not in removed:
                removed.append(k)
            note = "작품 아님 → 사전에서 제거"
            # 남은 이름(정식 제목 포함)이 하나도 없으면 그 단어 때문에 생긴 가짜 작품 → 삭제
            if wid and wid in works and wid not in aliases.values() and works[wid].get("source") != "직접 입력":
                note += f", 작품 '{works.pop(wid)['title']}'도 삭제"
            report.append(f"- {alias} → {note}")
            continue
        if is_auth:
            if alias not in authors:
                authors.append(alias)
            aliases.pop(k, None)
            report.append(f"- {alias} → 작가 이름으로 등록 (집계·검색 제외)")
            continue
        authors = [x for x in authors if norm_key(x) != k]   # 작가로 잘못 분류돼 있었으면 해제
        existing = works.get(norm_key(title))
        final = existing["title"] if existing else fixed.get(title, title)
        before = works.get(aliases.get(k, ""), {}).get("title")
        wid = add_work(works, aliases, final, alias=alias, via="직접 입력", force=True, source="직접 입력")
        works[wid]["needs_review"] = False
        cache.pop(k, None)
        note = "기존 작품에 연결" if existing else ("새 작품 등록" if final == title else f"새 작품 등록 (표기 수정: {title} → {final})")
        if before and before != final:
            note += f", 이전 연결 '{before}' 대체"
        report.append(f"- {alias} → {final} ({note})")

    write_json(WORKS, works)
    write_json(ALIASES, aliases)
    write_json(SEARCH_CACHE, cache)
    write_json(AUTHORS, sorted(set(authors)))
    write_json(DICT / "removed.json", sorted(set(removed)))
    save_alias_dates("직접 입력")
    msg = "\n".join(report)
    print(msg)
    out = os.environ.get("MANUAL_RESULT")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(msg)
    return report


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("MANUAL_INPUT", ""))
