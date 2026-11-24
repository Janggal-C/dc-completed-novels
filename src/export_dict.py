"""확장 프로그램용 사전 공개 파일: docs/api/dict.json

{
  "version": "2026-11-25T01:10",
  "rules": {"min_len": 3, "full_from": 6, "ambiguous": [...]},   # 대조 규칙 (src/matcher.py 와 동일)
  "works": {"id": {"t": 정식 제목, "a": 작가, "p": 연재처, "s": "완결|연재중|", "u": 링크}},
  "aliases": {"정규화된 줄임말": "작품 id"}
}
"""
import json

from .common import ALIASES, ROOT, WORKS, now_kst, read_json
from .matcher import AMBIGUOUS


def run():
    works = read_json(WORKS, {})
    aliases = read_json(ALIASES, {})
    used = set(aliases.values())
    out_works = {}
    for wid in used:
        w = works.get(wid)
        if not w:
            continue
        src = w.get("source", "")
        out_works[wid] = {k: v for k, v in {
            "t": w["title"], "a": w.get("author", ""), "p": w.get("platform", ""),
            "s": w.get("status", ""), "u": src if src.startswith("http") else ""}.items() if v}
    data = {
        "version": now_kst().strftime("%Y-%m-%dT%H:%M"),
        "rules": {"min_len": 3, "full_from": 6, "ambiguous": sorted(AMBIGUOUS)},
        "works": out_works,
        "aliases": {k: v for k, v in aliases.items() if v in out_works},
    }
    path = ROOT / "docs" / "api" / "dict.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    print(f"사전 공개 파일: 작품 {len(out_works)}개, 이름 {len(data['aliases'])}개")
    return data


if __name__ == "__main__":
    run()
