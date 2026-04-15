---
name: settings-rules
description: "ALF 규칙(rules)을 채널톡에 일괄 업로드. Stage 6 산출물(rules/ 디렉토리)의 개별 규칙 파일을 읽어 ALF Rules API로 생성하고 활성화한다."
user-invocable: true
argument-hint: "<rules_dir> <channelId> <xAccount> [env]"
---

# ALF 규칙 업로드

Stage 6에서 생성된 개별 규칙 파일(`rules/` 디렉토리)을 채널톡 ALF Rules API에 일괄 업로드합니다.

## 인자 파싱

`$ARGUMENTS`를 아래 순서로 파싱한다. 누락된 필수 인자는 사용자에게 질문한다.

| 위치 | 이름 | 필수 | 설명 | 기본값 |
|------|------|------|------|--------|
| `$0` | `rules_dir` | O | 규칙 파일 디렉토리 경로 (Stage 6 산출물: `rules/`) | — |
| `$1` | `channelId` | O | 채널 ID | — |
| `$2` | `xAccount` | O | 인증 토큰 (`x-account`) | — |
| `$3` | `env` | X | `prod` 또는 `exp` | `prod` |

## API 호스트

| env | ALF Host |
|-----|----------|
| `prod` | `https://front-alf-desk-api.channel.io` |
| `exp` | `https://front-alf-desk-api.exp.channel.io` |

**Base URL**: `{ALF_HOST}/desk/channels/{channelId}/front-alf/v2`

## 실행 절차

### 1. 규칙 파일 읽기

`rules_dir` 안의 `*.md` 파일 목록을 파일명 순으로 정렬하여 확인한다. 파일이 없으면 중단.

각 파일에서 추출할 정보:
- **title**: 파일의 첫 번째 `# 제목` 행. 없으면 파일명에서 생성 (예: `01_tone_manner.md` → `01 tone manner`)
- **instruction**: 파일 전체 내용 (제목 행 제외)

### 2. 기존 규칙 조회

먼저 현재 채널의 규칙 목록을 조회하여 중복 생성을 방지한다:

```bash
curl -s \
  "{BASE_URL}/rules" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "x-account: {xAccount}" \
  -H "Cookie: x-account={xAccount}"
```

응답의 `frontAlfRules[]`에서 `title`이 일치하는 규칙이 있으면 **수정(PUT)**, 없으면 **생성(POST)**으로 처리한다.

### 3. 규칙 생성 또는 수정

**신규 생성** (기존에 같은 title이 없는 경우):

```bash
curl -s -X POST \
  "{BASE_URL}/rules" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "x-account: {xAccount}" \
  -H "Cookie: x-account={xAccount}" \
  -d '{
    "title": "{title}",
    "trigger": "always",
    "instruction": "{instruction}",
    "state": "live"
  }'
```

**수정** (기존에 같은 title이 있는 경우):

```bash
curl -s -X PUT \
  "{BASE_URL}/rules/{ruleId}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "x-account: {xAccount}" \
  -H "Cookie: x-account={xAccount}" \
  -d '{
    "title": "{title}",
    "trigger": "always",
    "instruction": "{instruction}"
  }'
```

### 4. 규칙 활성화

생성/수정 후 규칙의 `state`가 `live`가 아니면 활성화 API를 호출한다:

```bash
curl -s -X PUT \
  "{BASE_URL}/rules/{ruleId}/live" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "x-account: {xAccount}" \
  -H "Cookie: x-account={xAccount}" \
  -d '{}'
```

응답의 `frontAlfRule.state`가 `live`이면 활성화 성공.

### 5. 결과 보고

모든 규칙 처리 후 결과를 사용자에게 보고:

```
규칙 업로드 완료

  생성: {N}개
  수정: {N}개
  활성화: {N}개
  실패: {N}개 (있으면 상세 내역)

  업로드된 규칙:
  [1] 01 역할·브랜드 (id=XXXXX) — live
  [2] 02 공감 표현 규칙 (id=XXXXX) — live
  ...
```

## 주의사항

- **instruction 최대 2,000자**: 규칙 1개당 본문이 2,000자를 초과하면 422 에러 발생. 초과 시 사용자에게 알리고 분리 방법을 제안한다.
- **생성 시 state 주의**: `state: "live"`로 생성 요청해도 실제로는 `paused`가 될 수 있음. 반드시 생성 후 `/live` 엔드포인트로 별도 활성화 필요.
- **trigger는 항상 "always"**: 현재 규칙은 모든 대화에 적용되는 `always` 트리거만 사용.
- 401 에러: x-account 토큰 만료 가능성 안내
- 404 에러: channelId 확인 요청
