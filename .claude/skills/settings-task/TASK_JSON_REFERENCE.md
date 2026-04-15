# ALF Task JSON 레퍼런스

> Source: cht-ax-agent/ax-resources (specs + knowledge)
> Task JSON을 생성할 때 이 문서를 참조하세요.

---

## 1. Top-level 구조

```json
{
  "task": { ... },
  "taskEditorPosition": { "nodePositions": [...], "edgePositions": [...] }
}
```

## 2. Task 필수 필드

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | O | Task 이름 (1~50자) |
| `trigger` | string | O | 트리거 조건 자연어 (1~5,000자) |
| `memorySchema` | []MemoryDef | O | 메모리 변수 정의 (최대 50개) |
| `nodes` | []TaskNode | O | 노드 배열 (최대 100개) |
| `startNodeId` | string | O | 시작 노드 ID |
| `targetMediums` | []Medium | - | `[{"mediumType": "native"}]` |
| `filter` | Expression | - | 전역 필터 조건 |

## 3. 노드 타입

### 3.1 Agent Node — LLM 대화
```json
{
  "id": "node-1", "key": "A", "name": "정보 수집",
  "type": "agent",
  "instruction": "## 역할\n...\n## 종료 조건\n...",
  "next": { "type": "goto", "to": "node-2" }
}
```
- instruction 안에서 메모리 읽기/쓰기:
  - 읽기: `<promptdata type="read-variable" subtype="taskMemory" identifier="key">key</promptdata>`
  - 쓰기: `<promptdata type="update-variable" subtype="taskMemory" identifier="key">key</promptdata>`
- **종료 조건 필수** — 없으면 무한 Processing 상태
- instruction 템플릿: `## 역할` → `## 대화 흐름` → `## 안내 메시지` → `## 예외 사항` → `## 종료 조건`

### 3.2 Code Node — API 호출 / 데이터 처리
```json
{
  "id": "node-2", "key": "B", "name": "API 호출",
  "type": "code",
  "code": "const axios = require('axios');\n...\nmemory.save();",
  "next": { "type": "goto", "to": "node-3" },
  "onError": { "type": "goto", "to": "node-error" }
}
```
- Node.js 환경, 최대 60초
- `memory.get('key')` / `memory.put('key', value)` / `memory.save()`
- `context.user.profile.xxx` 로 고객 정보 접근
- **API 호출 시 필수 패턴**: axios + 3회 재시도 + try-catch + onError
- `memory.save()`는 마지막에 한 번만

### 3.3 Message Node — 고정 메시지 전송
```json
{
  "id": "node-3", "key": "C", "name": "안내",
  "type": "message",
  "message": { "blocks": [{ "type": "text", "value": "안내 메시지" }] },
  "next": { "type": "goto", "to": "END_TASK" }
}
```
- 메모리 변수 사용 불가 (변수 필요 시 agent 노드 사용)
- 에러 안내 → 상담사 연결 전에 반드시 사용

### 3.4 UserChatInlineAction Node — 태그/배정
```json
{
  "id": "node-4", "key": "D", "name": "상담사 연결",
  "type": "userChatInlineAction",
  "actions": [
    { "type": "addUserChatTags", "tags": ["에스컬레이션"] },
    { "type": "assignManager", "managerId": "auto" }
  ],
  "next": { "type": "goto", "to": "END_TASK" }
}
```

## 4. 분기 (Branch)

```json
{
  "next": {
    "type": "branch",
    "conditions": [
      {
        "filter": {
          "and": [{ "or": [{
            "key": "taskMemory.order_count",
            "type": "number",
            "operator": "$gt",
            "values": [0]
          }]}]
        },
        "to": "node-있음"
      }
    ],
    "default": "node-없음"
  }
}
```

**연산자**: `$eq`, `$ne`, `$in`, `$nin`, `$exist`, `$nexist`, `$gt`, `$gte`, `$lt`, `$lte`, `$startWith`, `$containsAny`, `$containsAll`

**key 경로**:
- 메모리: `taskMemory.xxx`
- 고객: `user.member`, `user.profile.name`
- 상담: `userChat.state`, `userChat.profile.xxx`

## 5. Memory

```json
"memorySchema": [
  { "key": "customer_name", "type": "string", "description": "고객 이름" },
  { "key": "order_count", "type": "number", "description": "주문 수" },
  { "key": "has_info", "type": "boolean", "description": "정보 존재 여부" }
]
```
- 타입: `string`, `number`, `boolean`, `list`, `listOfNumber`, `date`, `datetime`, `object`, `listOfObject`
- 사용하는 모든 key는 memorySchema에 선언 필수
- Task 종료 시 휘발

## 6. API 호출 코드 스켈레톤

```javascript
const axios = require('axios');
const MAX_RETRIES = 3;
let retryCount = 0;

while (retryCount < MAX_RETRIES) {
  try {
    const response = await axios.get('{{BASE_URL}}/{endpoint}', {
      headers: { 'Content-Type': 'application/json' }
    });
    memory.put('data', response.data);
    console.log('[node-X] 성공:', { /* 필요한 정보 */ });
    break;
  } catch (error) {
    retryCount++;
    if (retryCount >= MAX_RETRIES) {
      console.error('[node-X] 최종 실패:', { error: error.message });
      throw error;  // → onError로 라우팅
    }
  }
}
memory.save();
```

## 7. taskEditorPosition

```json
{
  "nodePositions": [
    { "id": "TRIGGER", "position": { "x": 0, "y": 0 } },
    { "id": "node-1", "position": { "x": 400, "y": 0 } },
    { "id": "node-2", "position": { "x": 800, "y": 0 } }
  ],
  "edgePositions": [
    {
      "sourceNode": { "id": "TRIGGER", "offset": 0, "type": "goto", "index": 0 },
      "targetNode": { "id": "node-1", "offset": 0 }
    },
    {
      "sourceNode": { "id": "node-1", "offset": 0, "type": "goto", "index": 0 },
      "targetNode": { "id": "node-2", "offset": 0 }
    }
  ]
}
```
- TRIGGER 노드는 항상 포함 (x:0, y:0)
- 노드 간격: x +400, 분기 시 y +400
- branch: 조건별로 index 0, 1, 2... / default는 마지막 index

## 8. 검증 체크리스트

- [ ] 모든 next.to가 존재하는 노드 ID 또는 END_TASK를 가리킴
- [ ] startNodeId가 nodes에 존재
- [ ] 모든 메모리 key가 memorySchema에 선언됨
- [ ] agent 노드에 종료 조건 명시
- [ ] code 노드에 onError 설정 (API 호출 시)
- [ ] 자기 자신을 가리키는 next 없음 (무한 루프 방지)
- [ ] 모든 노드가 startNodeId에서 도달 가능
