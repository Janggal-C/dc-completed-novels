"""완결 상태 판정 단위 테스트: python tests/test_status.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.status import judge


def P(d, w):
    return {"date": f"2026-{d} 12:00:00", "writer": w}


# 진짜 완결: 6/3 혼자 언급(잡음) → 6/26 대량 언급
c = [P("06-03", "a")] + [P("06-26", f"w{i}") for i in range(20)] + [P("06-27", f"x{i}") for i in range(5)]
r = judge(c, [P("06-10", "q")])
assert r["status"] == "완결" and r["date"] == "2026-06-26", r

# 연재작: 완결 오판 몇 개 + '언제 완결' 질문 다수
c = [P(f"{m:02d}-1{d}", f"w{m}{d}") for m, d in [(6, 3), (7, 3), (10, 2), (11, 1)]]
q = [P(f"{m:02d}-0{d}", f"q{m}{d}") for m in range(6, 12) for d in range(1, 9)]
r = judge(c, q)
assert r["status"] == "연재중", r

# 예전 완결작: 몰린 시점 없이 꾸준히 '완결'로만 언급
c = [P(f"{m:02d}-15", f"w{m}") for m in range(6, 12)]
r = judge(c, [P("07-01", "q")])
assert r["status"] == "예전 완결", r

# 공식 상태가 연재중이면 무조건 제외
r = judge([P("06-26", f"w{i}") for i in range(10)], [], official="연재중")
assert r["status"] == "연재중", r

print("✅ 완결 상태 판정 테스트 통과")
