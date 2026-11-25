"""전체 제목에서 사전에 없는 '작품 이름 후보 단어'를 찾고, AI로 단어를 분류한다.

1) 후보 추리기(프로그램): 제목을 단어로 나눠 조사를 떼고, 여러 작성자가 쓴 단어 중
   사전·작가 목록에 없고, 동사·어미·감탄 같은 꼴이 아닌 것
2) 단어 분류(AI, haiku): 예시 제목 2~3개와 함께 보여주고
   work(작품명·줄임말) / common(일반 단어) / slang(갤러리 은어·밈) / person(작가·캐릭터·실존인물) / other
   로 나눈다. 한 단어는 한 번만 묻고 결과는 data/word_labels.json 에 쌓는다.
3) work 로 분류된 단어만 구글 검색 대상이 된다 (bulk/judge).
"""
import os
import random
import re
import sys
from collections import Counter, defaultdict

from . import ai
from .common import ALIASES, AUTHORS, DATA, load_config, norm_key, now_kst, read_json, write_json
from .rules import NOT_WORKS

LABELS = DATA / "word_labels.json"
TOK = re.compile(r"[가-힣A-Za-z0-9]+")
PART = re.compile(r"(은|는|이|가|도|을|를|의|에|에서|이랑|랑|하고|까지|부터|만|이네|이냐|냐|임|처럼|보다|으로|로|와|과|한테|에게|좀|들|같은|같이|이나|나)$")
END = re.compile(r"(다|요|네|음|함|됨|냐|지|고|서|면|는|던|게|데|니|까|자|죠|라|야|여|세|쇼|군|구나|더라|ㅋ|ㅎ|ㅠ|ㅜ|ㄷ|ㅇ)$")
VERB = re.compile(r"(하는|했|하고|하면|해서|한다|봤|보는|보고|볼|본|있|없|같|좋|싫|재밌|재미|웃|ㅋㅋ|어떻|왜|뭐|누가|언제|진짜|존나|씨발|시발)")


def tokens(title):
    out = []
    for tok in TOK.findall(title.lower()):
        k = PART.sub("", tok) if len(tok) > 2 else tok
        if 2 <= len(k) <= 12 and not k.isdigit():
            out.append(k)
    return out


def build_candidates(titles, min_writers=10):
    aliases = read_json(ALIASES, {})
    authors = {norm_key(a) for a in read_json(AUTHORS, [])}
    labels = read_json(LABELS, {})
    wr, cnt, ex, mon, days = defaultdict(set), Counter(), defaultdict(list), defaultdict(Counter), defaultdict(set)
    for r in titles.values():
        for k in set(tokens(r["title"])):
            wr[k].add(r["writer"])
            cnt[k] += 1
            mon[k][r["date"][:7]] += 1
            days[k].add(r["date"][:10])
            if len(ex[k]) < 3:
                ex[k].append(r["title"])
    out = {}
    for k, ws in wr.items():
        # 자동 후보 기준: 작성자 10명 이상 + 3일 이상에 걸쳐 쓰임 (하루 도배 제외)
        if len(ws) < min_writers or len(days[k]) < 3 or k in aliases or k in authors or k in NOT_WORKS or k in labels:
            continue
        if END.search(k) or VERB.search(k) or not re.search("[가-힣a-z]", k):
            continue
        tot = sum(mon[k].values())
        out[k] = {"w": len(ws), "c": cnt[k], "burst": round(max(mon[k].values()) / tot, 2), "ex": ex[k]}
    return out


CLASSIFY_PROMPT = """디시인사이드 장르소설(웹소설) 갤러리 글 제목에 자주 나오는 단어들이다.
각 단어를 예시 제목의 문맥을 보고 하나로 분류해라.

- work: 특정 웹소설·웹툰 작품의 제목이나 줄임말 (예: 전독시, 약먹마, 화산귀환, 가펑)
- common: 일반 단어·장르 용어 (예: 주인공, 히로인, 추천, 무협, 회귀, 빙의, 로판)
- slang: 갤러리 은어·밈·별명·사건 (예: 장붕이, 념글, 완장, 두쫀쿠)
- person: 작가 필명, 작품 속 캐릭터 이름, 실존 인물·스트리머
- other: 플랫폼·회사·게임·애니 등 웹소설이 아닌 고유명사, 기타

애매하면 문맥상 가장 가능성 높은 것으로. 아래 JSON 배열만 출력해라.
[{"w": "단어 그대로", "t": "work|common|slang|person|other"}]

"""


def classify(words, cands, model):
    if os.environ.get("AI_MOCK") == "1":
        return {w: "work" if cands[w]["burst"] > 0.3 else "common" for w in words}
    def line(w):
        hint = f"  [노벨피아 순위 제목과 조합 일치: {' / '.join(cands[w]['rk'][:3])}]" if cands[w].get("rk") else ""
        return f"- {w}  (예: {' / '.join(x[:40] for x in cands[w]['ex'][:3])}){hint}"
    lines = "\n".join(line(w) for w in words)
    res = ai._json_from(ai._call(CLASSIFY_PROMPT + lines, model))
    out = {}
    for r in res:
        w = (r.get("w") or "").strip().lower()
        if w in cands and r.get("t") in ("work", "common", "slang", "person", "other"):
            out[w] = r["t"]
    return out


def run(batch=150, max_minutes=300, limit=None):
    """후보 단어 전체를 AI로 분류 (이미 분류한 단어는 건너뜀). 많이 쓰인 단어부터, 묶음마다 저장"""
    import time
    from .common import checkpoint
    from .fullcrawl import load_titles
    cfg = load_config()
    deadline = time.time() + max_minutes * 60
    cands = build_candidates(load_titles(), cfg.get("discover", {}).get("min_writers", 10))
    labels = read_json(LABELS, {})
    from .resolve import removed
    gone = removed()
    todo = [w for w in sorted(cands, key=lambda w: -cands[w]["w"]) if w not in labels and w not in gone][:limit]
    from . import abbrev
    rk = abbrev.ranking_titles()
    for w in todo:
        cands[w]["rk"] = abbrev.find(w, rk)[:3]
    print(f"후보 {len(cands):,}개 중 분류할 것 {len(todo):,}개", flush=True)
    done = 0
    for i in range(0, len(todo), batch):
        if time.time() > deadline:
            print("시간 제한 → 다음 실행 때 이어서")
            break
        chunk = todo[i:i + batch]
        try:
            res = classify(chunk, cands, cfg["judge"]["model"])
        except ai.AIError as e:
            print(f"⚠️ AI 오류: {e}", file=sys.stderr)
            if e.fatal:
                break
            continue
        today = now_kst().strftime("%Y-%m-%d")
        for w in chunk:
            if w in res:
                c = cands[w]
                labels[w] = {"t": res[w], "w": c["w"], "burst": c["burst"], "ex": c["ex"][:2], "date": today, **({"rk": c["rk"]} if c.get("rk") else {})}
        done += len(res)
        write_json(LABELS, labels)
        cnt = Counter(v["t"] for v in labels.values())
        print(f"  {i + len(chunk):,}/{len(todo):,} · 누적 {dict(cnt)}", flush=True)
        checkpoint(f"단어 분류 {i + len(chunk):,}/{len(todo):,}", force=(i == 0), report=False)
    print(f"분류 완료 {done:,}개 · AI 사용량 {ai.USAGE}")


def test(n=100):
    """후보 n개를 뽑아 분류만 해보고 출력 (저장 안 함)"""
    from .fullcrawl import load_titles
    cfg = load_config()
    cands = build_candidates(load_titles(), cfg.get("discover", {}).get("min_writers", 10))
    print(f"후보 단어 {len(cands):,}개")
    ranked = sorted(cands, key=lambda w: -cands[w]["w"])
    random.seed(7)
    if os.environ.get("PICK") == "burst":     # 특정 달에 몰린 단어 위주 (작품명이 많은 쪽)
        bursty = [w for w in ranked if cands[w]["burst"] >= 0.3 and cands[w]["w"] >= 20]
        pick = bursty[:n]
    else:
        pick = ranked[: n // 2] + random.sample(ranked[n // 2:], n - n // 2)
    res = classify(pick, cands, cfg["judge"]["model"])
    print(f"분류 결과 {len(res)}/{len(pick)}  사용량 {ai.USAGE}")
    by = defaultdict(list)
    for w in pick:
        by[res.get(w, "?")].append(f"{w}({cands[w]['w']})")
    for t in ("work", "person", "slang", "other", "common", "?"):
        print(f"[{t}] {len(by[t])}개: {', '.join(by[t])}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        run()
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test(int(sys.argv[2]) if len(sys.argv) > 2 else 100)
