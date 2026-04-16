---
name: settings-rag
description: "RAG 지식 문서를 채널톡에 일괄 업로드. channel-labs Chat API를 통해 Document Article로 등록한다."
user-invocable: true
argument-hint: "<docs_dir> <channelId> <xAccount>"
---

# RAG 지식 문서 업로드 (via channel-labs)

Markdown 문서 디렉토리를 channel-labs Chat API를 통해 채널톡 Knowledge(Document Article)로 업로드합니다.

## 인자 파싱

`$ARGUMENTS`를 아래 순서로 파싱한다. 누락된 필수 인자는 사용자에게 질문한다.

| 위치 | 이름 | 필수 | 설명 | 기본값 |
|------|------|------|------|--------|
| `$0` | `docs_dir` | O | Markdown 문서 디렉토리 경로 (예: `results/{company}/07_alf_documents/rag/`) | — |
| `$1` | `channelId` | O | 채널 ID | — |
| `$2` | `xAccount` | O | 인증 토큰 (`x-account`, eyJ로 시작) | — |

## channel-labs API

| 용도 | Method | URL |
|------|--------|-----|
| 인증 | POST | `https://channel-labs-api.channel.io/api/auth/verify` |
| 세션 생성 | POST | `https://channel-labs-api.channel.io/api/chat/sessions` |
| 파일 업로드 | POST | `https://channel-labs-api.channel.io/api/chat/files` |
| 메시지 전송 | POST | `https://channel-labs-api.channel.io/api/chat/sessions/{sessionId}/stream` |

## 실행 절차

### 1. 문서 파일 확인

`docs_dir` 안의 `*.md` 파일 목록을 확인. 파일이 없으면 중단.

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
  -d '{"title": "RAG 지식 문서 업로드"}')
```

응답에서 `session.id` 추출.

### 4. 문서 등록 방식 선택

channel-labs Knowledge 등록은 여러 방식을 지원합니다. Markdown 문서는 **Document Article** 방식으로 등록합니다.

**방식 A: 메시지 본문에 내용 포함 (소량, 5개 이하)**

각 문서의 내용을 메시지 본문에 직접 포함하여 전송:

```bash
curl -s -X POST \
  "https://channel-labs-api.channel.io/api/chat/sessions/{sessionId}/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -H "x-account: {xAccount}" \
  -d '{
    "message": "채널 {channelId}에 아래 문서들을 ALF Knowledge Document Article로 등록해줘. 폴더가 없으면 \"RAG 지식\" 폴더를 만들어서 거기에 넣어줘. 모든 문서의 alfReferencing을 true로 설정해줘.\n\n=== 문서 1: {title} ===\n{markdown content}\n\n=== 문서 2: {title} ===\n{markdown content}"
  }'
```

**방식 B: 파일 첨부 (다량, 6개 이상)**

먼저 파일을 업로드한 후, fileId를 메시지에 첨부:

```bash
# 각 파일 업로드 (최대 5개씩)
FILE_RESPONSE=$(curl -s -X POST \
  "https://channel-labs-api.channel.io/api/chat/files" \
  -H "Authorization: Bearer {token}" \
  -H "x-account: {xAccount}" \
  -F "file=@{file_path}")
```

응답에서 `file.id` 추출 후, 메시지에 fileIds 배열로 첨부:

```bash
curl -s -X POST \
  "https://channel-labs-api.channel.io/api/chat/sessions/{sessionId}/stream" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -H "x-account: {xAccount}" \
  -d '{
    "message": "채널 {channelId}에 첨부한 Markdown 파일들을 ALF Knowledge Document Article로 등록해줘. 폴더가 없으면 \"RAG 지식\" 폴더를 만들어서 거기에 넣어줘. 모든 문서의 alfReferencing을 true로 설정해줘.",
    "fileIds": ["{fileId1}", "{fileId2}", ...]
  }'
```

**주의**: 파일 첨부는 메시지당 최대 5개. 6개 이상이면 여러 메시지로 나눠 전송.

### 5. SSE 응답 읽기

AI가 `channel_api_call` 도구를 사용하여:
1. Knowledge 폴더 생성/조회
2. Document Article 생성 (Space/Article API 경유)
3. alfReferencing 활성화

진행 상황과 결과를 SSE 텍스트로 보고합니다.

### 6. 결과 보고

```
RAG 지식 문서 업로드 완료 (via channel-labs)

  등록: {N}개
  실패: {N}개

  등록된 문서:
  [1] {title} — alfReferencing: true
  [2] {title} — alfReferencing: true
  ...
```

## 주의사항

- **파일 형식**: channel-labs 파일 업로드는 text/*, image/*, PDF, Excel, JSON 지원. Markdown(text/markdown)은 지원됨
- **파일 만료**: 업로드된 파일은 일정 시간 후 만료. 업로드 후 즉시 메시지 전송 필요
- **Document Article vs Excel Knowledge**: Markdown 문서는 Document Article로 등록. FAQ Excel이 있으면 별도로 Excel Knowledge로 등록 가능
- **세션 토큰 한도**: 대량 문서는 여러 세션에 나눠 처리
- **x-account 만료**: 401 에러 시 새 토큰 요청
- **prod/exp 자동 감지**: x-account JWT kid 필드에서 환경 자동 감지
