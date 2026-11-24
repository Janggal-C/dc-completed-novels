#!/usr/bin/env bash
# 바뀐 데이터만 커밋하고 푸시. 그 사이 사용자가 검수 파일을 고쳤어도 rebase로 합친다.
set -e
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add data dict docs review 2>/dev/null || true
if git diff --cached --quiet; then
  echo "변경 없음"
  exit 0
fi
git commit -q -m "$1"
for i in 1 2 3; do
  git pull --rebase -q origin main && git push -q origin HEAD:main && exit 0
  sleep 5
done
echo "푸시 실패" >&2
exit 1
