"""Claude Code CLI(`claude -p`) 호출. Pro 구독 토큰(CLAUDE_CODE_OAUTH_TOKEN)으로 동작.

AI_MOCK=1 이면 실제 호출 없이 규칙 기반 가짜 응답을 돌려준다(로컬 테스트용).
"""
import json
import os
import re
import subprocess

from .rules import classify, extract_work


USAGE = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cost_usd": 0.0}


class AIError(Exception):
    """사용량 한도·인증 오류 등. 이번 실행의 AI 작업을 멈추고 다음 실행 때 이어간다."""

    @property
    def fatal(self):
        """한도·인증 문제면 True (멈춤). 그 외 일시적 오류면 해당 묶음만 건너뜀."""
        m = str(self).lower()
        return any(k in m for k in ("limit", "rate", "auth", "login", "credit", "quota", "실행 실패"))


def _call(prompt, model, allow_search=False, max_turns=3, timeout=600):
    cmd = ["claude", "-p", "--output-format", "json", "--model", model,
           "--max-turns", str(max_turns)]
    if allow_search:
        cmd += ["--allowedTools", "WebSearch"]
    try:
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise AIError(f"claude 실행 실패: {e}")
    try:
        out = json.loads(p.stdout)
    except json.JSONDecodeError:
        raise AIError(f"응답 해석 실패 (code {p.returncode}): {p.stdout[-300:]} {p.stderr[-300:]}")
    if out.get("permission_denials"):
        print(f"  (도구 사용 거부됨: {out['permission_denials'][:2]})", flush=True)
    u = out.get("usage") or {}
    USAGE["calls"] += 1
    USAGE["input_tokens"] += u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
    USAGE["cache_read_tokens"] += u.get("cache_read_input_tokens", 0)
    USAGE["output_tokens"] += u.get("output_tokens", 0)
    USAGE["cost_usd"] += out.get("total_cost_usd") or 0
    if out.get("is_error") or out.get("subtype", "success") != "success":
        raise AIError(f"claude 오류 [{out.get('subtype')}]: {str(out.get('result'))[:300]}")
    return out.get("result", "")


def _json_from(text):
    """응답에서 JSON 배열을 찾아 파싱. 앞뒤 설명문·코드블록·여러 배열이 섞여 있어도 처리."""
    dec = json.JSONDecoder()
    best = None
    for m in re.finditer(r"\[", text or ""):
        try:
            obj, _ = dec.raw_decode(text[m.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj):
            if best is None or len(obj) > len(best):
                best = obj
    if best is None:
        raise AIError(f"JSON 배열을 찾지 못함: {(text or '')[:200]}")
    return best


CLASSIFY_PROMPT = """너는 디시인사이드 장르소설(웹소설) 갤러리 글 제목을 분류한다.
각 제목이 "특정 작품이 완결되었다"는 사실을 전제하거나 알리는 글인지 판단해라.

- complete: 작품이 이미 완결됨. 예) "OOO 완결되었네", "OO완결", "야 벌써 OOO완결이네", "OO 완결 후기", "OO 왜 완결임?"(이미 끝났다는 불만)
- not: 완결이 아님. 예) "OOO 언제 완결됨?", "OO완결 예상", "완결까지 몇화 남음", "완결작 추천좀", 특정 작품이 없는 일반 이야기
- 애매해도 둘 중 더 가능성 높은 쪽을 골라라.

work: 제목에 적힌 작품명을 쓰인 그대로(줄임말이면 줄임말 그대로). 작품이 없으면 "".
guess: 네가 확실히 아는 경우에만 정식 작품명. 모르면 "". 추측으로 지어내지 마라.

아래 JSON 배열만 출력해라. 다른 말은 쓰지 마라.
[{"no": 글번호, "label": "complete" 또는 "not", "work": "...", "guess": "..."}]

제목 목록:
"""

SEARCH_PROMPT = """너는 한국 웹소설 제목을 찾는 조사원이다. 아래 이름들은 디시인사이드 장르소설 갤러리에서
쓰인 작품명이며 대부분 줄임말이다. 최근(1~2년 내) 연재작이 많아 네 지식에 없을 수 있으니 반드시 웹 검색으로 확인해라.

검색 요령 (이름마다 필요한 만큼):
- "<이름> 웹소설", "<이름> 노벨피아", "<이름> 문피아", "<이름> 카카오페이지", "<이름> 디시 장르소설"
- 줄임말은 보통 정식 제목 각 어절의 앞글자다 (예: 아집숨 = 아포칼립스에 집을 숨김, 전독시 = 전지적 독자 시점)
- 예시 제목의 문맥(장르, 작가 이름, 플랫폼)을 단서로 써라
- 작가 이름이면 작품이 아니므로 found=false, title에 "작가명"이라고 적어라

판정: 근거 링크로 확인되면 confidence="high", 앞글자 규칙과 정황이 강하게 맞지만 직접 근거가 약하면 confidence="low"로 found=true.
아무 근거도 없으면 found=false. 지어내지 마라.

마지막에 아래 JSON 배열만 출력해라.
[{"alias": "입력 이름 그대로", "found": true/false, "is_author": true/false, "title": "정식 작품명", "author": "작가", "platform": "연재처", "confidence": "high" 또는 "low", "url": "근거 링크"}]

이름 목록:
"""


def classify_titles(items, model):
    """items: [{"no", "title"}] → {no: {"label", "work", "guess"}}"""
    if os.environ.get("AI_MOCK") == "1":
        return {it["no"]: {"label": "complete" if classify(it["title"]) == "complete" or
                           (classify(it["title"]) == "ambiguous" and "?" not in it["title"]) else "not",
                           "work": extract_work(it["title"]), "guess": ""} for it in items}
    lines = "\n".join(f'{it["no"]}\t{it["title"]}' for it in items)
    res = _json_from(_call(CLASSIFY_PROMPT + lines, model))
    out = {}
    for r in res:
        try:
            no = int(r["no"])
        except (KeyError, ValueError, TypeError):
            continue
        out[no] = {"label": "complete" if r.get("label") == "complete" else "not",
                   "work": (r.get("work") or "").strip(), "guess": (r.get("guess") or "").strip()}
    return out


def search_aliases(names, model):
    """names: [(alias, [예시 제목])] → {alias: {...}}"""
    if os.environ.get("AI_MOCK") == "1":
        return {a: {"found": True, "title": a, "author": "", "platform": "", "confidence": "low",
                    "url": ""} for a, _ in names}
    lines = "\n".join(f"{i + 1}. {a}  (예시 제목: {' / '.join(ex[:2])})" for i, (a, ex) in enumerate(names))
    text = _call(SEARCH_PROMPT + lines, model, allow_search=True, max_turns=4 + 3 * len(names))
    res = _json_from(text)
    # 모델이 이름을 살짝 바꿔 적어도(띄어쓰기 등) 맞출 수 있게 정규화 키 → 원래 이름으로 연결
    from .common import norm_key
    want = {norm_key(a): a for a, _ in names}
    out = {}
    for i, r in enumerate(res):
        a = want.get(norm_key(r.get("alias", "")))
        if a is None and len(res) == len(names):
            a = names[i][0]          # 순서대로 대응
        if a:
            out[a] = r
    found = sum(bool(r.get("found")) for r in out.values())
    print(f"  줄임말 검색 {len(names)}개 → 응답 {len(res)}개, 찾음 {found}개", flush=True)
    if not found:
        print(f"  (응답 앞부분: {text[:300]!r})", flush=True)
    return out


REVIEW_PROMPT = """너는 디시인사이드 장르소설(웹소설) 갤러리 글 제목 분류의 최종 검수자다.
아래 제목들은 1차 판정에서 규칙과 AI의 의견이 갈렸다. 갤러리 말투(줄임말·반어·드립)를 고려해 신중히 판단해라.

- complete: 제목이 특정 작품이 이미 완결되었음을 전제하거나 알린다 (후기, 감상, 급완결 불만, "왜 완결임" 등 포함)
- not: 완결 예정·예상·질문, 완결 여부 자체를 묻는 글, 완결작 일반 추천, 특정 작품이 없는 글
work: 제목에 쓰인 작품명 그대로(없으면 ""). reason: 판단 근거 한 줄(한국어).

아래 JSON 배열만 출력해라.
[{"no": 글번호, "label": "complete" 또는 "not", "work": "...", "reason": "..."}]

제목 목록 (글번호, 제목, 규칙 판정, 1차 AI 판정):
"""


def review_titles(items, model):
    """items: [{"no","title","rule","ai"}] → {no: {"label","work","reason"}}"""
    if os.environ.get("AI_MOCK") == "1":
        return {it["no"]: {"label": it["ai"], "work": extract_work(it["title"]), "reason": "mock"} for it in items}
    lines = "\n".join(f'{it["no"]}\t{it["title"]}\t규칙={it["rule"]}\tAI={it["ai"]}' for it in items)
    res = _json_from(_call(REVIEW_PROMPT + lines, model))
    out = {}
    for r in res:
        try:
            out[int(r["no"])] = {"label": "complete" if r.get("label") == "complete" else "not",
                                 "work": (r.get("work") or "").strip(), "reason": (r.get("reason") or "").strip()}
        except (KeyError, ValueError, TypeError):
            continue
    return out


EXTRACT_PROMPT = """아래는 디시인사이드 장르소설 갤러리에서 쓰인 웹소설 이름(대부분 줄임말)과,
그 이름으로 구글에서 검색한 상위 결과다. 검색 결과에 근거해 정식 작품명을 찾아라.

- 검색 결과 제목/요약에 정식 작품명이 분명히 보이면 found=true, confidence="high"
- 결과가 애매하거나 여러 작품이 섞여 확정이 어려우면 confidence="low" (그래도 가장 유력한 것)
- 결과에 근거가 없으면 found=false. 검색 결과에 없는 제목을 지어내지 마라.
- 이름이 작품이 아니라 작가 이름(필명)이면 found=false, is_author=true. 갤러리 예시 제목에 "OO 신작", "OO 이번 작품"처럼 쓰였다면 작가일 가능성이 높다.

아래 JSON 배열만 출력해라.
[{"alias": "입력 이름 그대로", "found": true/false, "is_author": true/false, "title": "정식 작품명", "author": "작가(보이면)", "platform": "연재처(보이면)", "confidence": "high"/"low", "url": "근거 링크"}]

"""


def extract_from_results(items, model):
    """items: [(alias, examples, results)] → {alias: {...}}"""
    if os.environ.get("AI_MOCK") == "1":
        return {a: {"found": bool(res), "title": res[0]["title"] if res else "", "confidence": "high",
                    "url": res[0]["link"] if res else ""} for a, _, res in items}
    blocks = []
    for i, (a, ex, res) in enumerate(items):
        lines = "\n".join(f"  - {r['title']} | {r['snippet'][:150]} | {r['link']}" for r in res[:8])
        blocks.append(f"[{i + 1}] 이름: {a}\n  갤러리 예시 제목: {' / '.join(ex[:2])}\n  구글 결과:\n{lines or '  (결과 없음)'}")
    res = _json_from(_call(EXTRACT_PROMPT + "\n\n".join(blocks), model))
    from .common import norm_key
    want = {norm_key(a): a for a, _, _ in items}
    out = {}
    for i, r in enumerate(res):
        a = want.get(norm_key(r.get("alias", "")))
        if a is None and len(res) == len(items):
            a = items[i][0]
        if a:
            out[a] = r
    return out
