---
name: settings-task
description: "Task JSON 파일을 채널톡에 업로드(생성/수정). channelId, x-account, 파일 경로를 받아 ALF Task API를 직접 호출한다."
user-invocable: true
argument-hint: "<filePath> <channelId> <xAccount> [env] [taskId]"
---

# Task JSON 업로드

Task JSON 파일을 채널톡 ALF Task API에 업로드합니다.

## 인자 파싱

`$ARGUMENTS`를 아래 순서로 파싱한다. 누락된 필수 인자는 사용자에게 질문한다.

| 위치 | 이름 | 필수 | 설명 | 기본값 |
|------|------|------|------|--------|
| `$0` | `filePath` | O | Task JSON 파일 경로 | — |
| `$1` | `channelId` | O | 채널 ID | — |
| `$2` | `xAccount` | O | 인증 토큰 (`x-account`) | — |
| `$3` | `env` | X | `prod` 또는 `exp` | `prod` |
| `$4` | `taskId` | X | 기존 Task 수정 시 Task ID | — |

## API 호스트

| env | ALF Host |
|-----|----------|
| `prod` | `https://front-alf-desk-api.channel.io` |
| `exp` | `https://front-alf-desk-api.exp.channel.io` |

## 실행 절차

### 1. Task JSON 읽기

Read 도구로 `filePath`의 JSON 파일을 읽는다. 파일 구조가 아래 두 형태 중 하나인지 확인:

- **wrapper 형태**: `{"task": {...}, "taskEditorPosition": {...}}` — 그대로 사용
- **task만 있는 형태**: `{"name": "...", "nodes": [...], ...}` — wrapper로 감싼다:
  ```json
  {"task": <원본 JSON>, "taskEditorPosition": {"nodePositions": {}, "edgePositions": {}}}
  ```

`taskEditorPosition`이 원본에 포함되어 있으면 분리해서 wrapper에 넣는다.

### 2. folderId 확인 (생성 시만)

`taskId`가 없으면 (신규 생성) folderId가 필요하다.

Task JSON에 `folderId`가 이미 있으면 그대로 사용. 없으면 조회:

```bash
curl -s -X GET \
  "{ALF_HOST}/desk/channels/{channelId}/front-alf/v2/task/folders/root/contents" \
  -H "Content-Type: application/json" \
  -H "x-account: {xAccount}" \
  -H "Cookie: x-account={xAccount}"
```

응답의 `childFolders[0].id`를 folderId로 사용. 폴더가 없으면:

```bash
curl -s -X POST \
  "{ALF_HOST}/desk/channels/{channelId}/front-alf/v2/task/folders" \
  -H "Content-Type: application/json" \
  -H "x-account: {xAccount}" \
  -H "Cookie: x-account={xAccount}" \
  -d '{"name": "기본"}'
```

task 객체에 `"folderId": "<조회한 ID>"`를 추가한다.

### 3. API 호출

**신규 생성** (`taskId` 없음):

```bash
curl -s -X POST \
  "{ALF_HOST}/desk/channels/{channelId}/front-alf/v2/tasks" \
  -H "Content-Type: application/json" \
  -H "x-account: {xAccount}" \
  -H "Cookie: x-account={xAccount}" \
  -d '<wrapper JSON>'
```

**수정** (`taskId` 있음):

```bash
curl -s -X PUT \
  "{ALF_HOST}/desk/channels/{channelId}/front-alf/v2/tasks/{taskId}" \
  -H "Content-Type: application/json" \
  -H "x-account: {xAccount}" \
  -H "Cookie: x-account={xAccount}" \
  -d '<wrapper JSON>'
```

### 4. 결과 확인

- **성공**: 응답의 `frontAlfTask.id`와 `name`을 사용자에게 알려준다.
- **422 에러**: 응답 body의 에러 메시지를 보여주고 수정 방법을 제안한다.
- **401 에러**: x-account 토큰 만료 가능성을 안내한다.
- **404 에러**: channelId 또는 taskId 확인을 요청한다.

## 스크립트로 실행

스킬 디렉토리의 `upload-task.sh`를 직접 실행할 수도 있다:

```bash
~/.claude/skills/settings-task/upload-task.sh <file_or_dir> <channel_id> <x_account> [env] [task_id]
```

- 디렉토리를 넘기면 안의 `*.json` 전부 업로드
- 폴더 선택 UI가 인터랙티브하게 표시됨

## 주의사항

- API body는 flat 구조 (task 필드를 최상위에 펼침 + `taskEditorPosition` 포함)
- `targetMediums`는 객체 배열: `[{"mediumType": "native"}]` (문자열 배열 아님)
- 수정(PUT) 시 기존 Task를 먼저 GET으로 조회하여 기존 데이터 기반으로 수정 권장
