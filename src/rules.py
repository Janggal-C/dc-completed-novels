"""규칙 기반 판정: 제목이 '어떤 작품이 완결됐다'는 글인지 + 작품명 추출.

라벨: complete(완결됨) / not(완결 아님) / ambiguous(규칙으로 판단 불가 → AI)
규칙을 고치면 다음 실행 때 과거 글 전체에 다시 적용된다(판정 결과를 저장하지 않음).
"""
import re

RULES_VERSION = 1

# 완결이 아님: 질문·예상·바람·일반 추천 등
NOT_PATTERNS = [
    r"완결\s*(까지|전에|전\b|나면|되면|하면|날\s*때|예정|예상|각|나기|되기|안\s*나|못|가능|기원|기다|하길|해라|해줘|좀|시켜|내줘|언제)",
    r"(언제|몇\s*화|남았|남음|남은|예정|예상|임박|카운트)",
    r"완결\s*(작|난\s*(거|것|작품|소설|웹소)|된\s*(거|것|작품|소설|웹소)|한\s*(거|것|작품|소설))",
    r"추천|추천좀|ㅊㅊ|뭐\s*(볼|읽)",
    r"(미|비|안\s*)완결|연중|연재\s*중단|무기한",
    r"완결\s*(나|되|났|됐|됨|임)\s*(냐|나요|었나|었냐|을까|ㄴ가|는지)",
    r"(했으면|났으면|됐으면|하겠지|하겠냐|할까|될까|나려나|되려나)",
]

# 완결됨
COMPLETE_PATTERNS = [
    r"왜\s*완결",                                   # "이거 왜 완결임?" = 이미 끝남
    r"완결\s*(났|됐|되었|했|함|남\b|됨|이네|이었|이구나|이라니|이다|이야|입니다|ㄷ|ㅋ|ㅠ|ㅜ|!|기념|후기|감상|소감|축하|ㅊㅋ|보고|봤|봄|찍|ㅅㅂ|ㅈㄴ|ㄹㅇ)",
    r"(벌써|드디어|마침내|결국|어느새|ㄷㄷ).{0,25}완결",
    r"완결\s*$",                                    # "OO 완결"
]

_NOT = [re.compile(p) for p in NOT_PATTERNS]
_COMPLETE = [re.compile(p) for p in COMPLETE_PATTERNS]

_QUOTE = re.compile(r"[「『\"“'‘<《〈\[](.{2,40}?)[」』\"”'’>》〉\]]")
_LEADING = re.compile(
    r"^(?:(?:야|와|와씨|헐|아|ㅋ+|ㅎ+|벌써|드디어|결국|마침내|어느새|이거|그거|오늘|방금|어제|님들|형들|얘들아|근데|와우|ㄷㄷ|ㅅㅂ|씨발|시발|진짜|ㄹㅇ)\s*[!~.,]*\s*|(?:그|이|저)\s+)+")
_TRAILING = re.compile(
    r"(?:\s*(?:이|가|은|는|도|이제|드디어|벌써|결국|도\s*결국|이것도|얘도|님|작가|작|왜|이거\s*왜|얘\s*왜|오늘|어제|이번에|진짜|ㄹㅇ))+\s*$")


def classify(title):
    t = re.sub(r"\s+", " ", title or "").strip()
    if "완결" not in t:
        return "not"
    if _COMPLETE[0].search(t):          # '왜 완결' 은 질문형이어도 완결
        return "complete"
    if any(p.search(t) for p in _NOT):
        return "not"
    if any(p.search(t) for p in _COMPLETE):
        return "complete"
    return "ambiguous"


def extract_work(title):
    """제목에서 작품명(줄임말일 수 있음)을 뽑는다. 못 찾으면 ''."""
    t = re.sub(r"\s+", " ", title or "").strip()
    m = _QUOTE.search(t)
    if m and "완결" not in m.group(1):
        return m.group(1).strip()
    if "<-" in t or "←" in t:
        cand = re.split(r"<-|←", t)[0]
    else:
        idx = t.find("완결")
        cand = t[:idx] if idx > 0 else ""
    cand = re.sub(r"[ㅋㅎㅠㅜㄷ]{2,}", " ", cand)
    cand = re.sub(r"[?!~.,…]+", " ", cand).strip()
    cand = _LEADING.sub("", cand).strip()
    cand = _TRAILING.sub("", cand).strip()
    return cand if 1 < len(cand) <= 40 else ""
