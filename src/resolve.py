"""최종 판정 규칙과 작품명 → 작품 ID 연결. judge/aggregate가 함께 쓴다."""
import csv
import hashlib

from .common import OVERRIDES, norm_key
from .rules import NOT_WORKS, classify, extract_work


def load_overrides():
    """review/overrides.csv → {no: {"label", "work_title"}}"""
    out = {}
    if not OVERRIDES.exists():
        return out
    with open(OVERRIDES, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            try:
                no = int((r.get("no") or "").strip())
            except ValueError:
                continue
            label = (r.get("label") or "").strip().lower()
            label = {"완결": "complete", "o": "complete", "제외": "not", "x": "not"}.get(label, label)
            out[no] = {"label": label if label in ("complete", "not") else "",
                       "work_title": (r.get("work_title") or "").strip()}
    return out


def sampled(no, rate):
    return int(hashlib.md5(str(no).encode()).hexdigest(), 16) % 1000 < rate * 1000


def needs_ai(post, mode, rate):
    if mode == "verify":
        return True
    return classify(post["title"]) == "ambiguous" or sampled(post["no"], rate)


def decide(post, ai, ov):
    """→ dict(label, source, rule, ai, disagree)"""
    rule = classify(post["title"])
    ai_label = ai["label"] if ai else None
    disagree = bool(ai_label and rule != "ambiguous" and rule != ai_label)
    if ov and ov.get("label"):
        label, source = ov["label"], "검수"
    elif ai_label and (rule == "ambiguous" or disagree):
        label, source = ai_label, "AI"
    elif rule != "ambiguous":
        label, source = rule, "규칙" if not ai_label else "규칙+AI"
    else:
        label, source = None, "대기"   # AI 판정 대기
    return {"label": label, "source": source, "rule": rule, "ai": ai_label, "disagree": disagree}


def work_name(post, ai, ov):
    """→ (제목에 쓰인 작품명, AI가 아는 정식 제목). 작품명이 아니면 ('', '')"""
    if ov and ov.get("work_title"):
        return ov["work_title"], ov["work_title"]
    if ai and ai.get("work"):
        name, guess = ai["work"], ai.get("guess", "")
    else:
        name, guess = extract_work(post["title"]), ""
    if norm_key(name) in NOT_WORKS:
        name = ""
    return name, guess


def resolve_id(name, guess, aliases):
    for n in (name, guess):
        k = norm_key(n)
        if k and k in aliases:
            return aliases[k]
    return None
