---
name: stage6-alf-document-export
description: Split rules_draft.md into individual rule files and expand rag_items.md into standalone RAG knowledge documents for direct ALF registration.
---

# Stage 6: ALF 문서 개별 파일 분리

## Overview

Stage 5에서 생성된 `rules_draft.md`(규칙 초안)와 `rag_items.md`(RAG 항목 목록)를 **ALF에 바로 등록 가능한 개별 파일**로 분리합니다.

- **규칙 분리**: `rules_draft.md`의 9개 섹션 → 개별 `.md` 파일
- **RAG 문서 생성**: `rag_items.md`의 각 항목 → SOP/FAQ 기반 확장된 지식 문서

**Language:** Detect the language from the user's first message and respond in that language throughout. Support Korean (한국어) and Japanese (日本語). Default to Korean if language is unclear.

**입력 파일:**
```
06_sales_report/alf_setup/rules_draft.md   → 규칙 초안 (9개 섹션)
06_sales_report/alf_setup/rag_items.md     → RAG 지식 항목 목록
03_sop/*.sop.md                            → 원본 SOP (RAG 문서 확장 참조)
02_extraction/faq.json                     → FAQ 원본 데이터 (RAG 문서 확장 참조)
```

**산출물:**
```
results/{company}/
└── 07_alf_documents/
    ├── rules/                         ← 개별 규칙 파일 (신규)
    │   ├── 01_tone_manner.md
    │   ├── 02_empathy_rules.md
    │   ├── 03_escalation_conditions.md
    │   ├── 04_issue_response_flow.md
    │   ├── 05_knowledge_reference.md
    │   ├── 06_feedback_collection.md
    │   ├── 07_repeated_question.md
    │   ├── 08_special_rules.md
    │   └── 09_non_automatable.md
    └── rag/                           ← 개별 RAG 지식 문서 (신규)
        ├── {토픽1_한글명}.md
        ├── {토픽2_한글명}.md
        └── ...
```

---

## Parameters

### Required
- **company**: 회사 식별자 (예: `kmong_v2`, `usimsa`)

### Optional
- **output_dir** (기본값: `results/{company}`): 출력 기본 디렉토리

---

## Steps

### 1. Validate Input Files

**Actions:**
1. Scan `results/` for company directories containing `06_sales_report/alf_setup/rules_draft.md`
2. Use `AskUserQuestion` to confirm the target company
3. Verify all input files exist:
   - `results/{company}/06_sales_report/alf_setup/rules_draft.md`
   - `results/{company}/06_sales_report/alf_setup/rag_items.md`
   - `results/{company}/03_sop/` (at least 1 `.sop.md` file)
   - `results/{company}/02_extraction/faq.json`

**Constraints:**
- If `rules_draft.md` or `rag_items.md` is missing, STOP and inform the user to run Stage 5 first
- SOP and FAQ files are optional for rule splitting but required for RAG document generation

**Expected Output:**
```
✅ 입력 파일 확인 완료
  - rules_draft.md: ✅ (9개 섹션 감지)
  - rag_items.md: ✅ (Priority 1: X항목 / Priority 2: X항목)
  - SOP 디렉토리: ✅ (X개 SOP)
  - faq.json: ✅
```

---

### 2. Split rules_draft.md into Individual Files

**Actions:**
1. Read `rules_draft.md` and identify all top-level sections (`## 1.` through `## 9.`)
2. Create `results/{company}/07_alf_documents/rules/` directory
3. For each section, extract the full content (including all sub-sections) and write to an individual file

**File naming convention:**
| Section | File Name |
|---------|-----------|
| 1. Tone & Manner | `01_tone_manner.md` |
| 2. 공감 표현 규칙 | `02_empathy_rules.md` |
| 3. Escalation Conditions | `03_escalation_conditions.md` |
| 4. 이슈 문의 응대 흐름 | `04_issue_response_flow.md` |
| 5. 지식 참조 원칙 | `05_knowledge_reference.md` |
| 6. 피드백 수집 규칙 | `06_feedback_collection.md` |
| 7. 반복 질문 대응 | `07_repeated_question.md` |
| 8. 고객사별 특수 규칙 | `08_special_rules.md` |
| 9. Non-automatable Situations | `09_non_automatable.md` |

**Each file format:**
```markdown
# {섹션 제목}

> 원본: rules_draft.md — 섹션 {N}
> 회사: {company_name}

---

{해당 섹션의 전체 내용 — 서브섹션, 테이블, 예시 모두 포함}
```

**Constraints:**
- **2,000자 제한 (필수)**: 채널톡 ALF Rules API의 `instruction` 필드는 최대 2,000자. 모든 규칙 파일은 **제목 행을 제외하고 2,000자 이내**여야 한다.
  - 분리 후 각 파일의 글자 수를 `wc -m`으로 검증
  - 2,000자를 초과하는 파일은 **서브 섹션 단위로 추가 분할** (예: `09_master_rules.md` → `09a_designated_rules.md` + `09b_fallback_defense.md`)
- **간결한 포맷**: 불필요한 마크다운 테이블, 이미지 참조, 장황한 예시를 제거하고 순수 텍스트/불렛 형태로 압축
  - 테이블 → 불렛 리스트로 변환
  - 긴 블록 인용 → 핵심만 1-2줄로 축약
  - 예시는 1개만 유지 (복수 예시 제거)
- If a section does not exist in the source file, skip it and note in the verification report
- Sub-section numbering (### 1.1, ### 1.2, etc.) MUST be preserved

**Expected Output:**
```
✅ 규칙 파일 분리 완료
  - 생성 파일: {N}개
  - 건너뛴 섹션: {있으면 목록, 없으면 "없음"}
```

---

### 3. Generate Individual RAG Knowledge Documents

**Actions:**
1. Read `rag_items.md` and parse each knowledge item (Priority 1 + Priority 2)
2. For each item, read the relevant SOP files and FAQ entries referenced in `rag_items.md`
3. Write an expanded knowledge document for each item to `results/{company}/07_alf_documents/rag/`

**File naming:** Use the Korean topic name with underscores (e.g., `세금계산서_수수료_구조_안내.md`)

**Each RAG document format:**

```markdown
# {토픽 한글 제목}

{토픽에 대한 1-2문장 소개}

---

## {하위 주제 1}

{FAQ 데이터와 SOP 내용을 결합한 상세 설명}
{고객이 실제로 물어보는 형태로 구조화}

- 절차는 **순서대로** 단계별 안내
- 조건/제한사항 반드시 포함
- 수치/기한은 정확하게 명시

> 💡 {핵심 팁 또는 참고사항}

---

## {하위 주제 2}
...
```

**Content generation rules:**
- Each document MUST be self-contained — a reader should understand the topic without referring to other files
- Include ALL FAQ Q/A pairs from `faq.json` that belong to this topic
- Include relevant procedure steps, conditions, and exceptions from the SOP
- Use customer-friendly language (not internal/technical terms)
- Include tips (💡) for commonly confused points
- Include warnings (⚠️) for irreversible actions or important conditions
- Do NOT fabricate information not present in the source SOP/FAQ data
- Priority 2 (Fallback) items: Write the fallback guidance as a standalone document

**Constraints:**
- Every Priority 1 and Priority 2 item from `rag_items.md` MUST have a corresponding file
- "고객사 추가 권장 항목" from `rag_items.md` are NOT generated as files — they are noted in the verification report as items the client needs to provide

**Expected Output:**
```
✅ RAG 문서 생성 완료
  - Priority 1 문서: {X}개
  - Priority 2 문서: {X}개
  - 고객사 추가 권장: {X}개 (파일 미생성, 클라이언트 제공 필요)
```

---

### 4. Verification — Completeness & Quality Check

After generating all files, perform a systematic verification.

**4-A. Completeness Check (누락 검증)**

1. **규칙 파일**: Compare section count in `rules_draft.md` vs generated file count in `rules/`
2. **RAG 문서**: Compare item count in `rag_items.md` vs generated file count in `07_alf_documents/rag/`
3. List any gaps found

**4-B. Content Quality Check (품질 검증)**

For each RAG document, verify:
1. **FAQ 커버리지**: All referenced FAQ IDs from `rag_items.md` are covered in the document
2. **절차 완전성**: Multi-step procedures include all steps (not truncated)
3. **수치 정확성**: Numbers/dates match the source SOP exactly
4. **자기완결성**: Document makes sense without referring to other files

**4-C. Verification Report**

Present the verification results to the user:

```
📋 검증 결과

[규칙 파일]
  원본 섹션: {N}개 → 생성 파일: {N}개 → {✅ 일치 / ⚠️ 불일치}
  {불일치 시 상세 내역}

[RAG 문서]
  rag_items 항목: {N}개 → 생성 문서: {N}개 → {✅ 일치 / ⚠️ 불일치}
  FAQ 커버리지: {covered}/{total} ({%})
  {불일치 시 상세 내역}

[고객사 추가 권장 항목] (파일 미생성)
  - {항목 1}: {필요 사유 요약}
  - {항목 2}: {필요 사유 요약}
  ...

수정이 필요한 부분이 있으면 말씀해주세요.
```

**Constraints:**
- You MUST present the verification report to the user and wait for feedback before declaring completion
- If the user requests changes, apply them and re-run the verification for the changed files only

---

### 5. Summary

After user approval, present the final summary:

```
✅ Stage 6 완료 — ALF 문서 개별 파일 분리

[규칙 파일] results/{company}/07_alf_documents/rules/
  {파일 목록}

[RAG 지식 문서] results/{company}/07_alf_documents/rag/
  {파일 목록}

[다음 단계]
  1. 07_alf_documents/rules/ 파일 → ALF 시스템 프롬프트에 규칙별로 등록
  2. 07_alf_documents/rag/ 파일 → ALF RAG 지식 DB에 등록
  3. 고객사 추가 권장 항목 {X}건 → 클라이언트에게 작성 요청
```

---

## Notes

### Relationship to Stage 5

This skill is a post-processing step after Stage 5's Step 2. It takes the monolithic outputs (`rules_draft.md`, `rag_items.md`) and converts them into granular, directly-usable files.

**When to use:**
- After Stage 5 has completed successfully
- When the client needs individual files for ALF system registration
- When rules or RAG items need to be updated independently

### RAG Document Quality Principles

Following the 6 knowledge reference principles from `rules_draft.md`:
1. Only include content confirmed in the data
2. Procedures in complete sequential order
3. Conditions and limitations always included
4. Exact numbers and deadlines
5. Role distinction (if applicable, e.g., seller vs buyer)
6. Honest about gaps — mark missing info as "(확인 필요)"
