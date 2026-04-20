---
name: stage3-sop-generation
description: Generate production-ready SOP documents from Stage 2 extraction results, with a verification loop that tests each SOP against real conversations. **Language:** Auto-detects Korean (한국어) or Japanese (日本語) from user input.
---

# Stage 3: SOP Generation with Verification

## Overview

Generate SOP documents from Stage 2 results, then **verify each SOP by testing it against real conversations** to catch gaps and improve quality.

**Language:** Detect the language from the user's first message and respond in that language throughout. Support Korean (한국어) and Japanese (日本語). Default to Korean if language is unclear.

**Input**: Stage 2 results (`patterns.json` with `sop_topic_map`, `faq.json`, `patterns_enriched.json`)
**Output**: SOP files (`.sop.md`) in `results/{company}/03_sop/`

**Key Change from Previous Version:** Instead of spending tokens on elaborate format constraints, this version invests tokens in a **verification loop** — generate the SOP, then test it against real conversations to find and fix gaps.

## Parameters

### Required
- **extraction_output_dir**: Directory with Stage 2 results (e.g., `results/{company}/02_extraction`)
- **company**: Company name
- **sop_title**: Title for the generated SOP set

### Optional
- **sop_type** (default: "customer_support"): `"customer_support"`, `"troubleshooting"`, or `"sales"`

## Steps

### 1. Load Extraction Results

Read all Stage 2 outputs:
1. `patterns.json` — patterns + **`sop_topic_map`** (authoritative topic plan)
2. `faq.json` — FAQ pairs by SOP topic
3. `patterns_enriched.json` — full conversation transcripts per cluster

**Constraints:**
- MUST follow `sop_topic_map` exactly — one SOP per topic, no additions or removals
- MUST read templates before generating: `templates/HT_template.md` and `templates/TS_template.md`
- MUST NOT redesign topic structure (already done in Stage 2)

---

### 2. Extract Concrete Details from Conversations

Before writing any SOP, mine `patterns_enriched.json` for actionable details per topic.

**Extract from agent messages:**
- Internal tool URLs/paths
- Step-by-step instructions agents actually gave (near-verbatim)
- UI navigation paths (e.g., "마이페이지 → 예약내역 → 하단 취소버튼")
- Conditional branches ("~인 경우", "~하셨다면")
- Warning messages ("주의", "중요", "꼭")

**Extract from customer messages:**
- Common expressions describing the problem (verbatim)
- Frequently asked follow-up questions

**Extraction Guardrails:**
- Distinguish **standard procedures** from **exception measures** (one-time workarounds should not become SOP steps)
- Don't over-generalize FAQ escalation phrases to all cases in the same topic
- Each Case in the SOP should cover ONE customer scenario, not mix multiple issues

---

### 3. Generate SOP Documents (per topic)

For each topic in `sop_topic_map`, generate one SOP file.

**File naming:** `HT_{여정단계}_{주제}.sop.md` or `TS_{여정단계}_{주제}.sop.md`

**Template:** Follow `templates/HT_template.md` for HT, `templates/TS_template.md` for TS. Do NOT use Overview/Parameters/Steps/Examples structure.

**Each Case under 해결책 안내 MUST include:**
1. Case 헤더 with 정량적 빈도 (e.g., "전체의 66.7%")
2. 주요 상황 서술 (customer scenario, not technical cause)
3. Step별 안내 멘트 in 블록 인용(>) — actual message-level detail, not "확인해 주세요"
4. 내부 도구 경로 or `{placeholder}` + `<!-- TODO -->` if not found
5. 조건 분기 and 완료 확인 ("~되셨나요?")

**For TS SOPs:** Follow non-destructive order (least → most invasive steps), with confirmation checkpoint after each step.

**Constraints:**
- MUST write SOP using LLM composition, NOT Python auto-generation
- MUST base 안내 멘트 on actual agent messages from enriched data
- MUST NOT invent URLs, tool paths, or contact info not found in data
- MUST save to `results/{company}/03_sop/` (or `03_sop_v2/` if already exists)

---

### 4. Verify Each SOP Against Real Conversations (NEW)

**This is the key quality improvement step.** After generating each SOP, test it against 3-5 real conversations from that topic's enriched data.

**Process per SOP:**

1. **Pick (Case 수 × 2) conversations** from `patterns_enriched.json` that belong to this topic (prefer diverse scenarios). E.g., Case 4개 → 8건, Case 2개 → 4건.
2. **Simulate:** For each conversation, walk through the SOP as if you were the agent:
   - Does the SOP cover this customer's question?
   - Can you follow the steps to reach the same resolution the real agent reached?
   - Are there steps the real agent took that the SOP doesn't mention?
   - Did the real agent give information the SOP lacks?
3. **Record gaps:**
   ```
   Conversation ID: {id}
   Customer issue: "취소하고 싶은데 수수료가 얼마인가요?"
   SOP coverage: ⚠️ Partial — SOP mentions 취소 방법 but doesn't cover 수수료 안내
   Missing: 지역별 취소수수료 차이 설명, 바우처에서 확인하는 방법
   ```
4. **Fix the SOP:** Add missing Cases, steps, or details found during verification
5. **Re-save** the improved SOP

**Constraints:**
- MUST verify every generated SOP (not optional)
- MUST use conversations NOT used during initial extraction if possible (to test generalization)
- MUST document verification results in `extraction_summary.md`
- If >50% of test conversations expose gaps → substantially rewrite the SOP before moving on

**Expected Output per SOP:**
```
✅ SOP 검증 완료: HT_예약전_차량검색.sop.md
  테스트 대화: 5건
  완전 커버: 3건 (60%)
  부분 커버: 2건 (40%) → Case 3에 수수료 안내 추가, Step 2에 앱 경로 보강
  미커버: 0건
```

---

### 5. Generate Summary and Metadata

After all SOPs are generated and verified:

1. Save `metadata.json` with version, source files, statistics, verification results
2. Update `extraction_summary.md` with SOP list and verification coverage

**Output Summary:**
```
✅ Stage 3 완료: {N}개 SOP 생성 + 검증
저장 위치: results/{company}/03_sop/

검증 결과:
  총 테스트 대화: {M}건
  평균 커버율: {X}%
  보강된 SOP: {Y}개
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Cases too generic ("확인해 주세요") | Re-read enriched conversations, extract actual agent messages near-verbatim |
| Cases describe technical causes, not customer scenarios | Rewrite from customer perspective: "고객이 [X]를 하려 하나 [Y] 상태라 불가한 경우" |
| Verification shows >50% gaps | Topic may need more data — go back to Stage 2 and increase samples for that cluster |
| No internal tool paths in data | Use `{placeholder}` + `<!-- TODO -->` — never invent URLs |

## Notes

- **Verification loop is where quality comes from** — generation alone produces 70-80% quality; verification + fix reaches 90%+
- Process SOPs sequentially in main agent for stability
- Templates (`HT_template.md`, `TS_template.md`) define structure — this SKILL focuses on content quality and verification
- Total time: ~10-15 min (generation ~7 min + verification ~5 min), but better quality per token spent
