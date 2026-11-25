"""노벨피아 24시간 TOP100 접근 점검 (한 번만 실행, 결과는 data/novelpia_probe.json).

원칙
- 사이트의 robots.txt를 먼저 읽는다. 이 페이지를 가져가도 된다고 나올 때만 목록 페이지를 딱 한 번 가져온다.
- 막혀 있거나(robots·403·점검 화면 등) 확인 절차가 나오면 거기서 멈춘다. 우회하지 않는다.
- 브라우저인 척하지 않고, 정체와 연락처가 보이는 User-Agent를 쓴다.
- 결과 파일에는 구조 정보와 제목 일부만 남긴다 (페이지 전체를 저장하지 않음).

python -m src.novelpia_probe
"""
import json
import re
import urllib.robotparser

import requests

from .common import DATA, now_kst, write_json

BASE = "https://novelpia.com"
PATH = "/top100"
UA = "dc-completed-novels-research (personal, low-volume; +https://github.com/answhdtjr736-spec/dc-completed-novels)"
OUT = DATA / "novelpia_probe.json"


def main():
    res = {"checked": now_kst().strftime("%Y-%m-%d %H:%M"), "ua": UA}
    try:
        r = requests.get(BASE + "/robots.txt", headers={"User-Agent": UA}, timeout=20)
    except Exception as e:
        res.update(stage="robots", error=f"{type(e).__name__}: {e}"[:200])
        write_json(OUT, res)
        print(res)
        return
    res["robots_status"] = r.status_code
    res["robots_text"] = r.text[:3000] if r.status_code == 200 else ""
    if r.status_code == 200:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(r.text.splitlines())
        res["allowed_for_us"] = rp.can_fetch(UA, BASE + PATH)
        res["allowed_for_any"] = rp.can_fetch("*", BASE + PATH)
    elif r.status_code in (401, 403) or r.status_code >= 500:
        res["allowed_for_us"] = False         # 확인 불가 → 가져가지 않는다
    else:
        res["allowed_for_us"] = r.status_code == 404   # robots.txt 없음 = 제한 없음
    if not res.get("allowed_for_us"):
        res["stage"] = "stopped_by_robots"
        write_json(OUT, res)
        print("robots.txt가 허용하지 않거나 확인할 수 없어 목록은 가져오지 않았습니다.")
        print(json.dumps({k: v for k, v in res.items() if k != "robots_text"}, ensure_ascii=False))
        print(res.get("robots_text", "")[:1500])
        return

    p = requests.get(BASE + PATH, headers={"User-Agent": UA, "Accept-Language": "ko"}, timeout=30)
    body = p.text
    res.update(stage="fetched", status=p.status_code, content_type=p.headers.get("content-type"), length=len(body))
    blocked = p.status_code != 200 or re.search(r"cloudflare|captcha|just a moment|사람인지", body[:5000], re.I)
    if blocked:
        res["note"] = "차단·확인 화면으로 보여 중단"
        write_json(OUT, res)
        print(json.dumps(res, ensure_ascii=False)[:800])
        return
    # 구조 점검: 제목이 HTML에 있는지, 별도 API를 부르는지만 본다
    res["has_novel_links"] = len(re.findall(r'href="[^"]*/novel/\d+', body))
    res["api_hints"] = sorted(set(re.findall(r'["\'](/proc/[a-z_/]+|/api/[A-Za-z0-9_/]+)["\']', body)))[:15]
    titles = re.findall(r'<a[^>]+href="[^"]*/novel/\d+"[^>]*>\s*([^<]{2,60}?)\s*</a>', body)
    res["sample_titles"] = [t for t in titles if t][:10]
    write_json(OUT, res)
    print(json.dumps({k: v for k, v in res.items() if k != "robots_text"}, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    main()
