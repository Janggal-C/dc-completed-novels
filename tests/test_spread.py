"""같이 쓰임(cooccur) 검사 테스트: python tests/test_spread.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.spread import cooccur

A = {"저능버": "저능아하꼬버튜버", "짱햄": "저능아하꼬버튜버", "괴이왕국": "괴이왕국의패왕군주",
     "패왕군주": "괴이왕국의패왕군주"}
T = {i: {"title": t} for i, t in enumerate([
    "저능버 짱햄 요즘 폼 미친듯", "저능버) 짱햄이 논리로 압살", "짱햄 진자 뜌땨이네", "저능버 재밌네",
    "괴이왕국 패왕군주 재밌다", "패왕군주 신작"])}
c = cooccur(["짱햄", "패왕군주", "없는이름"], A, T)
assert c["짱햄"] == {"n": 3, "co": 0.67}, c
assert c["패왕군주"]["co"] == 0          # 제목 조각은 같이 나와도 정상
assert "없는이름" not in c
from src.spread import _in_order
assert _in_order("외신마도서", "외신이쓴마도서를주웠다")      # 덜 줄인 꼴 = 같은 작품
assert not _in_order("아카흑막딸", "아카데미흑막시점")        # 다른 작품
print("✅ 같이 쓰임 검사 테스트 통과")
