---
name: convert-task-json
description: Stage 5 Task Markdown 문서(05_tasks/TASK*.md)를 채널톡 ALF Task API용 JSON으로 변환. Mermaid 플로우차트 + 설명을 파싱하여 nodes, memorySchema, trigger, taskEditorPosition을 자동 생성한다.
---

# Task Markdown → JSON 변환

Stage 5에서 생성된 Task 문서(Mermaid 플로우차트 + 설명)를 채널톡 ALF Task API에 업로드 가능한 JSON으로 변환합니다.

## 인자 파싱

| 위치 | 이름 | 필수 | 설명 | 기본값 |
|------|------|------|------|--------|
| 1 | `task_md_path` | O | Task Markdown 파일 경로 또는 디렉토리 | — |
| 2 | `output_dir` | X | JSON 출력 디렉토리 | 입력 파일과 같은 디렉토리 |

디렉토리를 넘기면 안의 `TASK*.md` 전부 변환.

## 레퍼런스

변환 시 반드시 `TASK_JSON_REFERENCE.md` (같은 프로젝트의 `.claude/skills/settings-task/TASK_JSON_REFERENCE.md`)를 참조하세요.

## 변환 절차

### 1. Task Markdown 읽기

Read 도구로 Task Markdown을 읽고, 아래 정보를 파싱한다:

- **Task 이름**: 첫 번째 `# 태스크` 또는 `# TASK` 헤더에서 추출
- **트리거 조건**: "트리거" 또는 "Trigger" 행에서 추출
- **필수 입력**: "Input" 또는 "입력" 행에서 추출
- **Mermaid 플로우차트**: ` ```mermaid ... ``` ` 블록에서 추출
- **노드 설명**: 요약표 또는 상세 설명 섹션에서 추출

### 2. Mermaid → 노드 매핑

Mermaid 플로우차트의 각 노드를 ALF Task 노드로 변환한다.

**Mermaid → ALF 노드 타입 매핑:**

| Mermaid 형태 | ALF 노드 타입 | 설명 |
|-------------|-------------|------|
| `([시작/종료])` | (시작점/종료점) | `startNodeId` 또는 `END_TASK` |
| `[프로세스]` | `agent` | 일반 처리 → 에이전트 지시문으로 변환 |
| `{조건 분기}` | 이전 노드의 `branch` next | 분기 조건 → branch conditions |
| `[(API 호출)]` | `code` | API 호출 → axios 코드 스켈레톤 |
| `[/메시지 출력/]` | `message` | 고정 메시지 → blocks |
| `((에스컬레이션))` | `userChatInlineAction` | 상담사 연결 → assignManager |

**노드 변환 규칙:**
- 각 노드에 UUID 형식의 id 부여 (`node-1`, `node-2`, ...)
- key는 알파벳 순서 (`A`, `B`, `C`, ...)
- Mermaid의 `-->` 화살표를 `next.goto`로 변환
- Mermaid의 `-->|조건|` 화살표를 `next.branch.conditions`로 변환
- 화살표가 없는 마지막 노드는 `END_TASK`로 연결

### 3. 에이전트 노드 instruction 생성

각 에이전트 노드의 instruction을 아래 템플릿으로 생성:

```
## 역할
{노드 이름/설명에서 추출한 역할}

## 대화 흐름
{Markdown 상세 설명에서 추출한 안내 내용}
{메모리 변수가 있으면 promptdata 태그 삽입}

## 종료 조건
{해당 노드의 완료 조건 — 반드시 명시}
```

- 메모리 읽기: `<promptdata type="read-variable" subtype="taskMemory" identifier="key">key</promptdata>`
- 메모리 쓰기: `<promptdata type="update-variable" subtype="taskMemory" identifier="key">key</promptdata>`

### 4. 코드 노드 code 생성

API 호출 노드는 아래 스켈레톤으로 생성:

```javascript
const axios = require('axios');
const MAX_RETRIES = 3;
let retryCount = 0;

while (retryCount < MAX_RETRIES) {
  try {
    const response = await axios.get('{{BASE_URL}}/{endpoint}', {
      headers: { 'Content-Type': 'application/json' }
    });
    memory.put('{result_key}', response.data);
    console.log('[{node_id}] 성공:', { /* 필요한 정보 */ });
    break;
  } catch (error) {
    retryCount++;
    if (retryCount >= MAX_RETRIES) {
      console.error('[{node_id}] 최종 실패:', { error: error.message });
      throw error;
    }
  }
}
memory.save();
```

- API URL은 `{{BASE_URL}}`로 플레이스홀더 처리 (실제 URL은 개발팀이 채움)
- `onError` 필드에 에러 핸들링 노드 연결

### 5. memorySchema 생성

모든 노드에서 사용하는 메모리 변수를 수집하여 `memorySchema` 배열 생성.

수집 대상:
- agent 노드의 `promptdata` 태그에서 identifier 추출
- code 노드의 `memory.put('key', ...)` 에서 key 추출
- branch 조건의 `taskMemory.xxx`에서 key 추출

### 6. taskEditorPosition 생성

노드 위치를 자동 배치:
- TRIGGER: `{ x: 0, y: 0 }`
- 이후 노드: x +400씩 증가
- 분기 시: y +400씩 증가

edgePositions는 모든 노드 간 연결을 반영.

### 7. JSON 출력

최종 JSON 구조:
```json
{
  "task": {
    "name": "{task_name}",
    "trigger": "{trigger_text}",
    "filter": {},
    "targetMediums": [{ "mediumType": "native" }],
    "memorySchema": [...],
    "nodes": [...],
    "startNodeId": "{first_node_id}"
  },
  "taskEditorPosition": {
    "nodePositions": [...],
    "edgePositions": [...]
  }
}
```

출력 경로: `{output_dir}/{task_name}.json` (파일명에서 공백 → 언더스코어)

### 8. 검증

생성된 JSON을 아래 체크리스트로 검증:
- [ ] 모든 next.to가 존재하는 노드 ID 또는 END_TASK
- [ ] startNodeId가 nodes에 존재
- [ ] 모든 메모리 key가 memorySchema에 선언
- [ ] agent 노드에 종료 조건 명시
- [ ] code 노드에 onError 설정 (API 호출 시)
- [ ] 자기 자신을 가리키는 next 없음

검증 통과 시 결과 출력:
```
✅ 변환 완료: {task_name}.json
   노드: {N}개 (agent: {a}, code: {c}, message: {m})
   메모리 변수: {N}개
   분기: {N}개
```

## 주의사항

- API URL은 `{{BASE_URL}}`로 플레이스홀더 — 개발팀이 실제 URL로 교체해야 함
- 변환된 JSON은 draft 상태 — `/settings-task`로 업로드 후 채널톡에서 검수 필요
- Mermaid 구문이 복잡한 경우 (서브그래프 등) 단순화하여 변환
