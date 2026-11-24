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
for i in 1 2 3 4 5 6 7 8; do
  if git pull --rebase -q origin main; then
    git push -q origin HEAD:main && exit 0
  else
    git rebase --abort 2>/dev/null || true   # 충돌 시 원격 데이터를 덮어쓰지 않고 중단
  fi
  sleep $(( (RANDOM % 10) + 3 ))   # 동시에 여러 작업이 저장할 때 엇갈리게
done
echo "푸시 실패" >&2
exit 1
