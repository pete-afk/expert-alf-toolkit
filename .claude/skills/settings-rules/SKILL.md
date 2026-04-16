---
name: settings-rules
description: "ALF 규칙(rules)을 채널톡에 일괄 업로드. channel-labs Chat API를 통해 규칙을 생성/수정하고 활성화한다."
user-invocable: true
argument-hint: "<rules_dir> <channelId> <xAccount>"
---

# ALF 규칙 업로드 (via channel-labs)

Stage 6에서 생성된 개별 규칙 파일(`rules/` 디렉토리)을 channel-labs Chat API를 통해 채널톡에 업로드합니다.

## 인자 파싱

`$ARGUMENTS`를 아래 순서로 파싱한다. 누락된 필수 인자는 사용자에게 질문한다.

| 위치 | 이름 | 필수 | 설명 | 기본값 |
|------|------|------|------|--------|
| `$0` | `rules_dir` | O | 규칙 파일 디렉토리 경로 (예: `results/{company}/07_alf_documents/rules/`) | — |
| `$1` | `channelId` | O | 채널 ID | — |
| `$2` | `xAccount` | O | 인증 토큰 (`x-account`, eyJ로 시작) | — |

## channel-labs API

| 용도 | Method | URL |
|------|--------|-----|
| 인증 | POST | `https://channel-labs-api.channel.io/api/auth/verify` |
| 세션 생성 | POST | `https://channel-labs-api.channel.io/api/chat/sessions` |
| 메시지 전송 | POST | `https://channel-labs-api.channel.io/api/chat/sessions/{sessionId}/stream` |

## 실행 절차

### 1. 규칙 파일 읽기

`rules_dir` 안의 `*.md` 파일 목록을 파일명 순으로 정렬. 파일이 없으면 중단.

각 파일에서 추출:
- **title**: 첫 번째 `# 제목` 행. 없으면 파일명에서 생성
- **instruction**: 파일 전체 내용 (제목 행 제외)

### 2. channel-labs 인증

```bash
AUTH_RESPONSE=$(curl -s -X POST \
  "https://channel-labs-api.channel.io/api/auth/verify" \
  -H "Content-Type: application/json" \
  -H "x-account: {xAccount}" \
  -d '{}')
```

응답에서 `token` 추출 → 이후 모든 요청에 `Authorization: Bearer {token}` 헤더 사용.

### 3. 세션 생성

```bash
SESSION=$(curl -s -X POST \
  "https://channel-labs-api.channel.io/api/chat/sessions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -H "x-account: {xAccount}" \
  -d '{"title": "ALF 규칙 업로드"}')
```

응답에서 `session.id` 추출.

### 4. 규칙 등록 요청

모든 규칙 파일의 내용을 하나의 메시지로 조합하여 전송한다:

```bash
curl -s -X POST \
  "https://channel-labs-api.channel.io/api/chat/sessions/{sessionId}/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -H "x-account: {xAccount}" \
  -d '{
    "message": "채널 {channelId}에 아래 ALF 규칙을 등록해줘. 이미 같은 제목의 규칙이 있으면 instruction을 수정해줘. 모든 규칙은 trigger=always, state=live로 설정해줘.\n\n{규칙 목록}"
  }'
```

**규칙 목록 포맷** (메시지 본문에 포함):
```
=== 규칙 1 ===
제목: {title}
내용:
{instruction}

=== 규칙 2 ===
제목: {title}
내용:
{instruction}

...
```

**instruction 길이 제한**: 규칙 1개당 2,000자 초과 시, 메시지에 "이 규칙은 2000자를 초과합니다. 핵심만 요약해서 등록해줘." 라고 부연한다.

**규칙이 많으면 분할**: 총 메시지가 매우 길면 (10,000자 초과) 여러 메시지로 나눠 전송한다. 각 메시지에 "이전 메시지에 이어서 나머지 규칙도 등록해줘"를 포함.

### 5. SSE 응답 읽기

응답은 `text/event-stream` (SSE) 형태로 스트리밍됩니다. curl 출력에서:
- `event: text_delta` / `data: {...}` → AI 응답 텍스트
- `event: done` → 완료

AI가 `channel_api_call` 도구를 사용하여 규칙을 등록하며, 진행 상황과 결과를 텍스트로 보고합니다.

### 6. 결과 보고

SSE 응답에서 AI가 보고한 결과를 파싱하여 사용자에게 전달:

```
규칙 업로드 완료 (via channel-labs)

  생성: {N}개
  수정: {N}개
  활성화: {N}개
  실패: {N}개

  업로드된 규칙:
  [1] {title} — live
  [2] {title} — live
  ...
```

## 주의사항

- **instruction 최대 2,000자**: 초과 시 channel-labs AI가 자동으로 에러를 반환하거나 요약을 시도함
- **세션 토큰 한도**: channel-labs에는 세션/일일 토큰 한도가 있음. 대량 규칙은 나눠서 처리
- **x-account 만료**: 401 에러 시 사용자에게 새 토큰 요청
- **prod/exp 자동 감지**: x-account JWT의 kid 필드에서 환경을 자동 감지하므로 별도 env 인자 불필요
