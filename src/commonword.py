"""사전 정리: 일상·장르 대화에서 다른 뜻으로도 쓰일 수 있는 '일반 단어' 이름은 사전에서 아예 뺀다.

기준 (사용자 결정 2026-11-25): 명확하게 줄임말이거나 독특한 제목만 남긴다.
  - 빼기: 수선, s급, 달빛, 도시, 화산, 판사, 대마법사 … (거의 그 작품 뜻이어도 일반어로 쓰일 수 있으면 뺌)
  - 남기기: 니생, 가펑, 달조, 담텔, 판초우, 눈마새, 전독시 같은 줄임말·독특한 제목
빠진 이름은 dict/removed.json 에 기록 → 자동 검색·등록으로 다시 들어오지 않음 (검수 탭 직접 입력으로는 다시 넣을 수 있음)
결과: data/commonword.json {이름: "remove"|"keep"}
"""
import sys

from . import ai
from .common import ALIASES, DATA, DICT, WORKS, checkpoint, load_config, read_json, write_json
from .matcher import AMBIGUOUS, WEAK

OUT = DATA / "commonword.json"
PROMPT = """아래는 웹소설 갤러리용 줄임말 사전의 '이름 → 작품' 목록이다. 각 이름을 판정해라.

- "remove": 이름이 일반적인 단어·표현이라 작품과 상관없는 대화에서도 쓰일 수 있는 경우.
  작품을 가리킬 때가 대부분이어도 일상어·장르 용어로 쓰일 수 있으면 remove.
  예) 수선, s급, 달빛, 도시, 화산, 판사, 대마법사, 헌터, 아카데미, 심해, 종말, 사신, 패왕, bj, 북미, 탑의
- "keep": 누가 봐도 그 작품의 줄임말이거나, 일상에서 쓰일 일 없는 독특한 제목·고유명사.
  예) 니생, 가펑, 달조, 담텔, 판초우, 눈마새, 전독시, 나혼렙, 회맹성, 약먹마, 화산귀환
- 애매하면 remove.
이름은 띄어쓰기를 없앤 형태다. 아래 JSON 배열만 출력해라.
[{"a": "이름 그대로", "v": "remove" 또는 "keep"}]

"""


def run(batch=120):
    model = load_config()["judge"]["model"]
    aliases = read_json(ALIASES, {})
    works = read_json(WORKS, {})
    done = read_json(OUT, {})
    todo = [k for k in aliases if k not in done]
    print(f"판정 대상 {len(todo)}개 / 전체 {len(aliases)}개", flush=True)
    for i in range(0, len(todo), batch):
        part = todo[i:i + batch]
        lines = "\n".join(f"{k} → {works.get(aliases[k], {}).get('title', '')}" for k in part)
        try:
            res = ai._json_from(ai._call(PROMPT + lines, model))
        except ai.AIError as e:
            print(f"⚠️ {e}", file=sys.stderr)
            if e.fatal:
                break
            continue
        got = {r.get("a"): r.get("v") for r in res if isinstance(r, dict)}
        for k in part:
            if got.get(k) in ("remove", "keep"):
                done[k] = got[k]
        write_json(OUT, done)
        print(f"  {min(i + batch, len(todo))}/{len(todo)} · 빼기 {sum(v == 'remove' for v in done.values())}", flush=True)
        checkpoint("일반 단어 판정", every_seconds=300)
    apply()


def apply():
    """판정 결과 + 기존 AMBIGUOUS + 2글자 검수에서 일반 단어로 나온 것 → 사전에서 제거"""
    aliases = read_json(ALIASES, {})
    works = read_json(WORKS, {})
    done = read_json(OUT, {})
    removed = set(read_json(DICT / "removed.json", []))
    drop = {k for k, v in done.items() if v == "remove"} | set(AMBIGUOUS) | set(read_json(WEAK, {}))
    gone = []
    for k in sorted(drop):
        if k in aliases:
            # 직접 입력한 것도 일반 단어면 뺀다 (사용자 결정)
            gone.append(f"{k}({works.get(aliases[k], {}).get('title', '')})")
            aliases.pop(k)
        removed.add(k)
    write_json(ALIASES, aliases)
    write_json(DICT / "removed.json", sorted(removed))
    write_json(WEAK, {})
    print(f"사전에서 뺀 이름 {len(gone)}개: " + ", ".join(gone))


if __name__ == "__main__":
    {"run": run, "apply": apply}[sys.argv[1] if len(sys.argv) > 1 else "run"]()
