---
name: stage7-deployment-scenario
description: Generate a client-facing deployment scenario and QA set from pipeline outputs (Stages 1-6). Maps consultation categories to resolution methods (RAG/Task) and deployment steps, with test queries per category. Outputs HTML + Markdown, optionally publishes to Notion.
---

# Stage 7: 배포 시나리오 & QA 세트 생성

## Overview

Stage 1~6 산출물을 재구조화하여 **고객사 공유용 배포 시나리오 + QA 세트**를 생성합니다.
기존 분석 데이터를 새로 생성하지 않고 **조합/재구성**만 수행합니다.

**Language:** Detect the language from the user's first message and respond in that language throughout. Support Korean (한국어) and Japanese (日本語). Default to Korean if language is unclear.

**핵심 산출물:**
- 상담 카테고리 × 빈도 × 해결방식(RAG/Task) × 배포 단계(Step 1/2) 매핑
- 각 카테고리별 테스트 쿼리(고객 발화 예시 + 기대 답변) 포함 QA 세트
- HTML 형식 (고객사 공유) + Markdown (로컬 보관)

**배포 단계 정의:**

| 단계 | 범위 | 소요 기간 | 담당 | 설명 |
|------|------|-----------|------|------|
| **Step 1-1** | RAG + rules 로 ALF가 완결하는 흐름 | 2~3일 | CS팀 | 정보 안내만으로 상담 종료. 상담사 개입 불필요. |
| **Step 1-2** | RAG + rules 에서 상담사 연결이 필요한 흐름 | 2~3일 | CS팀 | ALF가 초기 응대/정보 수집 후 상담사로 전환. **고객사와 조율 필수** — 어떤 시점에 연결할지, 어떤 정보를 사전 수집할지 구체적으로 정의해야 함. |
| **Step 2** | API 호출 코드노드 포함 task | 1~2주 | CS팀 + 개발팀 | 고객사 개발 필요. |

> **Step 1-1 vs 1-2 구분 기준**: 동일 카테고리 안에서도 흐름에 따라 나뉨.
> 예) "AS 비용/보증기간" → "배송비 얼마?" = 1-1 (정보 안내 완결) / "무상인지 유상인지 봐주세요" = 1-2 (상담사 판단 필요)

**커버리지 지표 정의:**

| 지표 | 정의 | 산출 방식 |
|------|------|-----------|
| **관여율** | 전체 상담 중 ALF가 개입하는 비율 | Step에 해당하는 카테고리 건수 합계 / 전체 건수 |
| **해결율** | ALF가 개입한 상담 중 상담사 개입 없이 완료한 비율 | `automation_analysis.md`의 보수적 조정값 (완전 해결 + 승인노드) |
| **커버리지** | 전체 상담 대비 ALF가 자동 완료하는 비율 | **관여율 × 해결율** |

> 요약 테이블에는 관여율, 해결율, 커버리지(= 관여율 × 해결율)를 모두 표기합니다.

**입력 파일:**
```
06_sales_report/analysis/cross_analysis.json  → 카테고리 빈도
06_sales_report/alf_setup/rag_items.md        → RAG 항목 (Priority 1/2)
{company}_api_requirements.md                 → API 필요/불필요 태스크 분류
05_tasks/TASK*.md                             → 태스크 정의
02_extraction/faq.json                        → FAQ Q/A 쌍 (테스트 쿼리 소스)
03_sop/*.sop.md                               → SOP Case 시나리오 (테스트 쿼리 소스)
06_sales_report/analysis/automation_analysis.md → 커버리지 수치
{company}_alf_implementation_guide.md          → ROI 수치
```

**산출물:**
```
results/{company}/08_deployment/
├── deployment_qa_set.html    ← QA 세트 (고객사 공유용, 인라인 CSS)
├── deployment_qa_set.md      ← QA 세트 (로컬 보관용 마크다운)
└── deployment_flow.html      ← 토픽→해결방식→Step 매핑 시각화 (SVG)
```

**Estimated Time**: ~5 minutes

---

## Parameters

### Required
- **company**: 회사 식별자 (예: `ppodeuk`, `usimsa_v2`)

### Optional
- **output_dir** (default: `results/{company}/08_deployment`): 출력 디렉토리
- **notion_parent_page** (default: none): Notion 부모 페이지 URL/ID. 제공 시 Notion에 퍼블리싱.

---

## Steps

### 1. Validate Input Files

**Actions:**
1. Scan `results/` for company directories containing `06_sales_report/analysis/cross_analysis.json`
2. Use `AskUserQuestion` to confirm target company
3. Verify all input files exist:
   - `cross_analysis.json` (REQUIRED)
   - `rag_items.md` (REQUIRED)
   - `{company}_api_requirements.md` (REQUIRED)
   - `05_tasks/TASK*.md` (REQUIRED, at least 0 — some companies may have no tasks)
   - `02_extraction/faq.json` (REQUIRED — for test queries)
   - `03_sop/*.sop.md` (REQUIRED — for test queries)
   - `automation_analysis.md` (optional — for coverage figures)
   - `alf_implementation_guide.md` (optional — for ROI figures)

**Constraints:**
- If `cross_analysis.json`, `rag_items.md`, or `api_requirements.md` is missing, STOP and inform user to run Stages 5-6 first
- If `faq.json` or SOPs are missing, STOP and inform user to run Stage 2-3 first

**Expected Output:**
```
✅ 입력 파일 확인 완료
  - cross_analysis.json: ✅ ({N} topics, {N} total chats)
  - rag_items.md: ✅ (Priority 1: {N}항목 / Priority 2: {N}항목)
  - api_requirements.md: ✅ (API 필요: {N}개 / 불필요: {N}개)
  - tasks: {N}개
  - faq.json: ✅ ({N} pairs)
  - SOPs: {N}개
```

---

### 2. Build Category Mapping Table

Read the source files and build the master mapping of categories to resolution methods and deployment steps.

**Actions:**
1. Read `cross_analysis.json` → extract `topic_dialog_cross` for per-topic record counts. Calculate each topic's total count and percentage of `total_chats`. Sort by count descending.

2. Classify each topic's **resolution method**:
   - Read `rag_items.md`:
     - Topics referenced ONLY in Priority 1 items (지식응답/정책확인) → **RAG**
   - Read `api_requirements.md`:
     - Section 3 "API 불필요 태스크" → **RAG** (knowledge response only) or **RAG + 상담사** (if listed as requiring agent handling)
     - Section 1 "API 필요 태스크" → **Task (API)**
   - Read `05_tasks/TASK*.md` file list:
     - Topics with a TASK file → **Task**
     - Check each TASK: if it has API call nodes (dashed orange border in Mermaid, or listed in api_requirements Section 1) → **Task (API)** = Step 2
     - If TASK has NO API calls → **Task (단순)** = Step 1

3. Assign **deployment step** — classify at the **flow level**, not just category level. A single category can have BOTH Step 1-1 and Step 1-2 flows:
   - **Step 1-1**: FAQ/정책 정보 안내만으로 상담 종료되는 흐름. 판단/증빙/사진 확인 불필요.
   - **Step 1-2**: ALF가 초기 응대/정보 수집 후 상담사 연결이 필요한 흐름. **고객사와 사전 조율 필요** — 어떤 시점에 전환할지, 어떤 정보를 수집할지 구체적으로 정의.
   - **Step 2**: API 호출이 필요한 Task
   - **상담사 전환**: Topics classified as `7_상담사전환` dominant in cross_analysis

4. Step 1-1 vs 1-2 구분 방법:
   - Read `faq.json` — Q/A 쌍의 answer가 정보 안내로 끝나는지(1-1), "AS 접수 양식 수집" / "사진/영상 보내주세요" / "상담사 확인 후 안내" 등으로 이어지는지(1-2) 판단
   - Read SOP Cases — Case의 최종 단계가 "안내 완료"면 1-1, "상담사 연결" / "수동 처리" / "증빙 판단"이면 1-2
   - 동일 카테고리의 서로 다른 흐름은 각각 1-1과 1-2에 배치

5. **Step 1-2 상세 요구사항** (고객사 조율 필수 항목):
   각 1-2 흐름에 대해 다음을 명시:
   - **ALF 처리 범위**: ALF가 어디까지 하는지 (예: 증상 확인 + 양식 수집)
   - **상담사 전환 시점**: 정확히 어떤 조건에서 상담사로 넘기는지
   - **사전 수집 정보**: 전환 전 ALF가 수집해야 할 데이터 목록
   - **고객사 확인 필요 사항**: 고객사와 합의해야 할 포인트 (예: 불량 판단 기준, 환불 승인 권한)

**Output format** (internal, used for Step 3-4):
```
[
  { topic: "HT_USAGE_ACCESSORIES", count: 214, pct: 7.5, flows: [
    { flow: "소모품 구매 안내", step: "1-1", resolution: "RAG" },
    { flow: "모델 미확인 → 상담사 확인", step: "1-2", resolution: "RAG → 상담사" }
  ]},
  { topic: "TS_PRODUCT_DEFECT_TRIAGE", count: 628, pct: 22.1, flows: [
    { flow: "자가점검 안내 (정상 범위 증상)", step: "1-1", resolution: "RAG" },
    { flow: "불량 판단 → AS 접수", step: "1-2", resolution: "RAG → 상담사", handoff_point: "사진 증빙 판단", pre_collect: ["성함","연락처","모델명","증상","사진"] }
  ]},
  { topic: "TS_AS_RECEIPT", count: 579, pct: 20.4, flows: [
    { flow: "AS 접수 자동화", step: "2", resolution: "Task (API)", task: "TASK1", apis: ["주문조회","AS접수등록"] }
  ]},
  ...
]
```

**Constraints:**
- Every topic in `cross_analysis.json` MUST appear in the mapping — no omissions
- A topic can appear in BOTH Step 1 (RAG part) and Step 2 (Task part) if it has both knowledge items and API tasks
- Resolution method MUST be derived from source files, not guessed

---

### 3. Generate Test Queries

For each **flow** (not just category) in the mapping table, generate 1-2 test queries.

**Actions:**

**For Step 1-1 flows (ALF 완결):**
1. Read `02_extraction/faq.json` — find Q/A pairs where the answer is self-contained information
2. Select the most representative 1-2 pairs
3. Format as:
   - **구체적 쿼리**: The actual customer utterance from FAQ
   - **기대 답변**: The expected answer summary (information-only, no agent handoff)

**For Step 1-2 flows (상담사 연결) — DETAILED:**
1. Read `faq.json` + `03_sop/*.sop.md` — find flows that end in agent handoff
2. For each flow, document:
   - **구체적 쿼리**: Customer utterance that triggers this flow
   - **ALF 응대 범위**: What ALF handles before handoff (e.g., self-check guide, form collection)
   - **상담사 전환 시점**: Exact condition/trigger for agent handoff
   - **사전 수집 정보**: Data ALF must collect before handoff (e.g., 성함, 연락처, 모델명, 증상, 사진)
   - **고객사 확인 필요**: What needs to be agreed with the client (e.g., defect judgment criteria, refund authority)

**For Step 2 flows (Task API):**
1. Read the corresponding `05_tasks/TASK*.md` — extract the trigger scenario
2. Read the corresponding `03_sop/*.sop.md` — extract Case 1 customer scenario
3. Format as:
   - **구체적 쿼리**: Realistic customer request that triggers this task
   - **기대 플로우**: Expected task execution flow (from TASK file summary table)
4. Note the required API endpoints

**Constraints:**
- Test queries MUST use natural customer language, not technical terms
- Expected answers MUST come from SOP/FAQ source data — no fabrication
- Each category MUST have at least 1 test query
- Maximum 2 test queries per category (1 concrete + 1 abstract if data allows)

---

### 4. Generate Output Files

#### 4-A. deployment_qa_set.md (Markdown)

Write the structured document following this format:

```markdown
# {회사명} ALF 배포 시나리오 & QA 세트

> 작성일: {YYYY-MM-DD} | 분석 규모: {N}건 / {K}개 카테고리
> Step 1 예상 소요: 2~3일 | Step 2 예상 소요: +1~2주

---

## 요약

| 구분 | 항목 수 | 관여율 | 해결율 | 커버리지 (관여율 × 해결율) |
|------|--------|--------|--------|--------------------------|
| **Step 1** (RAG + 규칙 + 단순 태스크) | {N}개 카테고리 | {A}% | {B}% | **{A×B/100}%** |
| **Step 2** (API 연동 태스크) | {N}개 카테고리 | 누적 {C}% | {D}% | 누적 **{C×D/100}%** |
| 상담사 전환 | {N}개 카테고리 | {E}% | — | — |

> **관여율** = 해당 Step 카테고리 건수 / 전체 건수
> **해결율** = ALF 개입 상담 중 상담사 없이 완료 비율 (automation_analysis.md 보수적 기준)
> **커버리지** = 관여율 × 해결율

---

## Step 1: RAG + 규칙 + 단순 태스크 (2~3일)

> CS팀만으로 세팅 가능. 규칙 등록 + RAG 지식 등록 + 단순 태스크 설정.

### {토픽 한글명} — {N}건 ({X}%) | RAG

| # | 유형 | 고객 발화 예시 | 기대 답변 | QA 결과 |
|---|------|-------------|----------|---------|
| 1 | 구체 | "{실제 고객 발화}" | {기대 답변 요약} | |
| 2 | 추상 | "{짧은/다른 표현}" | {기대 답변 요약} | |

### {토픽 한글명} — {N}건 ({X}%) | Task (단순)

| # | 유형 | 고객 발화 예시 | 기대 플로우 | QA 결과 |
|---|------|-------------|-----------|---------|
| 1 | 구체 | "{실제 고객 요청}" | {기대 처리 흐름} | |

---

## Step 2: API 연동 태스크 (+1~2주)

> 고객사 개발팀 API 개발 필요. 개발 완료 후 태스크 코드노드 연결.

### {토픽 한글명} — {N}건 ({X}%) | Task (API: {API명})

> 필요 API: {endpoint 목록}

| # | 유형 | 고객 발화 예시 | 기대 플로우 | QA 결과 |
|---|------|-------------|-----------|---------|
| 1 | 구체 | "{실제 고객 요청}" | {기대 처리 흐름} | |

---

## 전체 QA 요약

| # | 카테고리 | 빈도 | 해결 방식 | Step | QA 항목 수 | 결과 |
|---|---------|------|----------|------|-----------|------|
| 1 | {토픽명} | {N}건 ({X}%) | RAG | 1 | {N} | |
| 2 | {토픽명} | {N}건 ({X}%) | Task (API) | 2 | {N} | |
| ... | | | | | | |
| **합계** | | **{total}건** | | | **{total_qa}** | |
```

#### 4-B. deployment_qa_set.html (HTML)

Convert the Markdown to a standalone HTML file with these features:
- **Inline CSS only** — no external dependencies, single file
- **Clean, professional design**: Light gray background, white card sections, subtle borders
- **Collapsible sections**: Step 1 and Step 2 sections use `<details><summary>` for fold/unfold
- **QA result checkboxes**: Each QA row has an interactive checkbox (`<input type="checkbox">`)
- **Print-friendly**: `@media print` styles that expand all sections and show checkboxes as boxes
- **Color coding**: Step 1 items in green accent, Step 2 in orange accent, 상담사전환 in red accent
- **Summary stats at top**: Total categories, Step 1/2 counts, coverage percentages
- **Responsive**: Works on both desktop and mobile screens
- **Korean font stack**: `"Pretendard", "Noto Sans KR", sans-serif`

**Constraints:**
- HTML file MUST be completely self-contained (no CDN, no external CSS/JS)
- File size should be reasonable (~50-100KB max)
- Tables MUST be properly formatted with borders and padding
- The HTML MUST render correctly when opened directly in a browser (`file://` protocol)

#### 4-C. deployment_flow.html (시각화)

Generate a standalone HTML file with an inline SVG chart showing the 3-column flow:

**3-Column Layout:**
1. **왼쪽 — 상담 토픽 (빈도)**: Colored bars with height proportional to record count. Show topic name + count + percentage.
2. **가운데 — 해결 방식**: RAG/Rules box + Task (API) box. Show aggregate counts.
3. **오른쪽 — 배포 단계**: Step 1-1 (green), Step 1-2 (blue), Step 2 (orange) boxes. Show flow counts + coverage + timeline.

**Flow Lines:**
- Curved paths (`<path>` with cubic bezier) connecting topics → resolution → steps
- Line thickness proportional to record count
- Color matches the destination step
- Opacity 0.3-0.6 for readability

**Right-side Annotations:**
- For topics that split across Step 1-1 and 1-2, show annotation boxes listing which flows go where

**Design Requirements:**
- Inline SVG within HTML (no external images)
- `viewBox` based sizing for responsiveness
- Same CSS conventions as 4-B (font stack, background, print styles)
- Legend at bottom explaining colors

**Reference**: Use `results/오아/08_deployment/deployment_flow.html` as the structural reference. Adapt the data (topic names, counts, flow mappings) from the category mapping table built in Step 2.

---

### 5. Notion Publishing (optional)

**Skip if:** `notion_parent_page` is not provided.

**Actions:**
1. Use `AskUserQuestion` to get the Notion parent page URL or ID (if not already provided as parameter)
   - If user says 'skip', skip this step entirely
2. Fetch the parent page using `mcp__claude_ai_Notion__notion-fetch` to validate access
3. Create a hub page: `{회사명} ALF 배포 시나리오` under the parent page using `mcp__claude_ai_Notion__notion-create-pages`
   - Include the full deployment scenario content (converted to Notion markdown)
4. Create a QA tracking database under the hub page using `mcp__claude_ai_Notion__notion-create-database`:
   ```sql
   CREATE TABLE (
     "카테고리" TITLE,
     "빈도" NUMBER,
     "해결 방식" SELECT('RAG':blue, 'Task (단순)':green, 'Task (API)':orange, '상담사':red),
     "배포 단계" SELECT('Step 1':green, 'Step 2':orange),
     "테스트 쿼리" RICH_TEXT,
     "기대 답변" RICH_TEXT,
     "QA 결과" SELECT('Pass':green, 'Fail':red, '미테스트':gray),
     "메모" RICH_TEXT
   )
   ```
5. Create one row per QA item using `mcp__claude_ai_Notion__notion-create-pages`

**Constraints:**
- Notion page content MUST follow Notion's enhanced markdown spec
- If Notion API fails, skip gracefully and note in the summary — local files are the primary output

---

### 6. Verification + Summary

**Verify:**
1. **Completeness**: Every topic from `cross_analysis.json` appears in the output
2. **Classification consistency**: Step assignments match `api_requirements.md`
3. **Test query coverage**: Every category has at least 1 test query
4. **File integrity**: `.md`, `.html`, and `deployment_flow.html` all exist and are non-empty

**Present verification report:**
```
📋 검증 결과
  카테고리 수: cross_analysis {N}개 → QA 세트 {N}개 → ✅ 일치
  Step 1 항목: {N}개 (RAG {N} + 단순 Task {N})
  Step 2 항목: {N}개 (API Task {N})
  상담사 전환: {N}개
  테스트 쿼리: 총 {N}개 (카테고리당 평균 {X}개)
  Notion: {✅ 퍼블리싱 완료 / ⏭️ 스킵}

수정이 필요한 부분이 있으면 말씀해주세요.
```

**After user approval, present final summary:**
```
✅ Stage 7 완료 — 배포 시나리오 & QA 세트

📁 Output:
  - results/{company}/08_deployment/deployment_qa_set.md
  - results/{company}/08_deployment/deployment_flow.html
  - results/{company}/08_deployment/deployment_qa_set.html
  {- Notion: {page_url} (있는 경우)}

📊 요약:
  - 전체 카테고리: {N}개
  - Step 1 (2~3일): {N}개 → 관여율 {A}% × 해결율 {B}% = 커버리지 {X}%
  - Step 2 (+1~2주): {N}개 → 누적 관여율 {C}% × 해결율 {D}% = 누적 커버리지 {Y}%
  - QA 시나리오: 총 {N}개
```

---

## Notes

### Data Flow

```
cross_analysis.json ──→ 카테고리 빈도
rag_items.md ──────────→ RAG 분류 (Priority 1 = Step 1)
api_requirements.md ───→ Task 분류 (API 유무 → Step 1/2)
faq.json ──────────────→ RAG 테스트 쿼리 (Q/A 쌍)
03_sop/*.sop.md ───────→ Task 테스트 쿼리 (Case 시나리오)
automation_analysis.md → 커버리지 수치
alf_implementation_guide.md → ROI 수치
```

### Category Resolution Logic

```
Topic in api_requirements Section 3 ("API 불필요")
  → RAG or RAG + 상담사 → Step 1

Topic in api_requirements Section 1 ("API 필요")
  → Task (API) → Step 2

Topic not in api_requirements
  → Check rag_items.md Priority 1 → RAG → Step 1
  → Check dominant dialog type in cross_analysis:
    1_지식응답 / 4_정책확인 → RAG → Step 1
    7_상담사전환 → 상담사 전환
    Otherwise → Step 1 (conservative default)
```

### Handling Topics That Span Both Steps

Some topics may have BOTH a RAG component (Step 1) and a Task component (Step 2). For example:
- "서비스 해지" has a RAG knowledge item (해지 방법 안내) AND a Task (TASK2 해지 처리 API)
- In this case, list the topic in BOTH Step 1 (RAG part) and Step 2 (Task part) with clear labels

### HTML Design Principles

- Professional, clean design suitable for client presentation
- No JavaScript frameworks — vanilla HTML/CSS only
- Checkboxes for QA tracking work without JS (native `<input type="checkbox">`)
- `<details>/<summary>` for collapsible sections (native HTML5, no JS)
- Print styles for PDF export
