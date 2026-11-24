"""규칙 기반 판정: 제목이 '어떤 작품이 완결됐다'는 글인지 + 작품명 추출.

라벨: complete(완결됨) / not(완결 아님) / ambiguous(규칙으로 판단 불가 → AI)
규칙을 고치면 다음 실행 때 과거 글 전체에 다시 적용된다(판정 결과를 저장하지 않음).
"""
import re

RULES_VERSION = 2

# 완결이 아님: 질문·예상·바람·일반 추천 등
NOT_PATTERNS = [
    r"완결\s*(까지|전에|전\b|나면|되면|하면|날\s*때|예정|예상|각|나기|되기|안\s*나|못|가능|기원|기다|하길|해라|해줘|좀|시켜|내줘|언제)",
    r"(언제|몇\s*화|남았|남음|남은|예정|예상|임박|카운트)",
    r"완결\s*작\s*(추천|있|뭐|중|들|목록|리스트|만|위주)|완결\s*(난|된|한)\s*(거|것|작품|소설|웹소)\s*(추천|있|뭐|중|들|좀)",
    r"추천|추천좀|ㅊㅊ|뭐\s*(볼|읽)",
    r"(미|비|안\s*)완결|연중|연재\s*중단|무기한",
    r"완결\s*(나|되|났|됐|됨|임)\s*(냐|나요|었나|었냐|을까|ㄴ가|는지)",
    r"(했으면|났으면|됐으면|하겠지|하겠냐|할까|될까|나려나|되려나)",
]

# 완결됨
COMPLETE_PATTERNS = [
    r"왜\s*완결",                                   # "이거 왜 완결임?" = 이미 끝남
    r"(급|강제|조기)\s*완결(?!\s*(로|으로|각|될|할|날|나려|되려|낼|내려|칠|치려|예정|분위기|느낌|조짐))",  # 급완결·강제완결 = 끝난 것
    r"완결\s*(난|된|낸)\s*거\s*(알|모르|실화|같|맞|봐|보)",           # 완결난거 알아? / 같은데
    r"완결\s*까지\s*(다\s*)?(봤|본|봄|읽었|읽은|달렸|달린|냈|정주행\s*(했|함|완료))",
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


_AMBIG = [re.compile(p) for p in [
    r"\d+\s*(년|달|개월|화)\s*(뒤|후|만에)?\s*완결\s*(이었|예정|이라)",   # 원래 1년 뒤 완결이었다
    r"언제\s*완결\s*(났|됐|되었)",                                        # 언제 완결났대 (과거형)
]]


def classify(title):
    t = re.sub(r"\s+", " ", title or "").strip()
    if "완결" not in t:
        return "not"
    if any(p.search(t) for p in _AMBIG):
        return "ambiguous"
    if any(p.search(t) for p in _COMPLETE[:3]):   # '왜 완결', '급완결', '완결까지 봤' 은 다른 표현이 섞여도 완결
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


# 작품명이 아닌 것 (연재처·일반 명사). 정규화 키 기준
NOT_WORKS = {"노피아", "문피아", "카카페", "카카오페이지", "카카오", "네이버", "시리즈", "네이버시리즈",
             "리디", "리디북스", "조아라", "블라이스", "1부", "2부", "3부", "시즌1", "시즌2", "외전",
             "본편", "웹소", "웹소설", "소설", "작품", "이거", "그거", "이번달", "이번주", "오늘", "요즘",
             "드디어", "벌써", "결국", "작가", "신작", "연재작"}
