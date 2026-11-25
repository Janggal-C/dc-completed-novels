"""월초 카드뉴스 생성: docs/data/mentions.json → 결산 카드 5장 HTML (사이트.md "월초 카드뉴스" 규칙)

사용: python scripts/cardnews.py 2026-09 out_dir
  out_dir/card-1.html … card-5.html (카드마다 한 장, PNG 캡처용)
  out_dir/cards.html (5장 세로로 쌓은 미리보기)
"""
import json
import sys
from pathlib import Path

FONT = "'Noto Sans KR','Noto Sans CJK KR','Malgun Gothic',sans-serif"
CARD = f"box-sizing:border-box;width:1080px;position:relative;overflow:hidden;display:flex;flex-direction:column;font-family:{FONT};"
MEDAL = {1: ("#F5B301", "#B98700", "#FFE08A"), 2: ("#9AA3B8", "#737C93", "#D3D8E8"), 3: ("#C98A5B", "#9C6A41", "#EDCFB3")}


# 배경 장식(원·금색 점)은 넣지 않음 (2026-11-26 사용자: 정신없음)


def row(rank, item, top_n, fixed=True, done_card=False):
    pct = item["n"] / top_n * 100 if top_n else 0
    if rank in MEDAL:
        c, sh, gauge = MEDAL[rank]
        badge = (f'<div style="flex:none;width:104px;height:104px;border-radius:52px;background:{c};box-shadow:0 5px 0 {sh};'
                 f'display:flex;align-items:center;justify-content:center;color:#ffffff;font-size:68px;font-weight:900">{rank}</div>')
    else:
        gauge = "#D5DAF5"
        fs = 48 if rank >= 10 else 56
        badge = (f'<div style="flex:none;width:104px;height:104px;border-radius:52px;background:#E4E7FA;display:flex;'
                 f'align-items:center;justify-content:center;color:#3B4890;font-size:{fs}px;font-weight:800">{rank}</div>')
    tags = ""
    if done_card:
        md = item["cdate"][5:7] + "/" + item["cdate"][8:10]
        tags = ('<span style="font-size:28px;font-weight:700;padding:1px 16px;border-radius:999px;background:#DFF3E6;color:#1F7A45">완결</span>'
                f'<span style="font-size:30px;color:#5B6388">{md}</span>')
    else:
        st = item.get("status") or ""
        if st == "완결":
            tags = '<span style="font-size:28px;font-weight:700;padding:1px 16px;border-radius:999px;background:#DFF3E6;color:#1F7A45">완결</span>'
        elif st:
            tags = f'<span style="font-size:28px;font-weight:700;padding:1px 16px;border-radius:999px;background:#E4E7FA;color:#3B4890">{st}</span>'
    size = "height:150px;flex:none;" if fixed else "flex:1 1 0;min-height:0;"
    return (f'<div style="{size}position:relative;overflow:hidden;display:flex;align-items:center;border-radius:30px;background:#ffffff">'
            f'<div style="position:absolute;left:0;top:0;bottom:0;width:{pct:.1f}%;background:{gauge};z-index:0"></div>'
            '<div style="position:relative;z-index:1;flex:1;min-width:0;display:flex;align-items:center;gap:26px;padding:0 34px 0 22px">'
            f'{badge}<div style="flex:1;min-width:0"><div style="font-size:40px;font-weight:800;line-height:1.15;color:#1B1F4B;word-break:keep-all">{item["title"]}</div>'
            f'<div style="margin-top:6px;display:flex;gap:12px;align-items:center;min-height:6px">{tags}</div></div>'
            f'<div style="flex:none;text-align:right;line-height:1.05"><div style="font-size:64px;font-weight:900;color:#3B4890">{item["n"]:,}</div>'
            '<div style="font-size:28px;color:#5B6388;margin-top:2px">언급</div></div></div></div>')


def head(pill, desc, title):
    return ('<div style="position:relative"><div style="display:flex;align-items:center;gap:16px">'
            f'<div style="background:#3B4890;color:#ffffff;border-radius:999px;padding:8px 28px;font-size:36px;font-weight:800">{pill}</div>'
            f'<span style="font-size:32px;font-weight:600;color:#6B7399">{desc}</span></div>'
            f'<div style="font-size:60px;font-weight:900;letter-spacing:-0.02em;color:#1B1F4B;margin-top:14px;line-height:1.2">{title}</div></div>')


def foot(left):
    return ('<div style="margin-top:auto;padding-top:18px;font-size:32px;color:#7D85AB;display:flex;justify-content:space-between">'
            f'<span>{left}</span><span>장갤수집가</span></div>')


def build(month, data):
    y, m = month.split("-")
    mi = int(m)
    q = (mi - 1) // 3 + 1
    qm = [f"{y}-{(q - 1) * 3 + k:02d}" for k in (1, 2, 3)]
    mon = data["periods"][month]
    qtr = data["periods"][f"{y}-Q{q}"]
    top10 = mon[:10]
    # 동점이면 완결일이 더 최근인 작품이 위
    mdone = sorted([x for x in mon if (x.get("cdate") or "")[:7] == month], key=lambda x: (-x["n"], [-ord(c) for c in x["cdate"]]))[:5]
    qdone = sorted([x for x in qtr if (x.get("cdate") or "")[:7] in qm], key=lambda x: (-x["n"], [-ord(c) for c in x["cdate"]]))[:5]

    cover = (f'<div style="{CARD}height:864px;background:#3B4890;color:#ffffff;padding:40px 80px 96px;justify-content:center">'
             + '<div style="position:relative">'
             f'<div style="display:inline-block;background:#F5B301;color:#1B1F4B;border-radius:999px;padding:8px 30px;font-size:38px;font-weight:800">{y}.{mi} 월간 결산</div>'
             '<div style="font-size:46px;font-weight:700;color:#C7CDF0;margin-top:30px">장르소설 갤러리</div>'
             f'<div style="font-size:210px;line-height:1.05;font-weight:900;letter-spacing:-0.03em;white-space:nowrap;margin-top:6px">{mi}월 <span style="color:#F5B301">결산</span></div>'
             f'<div style="font-size:50px;line-height:1.5;font-weight:600;color:#DDE1F7;margin-top:34px">가장 많이 언급된 작품 TOP 10<br>{mi}월 · {q}분기 완결작 TOP 5</div></div>'
             '<div style="position:absolute;right:80px;bottom:52px;font-size:32px;color:#AAB2E6">장갤수집가</div></div>')

    topn = top10[0]["n"] if top10 else 0
    c2 = (f'<div style="{CARD}height:1080px;background:#F1F2FF;padding:52px 60px 52px">'
          + head("언급 TOP 10", "완결 여부 무관", f"{mi}월 언급수 TOP10")
          + '<div style="margin-top:26px;display:flex;flex-direction:column;gap:14px;position:relative">'
          + "".join(row(i + 1, x, topn) for i, x in enumerate(top10[:5])) + '</div></div>')
    c3 = (f'<div style="{CARD}height:1080px;background:#F1F2FF;padding:52px 60px 44px">'
          + '<div style="display:flex;flex-direction:column;gap:14px;position:relative">'
          + "".join(row(i + 6, x, topn) for i, x in enumerate(top10[5:10])) + '</div>'
          + foot(f"장르소설 갤러리 · {y}년 {mi}월 결산") + '</div>')

    def done_card(items, desc, title, left):
        tn = items[0]["n"] if items else 0
        return (f'<div style="{CARD}height:1080px;background:#E3E6F8;padding:52px 60px 44px">'
                + head("완결 TOP 5", desc, title)
                + '<div style="margin-top:26px;display:flex;flex-direction:column;gap:14px;flex:1;min-height:0;position:relative">'
                + "".join(row(i + 1, x, tn, fixed=len(items) < 5, done_card=True) for i, x in enumerate(items)) + '</div>'
                + foot(left) + '</div>')

    c4 = done_card(mdone, f"{mi}월 언급 · 이 달 완결작만", f"{mi}월 완결작 TOP5", f"장르소설 갤러리 · {y}년 {mi}월 결산")
    qs, qe = (q - 1) * 3 + 1, q * 3
    c5 = done_card(qdone, f"{q}분기 언급 · 이 분기 완결작만", f"{q}분기 완결작 TOP5", f"장르소설 갤러리 · {y}년 {q}분기({qs}~{qe}월)")
    return [cover, c2, c3, c4, c5], {"top10": top10, "month_done": mdone, "quarter_done": qdone}


def page(body, title):
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>{title}</title>'
            '<style>*{box-sizing:border-box;margin:0;padding:0}html,body{background:#d9dce8}</style></head>'
            f'<body>{body}</body></html>')


if __name__ == "__main__":
    month, out = sys.argv[1], Path(sys.argv[2])
    src = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("docs/data/mentions.json")
    out.mkdir(parents=True, exist_ok=True)
    cards, picked = build(month, json.loads(src.read_text(encoding="utf-8")))
    for i, c in enumerate(cards, 1):
        (out / f"card-{i}.html").write_text(page(c, f"card {i}"), encoding="utf-8")
    (out / "picked.json").write_text(json.dumps(picked, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: [(x["title"], x["n"], x.get("cdate")) for x in v] for k, v in picked.items()}, ensure_ascii=False, indent=1))
