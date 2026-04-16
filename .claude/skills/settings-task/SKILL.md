---
name: settings-task
description: "Task JSON 파일을 채널톡에 업로드(생성/수정). channel-labs Chat API를 통해 ALF Task를 등록한다."
user-invocable: true
argument-hint: "<filePath_or_dir> <channelId> <xAccount> [taskId]"
---

# Task JSON 업로드 (via channel-labs)

Task JSON 파일을 channel-labs Chat API를 통해 채널톡에 업로드합니다.

## 인자 파싱

`$ARGUMENTS`를 아래 순서로 파싱한다. 누락된 필수 인자는 사용자에게 질문한다.

| 위치 | 이름 | 필수 | 설명 | 기본값 |
|------|------|------|------|--------|
| `$0` | `filePath` | O | Task JSON 파일 경로 또는 디렉토리 (디렉토리면 안의 `*.json` 전부) | — |
| `$1` | `channelId` | O | 채널 ID | — |
| `$2` | `xAccount` | O | 인증 토큰 (`x-account`, eyJ로 시작) | — |
| `$3` | `taskId` | X | 기존 Task 수정 시 Task ID | — |

## channel-labs API

| 용도 | Method | URL |
|------|--------|-----|
| 인증 | POST | `https://channel-labs-api.channel.io/api/auth/verify` |
| 세션 생성 | POST | `https://channel-labs-api.channel.io/api/chat/sessions` |
| 파일 업로드 | POST | `https://channel-labs-api.channel.io/api/chat/files` |
| 메시지 전송 | POST | `https://channel-labs-api.channel.io/api/chat/sessions/{sessionId}/stream` |

## 실행 절차

### 1. Task JSON 읽기

- 파일 경로면: 해당 JSON 파일 1개 읽기
- 디렉토리면: 안의 `*.json` 파일 전부 읽기

각 파일에서 Task name을 확인한다 (파일 최상위 또는 `task.name`).

### 2. channel-labs 인증

```bash
AUTH_RESPONSE=$(curl -s -X POST \
  "https://channel-labs-api.channel.io/api/auth/verify" \
  -H "Content-Type: application/json" \
  -H "x-account: {xAccount}" \
  -d '{}')
```

응답에서 `token` 추출.

### 3. 세션 생성

```bash
SESSION=$(curl -s -X POST \
  "https://channel-labs-api.channel.io/api/chat/sessions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -H "x-account: {xAccount}" \
  -d '{"title": "ALF Task 업로드"}')
```

응답에서 `session.id` 추출.

### 4. Task 등록 요청

**신규 생성** (taskId 없음):

Task JSON 파일을 channel-labs에 업로드하고, 메시지로 등록 요청:

```bash
# 파일 업로드
FILE_RESPONSE=$(curl -s -X POST \
  "https://channel-labs-api.channel.io/api/chat/files" \
  -H "Authorization: Bearer {token}" \
  -H "x-account: {xAccount}" \
  -F "file=@{filePath}")
```

```bash
# 등록 요청
curl -s -X POST \
  "https://channel-labs-api.channel.io/api/chat/sessions/{sessionId}/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -H "x-account: {xAccount}" \
  -d '{
    "message": "채널 {channelId}에 첨부한 Task JSON 파일을 ALF Task로 등록해줘. 폴더가 없으면 기본 폴더에 넣어줘. 등록 후 validate까지 해줘.",
    "fileIds": ["{fileId}"]
  }'
```

**수정** (taskId 있음):

```bash
curl -s -X POST \
  "https://channel-labs-api.channel.io/api/chat/sessions/{sessionId}/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -H "x-account: {xAccount}" \
  -d '{
    "message": "채널 {channelId}의 Task {taskId}를 첨부한 JSON으로 수정해줘. 수정 후 validate해줘.",
    "fileIds": ["{fileId}"]
  }'
```

**다수 Task 일괄 등록** (디렉토리):

각 JSON 파일을 순서대로 업로드하고 등록 요청. 메시지당 1 Task 파일 (파일당 최대 5개까지 묶을 수 있지만, Task는 개별 등록이 안전).

### 5. SSE 응답 읽기

AI가 `channel_api_call` 도구를 사용하여:
1. Task 폴더 조회/생성
2. Task 생성 (POST) 또는 수정 (PUT)
3. Task 검증 (validate)
4. 결과 보고

### 6. 결과 보고

```
Task 업로드 완료 (via channel-labs)

  생성: {N}개
  수정: {N}개
  검증 통과: {N}개
  실패: {N}개

  업로드된 Task:
  [1] {name} (id={taskId}) — draft
  [2] {name} (id={taskId}) — draft
  ...

  💡 Task를 Live로 전환하려면 채널톡 데스크에서 직접 활성화하세요.
```

## 주의사항

- **Task는 draft로 생성**: channel-labs AI가 자동으로 Live 전환하지 않음. 검증 후 수동 활성화 필요
- **Task JSON 형식**: `{"task": {...}, "taskEditorPosition": {...}}` wrapper 형태 또는 task 객체만 있는 형태 모두 지원
- **targetMediums**: 객체 배열 형태 `[{"mediumType": "native"}]`
- **파일 만료**: 업로드된 파일은 일정 시간 후 만료. 업로드 직후 메시지 전송
- **x-account 만료**: 401 에러 시 새 토큰 요청
- **prod/exp 자동 감지**: x-account JWT kid 필드에서 환경 자동 감지
