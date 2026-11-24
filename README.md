# 장르소설갤 완결작 집계

디시인사이드 장르소설 마이너 갤러리에서 제목에 '완결'이 들어간 글을 매일 수집해,
실제로 완결된 작품을 언급한 글만 골라 **월별·분기별로 많이 언급된 완결작**을 집계합니다.

### 📊 [보고서 보기 →](https://answhdtjr736-spec.github.io/dc-completed-novels/)

- 매일 한국시간 새벽 4시 전후 자동 실행 (GitHub Actions)

## 처음 설정 (한 번만)

### 1. 비밀값(Secrets) 등록
저장소 **Settings → Secrets and variables → Actions → New repository secret**

| 이름 | 값 |
|---|---|
| `WRITER_SALT` | 아무 긴 무작위 문자열 (작성자 식별값을 해시할 때 씀. 한 번 정하면 바꾸지 말 것) |
| `SERPAPI_KEY` | (선택) SerpApi 키. 있으면 줄임말을 구글 검색 결과로 찾음. 월 무료 250회 안에서만 사용 |
| `CLAUDE_CODE_OAUTH_TOKEN` | Pro 구독 토큰. PC에 Claude Code 설치 후 터미널에서 `claude setup-token` 실행 → 나온 값 |

토큰이 없어도 크롤링·규칙 판정·보고서는 돌아갑니다(AI 판정만 빠짐).

### 2. 보고서 웹페이지 켜기
**Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: `main` / `/docs` → Save** (설정 완료)

### 3. 첫 실행
**Actions → 매일 수집·집계 → Run workflow**.
처음엔 6개월치를 수집하므로 오래 걸리고, 다 못 하면 다음 실행 때 이어서 합니다.
AI 판정도 하루 상한(`max_titles_per_run`)씩 나눠 처리합니다.

## 동작 방식

1. **크롤링** (`src/crawl.py`): 최신 글부터 내려가다 지난번 마지막 글번호를 만나면 멈춤. 본문은 안 봄.
2. **판정** (`src/rules.py`, `src/judge.py`): 규칙 + AI(Claude Code, Pro 구독)로 '완결된 작품 언급'인지 판정하고 작품명을 뽑음.
3. **줄임말 사전** (`dict/`): 사전에 없는 작품명만 검색해서 정식 제목을 추가. 이미 있으면 검색 안 함.
   순위권 이름(작성자 2명 이상)은 구글 검색 결과(SerpApi)를 AI가 읽고 추출, 나머지는 AI 웹 검색.
4. **집계** (`src/aggregate.py`): 매번 전체 데이터로 다시 계산 → `docs/data/report.json`

### 집계 기준
- 순위: 그 기간에 해당 작품을 '완결' 언급한 **고유 작성자 수** → 언급 글 수
  (작성자는 해시값만 저장. 같은 사람이 여러 번 써도 1명)
- 완결 추정 월: 고유 작성자가 `min_writers_for_completion`명 이상인 첫 달

## 검수와 모드 전환

- 규칙과 AI 판정이 갈린 제목은 **상위 모델(sonnet)이 자동으로 최종 검수**합니다 (`data/review_ai/`, 판단 근거 포함).
- 보고서 **검수** 탭에서 결과를 볼 수 있고, 틀린 게 있으면 버튼으로 한 줄 복사 →
  `review/overrides.csv`에 붙여넣기 → 저장. 사람 검수가 항상 우선합니다.
  - 형식: `글번호,complete 또는 not,정식 제목(선택),메모(선택)`
- **지표** 탭의 일치율이 연속 2~3회 95% 이상이면 `config.yaml`의 `judge.mode`를 `economy`로 바꾸세요.
  규칙으로 애매한 제목과 일부 표본만 AI로 보내 사용량을 줄입니다.
- 사전 수정: `dict/aliases.json`(줄임말 → 작품 ID), `dict/works.json`(작품 정보)

## 폴더 구조

```
data/posts/YYYY-MM.jsonl  월별 수집 글 (글번호·제목·날짜·작성자 해시·댓글 수)
data/ai/YYYY-MM.jsonl     월별 AI 판정 결과
data/state.json           마지막 글번호, 초기 수집 진행 위치
data/metrics.jsonl        실행별 지표
dict/                     줄임말 사전, 작품 정보, 검색 실패 기록
review/overrides.csv      사용자 검수
docs/                     보고서 웹페이지
```

## 로컬 테스트

```
pip install -r requirements.txt
python tests/test_pipeline.py   # 가짜 페이지·가짜 AI로 전체 흐름 확인
```
