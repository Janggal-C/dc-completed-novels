"""사전 대조 엔진 테스트: python tests/test_matcher.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.matcher import Matcher

A = {"4군6진": "w1", "단종구하러4군6진": "w1", "종말뱀": "w2", "러스트": "w3", "약먹마": "w4", "전독시": "w5",
     "화귀": "w6", "임기": "w7"}
m = Matcher(A)
assert set(m.find("4군6진에 이어 종말뱀도 완결났구나")) == {"w1", "w2"}
assert set(m.find("단종 구하러 4군6진 완결")) == {"w1"}
assert m.find("완결 기념 일러스트") == {}               # 단어 중간은 제외
assert set(m.find("약먹마랑 전독시 둘다 완결")) == {"w4", "w5"}
assert set(m.find("화귀 언제 완결")) == {"w6"}          # 2글자는 단어로 정확히 있을 때만
assert m.find("화귀환 어쩌구") == {}
assert m.find("임기 첫날") == {}                         # 흔한 단어는 제외
print("✅ 대조 엔진 테스트 통과")
