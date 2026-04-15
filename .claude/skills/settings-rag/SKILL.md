---
name: settings-rag
description: "RAG 지식 문서를 채널톡에 일괄 업로드. channelId, spaceId, x-account, 문서 디렉토리를 받아 Document API를 호출한다."
user-invocable: true
argument-hint: "<docs_dir> <channelId> <spaceId> <xAccount> [env]"
---

# RAG 지식 문서 업로드

Markdown 문서 디렉토리를 채널톡 Document API에 일괄 업로드합니다.

## 인자 파싱

`$ARGUMENTS`를 아래 순서로 파싱한다. 누락된 필수 인자는 사용자에게 질문한다.

| 위치 | 이름 | 필수 | 설명 | 기본값 |
|------|------|------|------|--------|
| `$0` | `docs_dir` | O | Markdown 문서 디렉토리 경로 (Stage 6 산출물: `07_alf_documents/rag/`) | — |
| `$1` | `channelId` | O | 채널 ID | — |
| `$2` | `spaceId` | O | Document Space ID | — |
| `$3` | `xAccount` | O | 인증 토큰 (`x-account`) | — |
| `$4` | `env` | X | `prod` 또는 `exp` | `prod` |

## API 호스트

| env | Document API Host |
|-----|-------------------|
| `prod` | `https://document-api.channel.io` |
| `exp` | `https://document-api.exp.channel.io` |

## 실행 절차

### 1. 문서 디렉토리 확인

`docs_dir` 안의 `*.md` 파일 목록을 확인한다. 파일이 없으면 중단.

### 2. 스크립트 실행

프로젝트 루트의 `scripts/upload_documents.py`를 실행한다:

```bash
source venv/bin/activate 2>/dev/null || true
python3 scripts/upload_documents.py <docs_dir> <channelId> <spaceId> <xAccount> [env]
```

### 3. 결과 확인

- **성공**: 업로드된 문서 수와 ID 목록을 사용자에게 보고
- **실패**: 에러 메시지를 보여주고 원인 안내
  - 401: x-account 토큰 만료
  - 404: channelId 또는 spaceId 확인
  - 422: 문서 포맷 문제

## Space ID 조회 방법

사용자가 spaceId를 모를 경우, 아래 API로 조회할 수 있다:

```bash
curl -s -X GET \
  "https://document-api.channel.io/desk/v1/channels/{channelId}/spaces" \
  -H "x-account: {xAccount}" \
  -H "Cookie: x-account={xAccount}"
```

응답의 `spaces[].id`와 `spaces[].name`을 보여주고 사용자에게 선택하게 한다.

## 주의사항

- Markdown → Channel.io document body 변환은 스크립트가 자동 처리
- 파일명의 첫 `# 제목`이 문서 제목으로 사용됨
- Rate limit 있음 (article당 3 API 호출, 0.3초 간격)
- 업로드 후 자동 publish됨 (draft 상태 아님)
