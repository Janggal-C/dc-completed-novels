#!/bin/bash
# 확장 배포 파일 만들기: 최신 사전 내장 + '빌드 다음 날 0시(한국시간)부터 갱신' 시각 박기
set -e
cd "$(dirname "$0")/.."
python3 -m src.export_dict >/dev/null
rm -rf /tmp/ext_build && cp -r extension /tmp/ext_build
cp docs/api/dict.json /tmp/ext_build/dict.json
NEXT=$(TZ=Asia/Seoul date -d tomorrow +%Y-%m-%dT00:00:00+09:00)
sed -i "s|__NO_CHECK_UNTIL__|$NEXT|" /tmp/ext_build/background.js
VER=$(python3 -c "import json;print(json.load(open('extension/manifest.json'))['version'])")
OUT="${1:-/home/claude}/장르소설갤-줄임말사전-v$VER.zip"
rm -f "$OUT"; (cd /tmp/ext_build && zip -qr "$OUT" .)
echo "$OUT (사전 $(python3 -c "import json;print(json.load(open('docs/api/dict.json'))['version'])"), 갱신 시작 $NEXT)"
