"""제목에서 사전에 있는 작품 이름을 전부 찾는 대조 엔진 (AI 없음).

- 3글자 이상 이름: 띄어쓰기·기호를 무시하고 제목 안에서 찾는다.
  겹치면 긴 이름 우선 ("단종구하러4군6진" 안의 "4군6진"은 따로 세지 않음)
- 2글자 이름: 흔한 단어와 겹치기 쉬워서, 제목의 한 단어(조사 제거)와 정확히 같을 때만
- 흔한 단어와 겹치는 이름(AMBIGUOUS)은 대조에서 제외 (AI가 뽑은 이름으로만 셈)
같은 규칙을 나중에 전체 제목 언급 집계와 브라우저 확장에서도 쓴다.
"""
import re

from .common import DICT, norm_key, read_json

WEAK = DICT / "weak_aliases.json"   # AI 판정: 갤에서 주로 일반 단어로 쓰이는 짧은 이름 (사전엔 두고 대조에서만 제외)


def excluded():
    return AMBIGUOUS | set(read_json(WEAK, {}).keys())

# 일반 단어와 겹쳐서 제목 대조에 쓰면 오탐이 나는 이름
AMBIGUOUS = {"s급", "스급", "나만", "대영", "임기", "코메", "아생", "생갤", "니생", "그살",
             "고아원장", "마법소녀", "러스트", "아카데미", "헌터", "회귀자", "마법사", "용사", "악녀"}
_PARTICLES = re.compile(r"(은|는|이|가|도|을|를|의|에|에서|이랑|랑|하고|까지|부터|만|이네|처럼|보다|이랑|임|이냐|냐|나|야)$")
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


class Matcher:
    def __init__(self, aliases, min_len=3):
        skip = excluded()
        self.long = sorted((k for k in aliases if len(k) >= min_len and k not in skip), key=len, reverse=True)
        self.short = {k for k in aliases if len(k) < min_len and k not in skip}
        self.aliases = aliases

    @staticmethod
    def _key_with_starts(title):
        """정규화 문자열 + 각 글자가 원래 제목에서 단어 첫 글자인지"""
        chars, starts = [], []
        prev_word = False
        for ch in title.lower():
            is_word = bool(_TOKEN.match(ch))
            if is_word:
                chars.append(ch)
                starts.append(not prev_word)
            prev_word = is_word
        return "".join(chars), starts

    def find(self, title):
        """제목 → {작품 ID: 찾은 이름}
        6글자 미만 이름은 단어 첫머리에서 시작할 때만 인정 ("일러스트" 안의 "러스트" 제외)"""
        key, starts = self._key_with_starts(title)
        used = [False] * len(key)
        found = {}
        for a in self.long:
            start = key.find(a)
            while start != -1:
                end = start + len(a)
                if (len(a) >= 6 or starts[start]) and not any(used[start:end]):
                    for i in range(start, end):
                        used[i] = True
                    found.setdefault(self.aliases[a], a)
                start = key.find(a, start + 1)
        for tok in _TOKEN.findall(title.lower()):
            for t in (tok, _PARTICLES.sub("", tok)):
                if t in self.short:
                    found.setdefault(self.aliases[t], t)
        return found
