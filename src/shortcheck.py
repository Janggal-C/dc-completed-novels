"""2글자 줄임말 검수: 갤에서 그 단어가 주로 작품을 뜻하는지, 일반 단어로 더 많이 쓰이는지 AI(haiku)가 판정

sample (로컬/Actions): 전체 제목에서 단어로 쓰인 예시를 모아 data/short_samples.json
run   (Actions): haiku 판정 → 일반 단어면 dict/weak_aliases.json 에 추가 (사전에는 그대로, 대조·집계·확장에서만 제외)
"""
import json
import random
import sys
from collections import defaultdict

from . import ai
from .common import ALIASES, DATA, WORKS, checkpoint, load_config, read_json, write_json
from .fullcrawl import load_titles
from .matcher import WEAK, _PARTICLES, _TOKEN

SAMPLES = DATA / "short_samples.json"

PROMPT = """디시인사이드 장르소설(웹소설) 갤러리 글 제목에서 아래 짧은 단어들이 쓰인 예시다.
각 단어가 이 갤러리에서 '주로' 해당 웹소설을 가리키는 줄임말로 쓰이는지, 아니면 일반 단어·다른 뜻으로 더 많이 쓰이는지 판정해라.
- 예시 제목의 절반 이상이 그 작품 얘기면 "work", 아니면 "general"
- 작품 얘기인지 애매하면 "general"
아래 JSON 배열만 출력해라.
[{"alias": "단어 그대로", "v": "work" 또는 "general", "why": "짧은 이유"}]

"""


def sample(n=12):
    aliases = read_json(ALIASES, {})
    works = read_json(WORKS, {})
    short = {k for k in aliases if len(k) <= 2}
    hits = defaultdict(list)
    count = defaultdict(int)
    for row in load_titles().values():
        t = row["title"]
        for tok in _TOKEN.findall(t.lower()):
            for x in (tok, _PARTICLES.sub("", tok)):
                if x in short:
                    count[x] += 1
                    if len(hits[x]) < 200:
                        hits[x].append(t)
                    break
    rnd = random.Random(1)
    out = {k: {"title": works.get(aliases[k], {}).get("title", ""), "n": count[k],
               "ex": rnd.sample(hits[k], min(n, len(hits[k])))} for k in short}
    write_json(SAMPLES, out)
    print(f"2글자 줄임말 {len(short)}개, 예시 수집 완료")


def run(batch=25):
    model = load_config()["judge"]["model"]
    samples = read_json(SAMPLES, {})
    weak = read_json(WEAK, {})
    checked = read_json(DATA / "short_checked.json", {})
    todo = [k for k in samples if k not in checked and samples[k]["ex"]]
    print(f"판정 대상 {len(todo)}개", flush=True)
    for i in range(0, len(todo), batch):
        part = todo[i:i + batch]
        blocks = [f"[{k}] → 작품: {samples[k]['title']}\n" + "\n".join(f"  - {e}" for e in samples[k]["ex"]) for k in part]
        try:
            res = ai._json_from(ai._call(PROMPT + "\n\n".join(blocks), model))
        except ai.AIError as e:
            print(f"⚠️ {e}", file=sys.stderr)
            if e.fatal:
                break
            continue
        got = {r.get("alias"): r for r in res if isinstance(r, dict)}
        for k in part:
            r = got.get(k)
            if not r:
                continue
            checked[k] = r.get("v")
            if r.get("v") == "general":
                weak[k] = {"title": samples[k]["title"], "why": r.get("why", "")}
            else:
                weak.pop(k, None)
        write_json(WEAK, weak)
        write_json(DATA / "short_checked.json", checked)
        print(f"  {min(i + batch, len(todo))}/{len(todo)} · 일반 단어 {len(weak)}개", flush=True)
        checkpoint("2글자 줄임말 검수", every_seconds=300)
    print("일반 단어로 판정:", ", ".join(f"{k}({v['title']})" for k, v in weak.items()))


if __name__ == "__main__":
    {"sample": sample, "run": run}[sys.argv[1]]()
