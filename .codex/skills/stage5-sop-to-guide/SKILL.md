---
name: stage5-sop-to-guide
description: Generate an ALF implementation package from all pipeline outputs. Produces rules draft, RAG knowledge items, dialog type cross-analysis heatmap, automation feasibility analysis, ROI calculation, task flowcharts (05_tasks/), API requirements doc, and final ALF implementation guide. **Language:** Auto-detects Korean (한국어) or Japanese (日本語) from user input.
---

# Stage 5: ALF 구축 패키지 생성

## Overview

Stage 1~3 산출물을 모두 활용하여 ALF(AI 챗봇) 도입을 위한 **구축 패키지**를 생성합니다.
단순 ROI 리포트를 넘어, 실제 챗봇 구축에 필요한 규칙 초안·RAG 항목·자동화 전략을 함께 제공합니다.

**Language:** Detect the language from the user's first message and respond in that language throughout. Support Korean (한국어) and Japanese (日本語). Default to Korean if language is unclear.

**입력 파일:**
```
01_clustering/{company}_messages.csv   → 대화 원시 데이터 (cluster_id 포함)
01_clustering/{company}_tags.xlsx      → 클러스터 메타 (라벨/크기)
02_extraction/patterns.json, faq.json      → 패턴/FAQ
03_sop/*.sop.md + *_FLOWCHART.md          → SOP/플로우차트
03_sop/metadata.json                       → SOP 커버리지 정보
```

**Stage Flow:**
```
입력 (Stage 1~3 산출물)
    ↓
Step 1: 파라미터 수집 (회사, 월 상담 건수, 시급 등 + ALF 세팅 현황)
    ↓
Step 2: LLM — SOP + patterns/faq 기반 분석
    → rules_draft.md          (규칙 초안)
    → rag_items.md            (RAG 필요 항목)
    ↓
Step 3: 대화유형 분류 + 교차분석 + 자동화 분석
    scripts/analyze_dialogs.py  (Claude API 우선, Upstage Solar fallback)
    → cross_analysis.json + heatmap.png
    에이전트 직접 작성 (API 호출 없음)
    → automation_analysis.md  (자동화 가능성)
    ↓
Step 4: Python — ROI 계산
    python3 scripts/generate_sales_report.py
    → sales_report_config.json + ROI 수치
    ↓
Step 5: LLM — 태스크 정의 + API 요건 정의서
    → 05_tasks/TASK{N}_{이름}.md   (태스크별 Mermaid 플로우차트 + 요약표)
    → {company}_api_requirements.md  (개발팀용 API 요건 정의서)
    ↓
Step 6: LLM — 최종 통합 보고서 (ALF 도입 가이드)
    → {company}_alf_implementation_guide.md
    ↓
Step 7: LLM — 최종 분석 리포트 (Rosa 프레임워크)
    → {company}_analysis_report.md
```

**산출물 디렉토리:**
```
results/{company}/
├── 05_tasks/                              ← (Stage 5에서 생성)
│   ├── TASK{N}_{이름}.md                  ← 태스크별 Mermaid 플로우차트 + 요약표
│   └── TASK{N}_{이름}.svg                 ← (선택, mmdc 설치 시)
├── {company}_api_requirements.md          ← API 요건 정의서 (개발팀용)
├── {company}_alf_implementation_guide.md  ← 최종 ALF 도입 가이드
└── 06_sales_report/
    ├── alf_setup/
    │   ├── rules_draft.md          ← 규칙 초안 (시스템 프롬프트)
    │   └── rag_items.md            ← RAG 지식 DB 등록 항목
    ├── analysis/
    │   ├── cross_analysis.json     ← 교차분석 원시 데이터
    │   ├── heatmap.png             ← 상담주제 × 대화유형 히트맵
    │   └── automation_analysis.md  ← 자동화 가능성 분석 (4-Layer 모델)
    ├── sales_report_config.json
    └── {company}_analysis_report.md ← 최종 분석 리포트 (Rosa 프레임워크)
```

**Total Time**: ~20–35 minutes (데이터 크기에 따라)

---

## Parameters

### Required
- **company**: 회사 식별자 (예: `usimsa`, `meliens`)
- **monthly_volume**: 월 상담 건수 (실측값 또는 추산, 정수)

### Optional
- **hourly_wage** (기본값: `15100`): 상담사 시급 (원, 임금직업포털 중위값)
- **avg_handling_time_min** (기본값: `8`): 건당 평균 처리 시간 (분)
- **alf_chat_cost** (기본값: `500`): ALF 채팅 참여 비용 (원/건)
- **alf_task_cost** (기본값: `200`): ALF 태스크 실행 비용 (원/건)
- **phase2_min_krw** / **phase2_max_krw**: Phase 2 외주 개발비 범위 (원)
- **output_dir** (기본값: `results/{company}/06_sales_report`): 출력 디렉토리
- **app_functions** (기본값: `false`): 고객사가 앱태스크(앱함수) 연동을 사용하는지 여부. `true` 시 Step 5 태스크 기획에서 코드노드 대신 앱함수를 우선 적용 가능한 항목을 별도 분류함
- **app_functions_services** (기본값: `[]`): 연동된 앱 서비스 목록. 예: `["이지어드민", "카페24", "사방넷"]`

---

## Steps

### 1. Gather Parameters

**Actions:**
1. Scan `results/` for company directories that contain both `01_clustering/` and `03_sop/`
2. **Auto-estimate `monthly_volume`** from Stage 1 data:
   a. Read `results/{company}/01_clustering/pipeline_summary.md` → extract original UserChat count (e.g., "원본 데이터: UserChat 4,969건")
   b. Read the first 2 and last 2 lines of `results/{company}/01_clustering/{company}_messages.csv` → extract `createdAt` min/max to determine date range
   c. Calculate: `estimated_monthly = original_count / (date_range_days / 30)`
   d. If `pipeline_summary.md` is missing, fall back to row count of `{company}_clustered.xlsx` (note this is the sampled count)
3. Use `AskUserQuestion` to collect all required inputs at once — show the estimated monthly volume as the suggested default:
   - Target company (select from detected list or enter manually)
   - `monthly_volume` (show estimated value + calculation basis, user confirms or overrides)
   - `hourly_wage` (show default 15,100원, confirm or update)
   - `phase2_min_krw` / `phase2_max_krw` (outsourcing dev cost range)
   - **앱태스크(앱함수) 연동 여부**: "이지어드민·카페24·사방넷 등 앱함수를 연동하고 있나요? (예/아니오)"
     - 예: 연동된 서비스 목록 선택 (이지어드민 / 카페24 / 사방넷 / 기타)
     - Store as `app_functions=true`, `app_functions_services=[...]`
     - 아니오: `app_functions=false`로 설정, 태스크는 코드노드 기반으로 기획
     - **Skip if `app_functions` was already provided (pipeline mode)**
4. Auto-resolve file paths:
   - `messages_csv` = `results/{company}/01_clustering/{company}_messages.csv`
   - `tags_xlsx` = `results/{company}/01_clustering/{company}_tags.xlsx`
   - `sop_dir` = `results/{company}/03_sop`
   - `patterns_json` = `results/{company}/02_extraction/patterns.json`
   - `faq_json` = `results/{company}/02_extraction/faq.json`

**Monthly Volume Estimation Logic:**
```
원본 건수: pipeline_summary.md → "원본 데이터: UserChat {N}건"
날짜 범위: messages.csv → createdAt min ~ max → {D}일
추정 월간량: {N} × (30 / {D}) = {estimated}건/월

예) 원본 4,969건 / 30일 범위 → 약 4,969건/월
```

**Constraints:**
- You MUST collect ALL inputs in Step 1 — no further questions after this step
- You MUST present the estimated `monthly_volume` with its calculation basis — user confirms or overrides
- If the estimate is based on sampled data (not original count), clearly note "(샘플 기반 추정, 실제보다 낮을 수 있음)"
- If using defaults, mark them as `(기본값)` in the final report
- If using the auto-estimate, mark as `(데이터 기반 추정)` in the final report
- **ALF 세팅 현황**: 규칙·지식·태스크 중 이미 완료된 항목을 확인 → Step 6 ALF 가이드의 ✅/🔧 표시에 반영

**Expected Output:**
```
✅ Stage 5 파라미터 확인
  - Company: kmong_v2
  - messages.csv: results/kmong_v2/01_clustering/kmong_messages.csv ✅
  - tags.xlsx:    results/kmong_v2/01_clustering/kmong_tags.xlsx ✅
  - SOP dir:      results/kmong_v2/03_sop ✅ (11 SOPs)
  - Monthly volume: ~4,969건/월 (데이터 기반 추정: 원본 4,969건 / 30일)
  - Hourly wage: 15,100원 (기본값)
  - Handling time: 8분 (기본값)
  - Phase 2 dev cost: 100~300만원
  - Output: results/kmong_v2/06_sales_report/
```

---

### 2. Rules Draft + RAG Items (Python + LLM)

#### 2-A. Python: Run extract_alf_setup_data.py

```bash
python3 scripts/extract_alf_setup_data.py \
    --sop_dir   results/{company}/03_sop \
    --patterns  results/{company}/02_extraction/patterns.json \
    --faq       results/{company}/02_extraction/faq.json \
    --output    results/{company}/06_sales_report/alf_setup
```

Produces `alf_setup/alf_setup_data.json` containing:
- `tone_rules.examples` — tone & manner examples from all SOP tone sections
- `tone_rules.forbidden` — forbidden phrases (❌) from all SOPs
- `escalation_conditions` — parsed escalation tables from all SOPs (with source SOP)
- `faq_pairs` — all FAQ Q/A pairs from faq.json
- `high_freq_patterns` — high/very-high frequency patterns from patterns.json

#### 2-B. LLM: Write rules_draft.md and rag_items.md

Read `alf_setup/alf_setup_data.json` (single structured file) to produce two output files.

#### 2-A. rules_draft.md — Rules Draft

**No hallucination**: Only include content explicitly stated in the SOPs.

**Reference**: Fetch the ALF 규칙 레퍼런스 Notion page (`https://www.notion.so/channelio/2af74b55ec7c80db947edb39c2d59f96`) using the `mcp__claude_ai_Notion__notion-fetch` tool. This page contains best-practice rule examples and detailed condition values (상담원 연결 조건, 공감 표현, 이슈 응대, 지식 참조 원칙 등) that MUST be used to fill in the detailed condition values of each section. The SOP data provides the company-specific content; the Notion reference provides the structural depth and condition logic.

**금칙 작성 지침 적용** (`금칙 설정 작성 지침.md` 기반):

Transformer Attention 특성상 부정어("~하지 마시오")는 금지 대상 토큰에 가중치가 쏠려 역효과가 발생합니다. 아래 적용 전략을 반드시 준수합니다.

| 적용 강도 | 대상 | 적용 원칙 |
|-----------|------|-----------|
| **Light** | 섹션 1~8 (영역별 규칙) | 원칙 1 (긍정 지시어 치환) + 원칙 2 (If-Then 규칙) |
| **Full** | 섹션 9 (필수 응대 규칙 — 마스터) | 원칙 1 + 2 + 3 (마크다운 격리) + 4 (CoT 검열) + 5 (Fallback 방어) |

**[원칙 1: 긍정 지시어 치환]** — 섹션 1~9 전체 적용
- 모든 부정문을 긍정문으로 치환: "~하지 않음" → "~한다", "금지" → "준수 사항"
- 섹션 헤더도 긍정형: "주의사항"/"금칙사항" → "필수 응대 규칙"/"준수 사항"
- 예: "추측하지 않는다" → "등록된 지식의 내용만을 근거로 답변한다"

**[원칙 2: If-Then 규칙]** — 섹션 1~9 전체 적용
- 각 규칙에 트리거 조건과 출력할 정확한 텍스트를 명시
- 예: "모르는 내용을 지어내지 마세요" → "검색된 문서에 답이 없다면, '확인 후 안내드리겠습니다'라고 응답한다"
- 트리거 조건은 동의어/유사 표현까지 확장: "환불 일자" → "환불 일자/시점/소요 기간/반영 시기"

**[원칙 3: 마크다운 격리]** — 섹션 9에만 적용
- 블록 인용(`>`) + 구분선(`---`)으로 제약 조건을 구조적으로 격리

**[원칙 4: CoT 검열]** — 섹션 9 끝에 1회 배치
- 최종 답변 전 자가 검증 문구: "최종 답변을 생성하기 전, '필수 응대 규칙' 섹션의 규칙을 위반하지 않았는지 내부적으로 검증하세요."

**[원칙 5: 3계층 Fallback 방어]** — 섹션 9에 배치
- Tier 1: 지정 규칙 (R-1 ~ R-N) — 트리거 매칭 시 hardcoded 응답
- Tier 2: 일반 규칙 + RAG 종합 판단 — Tier 1 미매칭 시
- Tier 3: 에스컬레이션 — 명시적 실패 조건 리스트로 상담원 인계

Include all of the following sections:

1. **Tone & Manner** — Three sub-sections:
   - **기본 페르소나**: ALF의 역할 정의 (1~2문장)
   - **말투 규칙**: 격식체/비격식체 혼합, 답변 길이 제한 (400자), 가독성 규칙
   - **응대 가이드라인**: Synthesize SOP tone sections into **behavioral guidelines** (원칙) with supporting examples. Include: 첫 질문 확인 원칙, 첫 인사 1회 원칙, 구체적 경로 안내, 공감 우선, 단계별 해결, 대안 제시, 사전 검증, 마무리 완결성. Aim for 5–10 guidelines.

2. **공감 표현 규칙** — Detailed empathy response rules:
   - **트리거 조건**: 감정 표현 패턴 (툴툴거림, 황당함, 어려움, 불만)
   - **감정별 공감 매핑 테이블**: 고객 감정 → ALF 응답 (최소 3~5개)
   - **강한 불만 시 회유**: 사용 중단 언급 시 공감/사과 → 대안 → 회유
   - Reference the Notion page 공감표현 예시 for structural depth

3. **Escalation Conditions** — Two sub-sections:
   - **상담원 연결 요청 단계별 응대 ({N}회 규칙)**: 1회차(ALF 응대) → 2회차(재안내 + ALF 장점 어필) → {N}회차(즉시 연결). Include exact response templates for each stage. Also cover: 상담 도중 연결 요청, 전화 상담 요청. Reference the Notion page 상담원 연결 조건 for the 3-strike pattern and exact response templates.
   - **즉시 상담원 연결 조건**: Group by situation pattern (강한 불만, AI 불신, 기술 오류, 서비스 장애, 보안, 결제/환불, 견적, API/개발, 외부 연동 등). End with 트리거 키워드 block.

4. **이슈 문의 응대 흐름** — Step-by-step diagnosis flow:
   - **트리거 키워드**: 장애, 오류, 접속 불가 등
   - **응대 플로우**: 오류 화면 요청 → RAG 확인 → 기능 확인 → 원인 분류 (기존 동작 장애 vs 신규 설정 문제) → 상담원 연결 조건
   - Reference the Notion page 이슈문의응대 for the complete flow structure

5. **지식 참조 원칙** — 6 principles (긍정문 기반):
   - 등록된 지식만 근거로 답변, 근거 없으면 "확인 후 안내" 응답, 자사 서비스 정보만 안내, 공식 URL만 제공, 자연스러운 표현 사용, 가능 여부와 대안을 명확히 안내
   - Include If-Then pairs: 트리거 조건 → 출력할 정확한 텍스트
   - Reference the Notion page 지식 참조 예시 for the exact patterns

6. **피드백 수집 규칙** — (SOP에서 피드백/건의 관련 패턴이 발견된 경우):
   - 트리거 조건, 응대 흐름 (공감 → 현황 → 접수 유도 → 배경 요청), 준수 사항

7. **반복 질문 대응** — 횟수별 대응 (1회 상세 → 2회 요약 → 3회+ 상담원 고려)

8. **고객사별 특수 규칙** — SOP에서 해당 고객사에만 적용되는 특수 규칙 (예: 가격 개편 응대, 특정 프로모션 등)

9. **필수 응대 규칙 (마스터)** — 모든 영역에 공통 적용되는 제약 사항을 중앙 집중 관리. Full 적용 (원칙 1~5 모두):
   - **지정 규칙 (R-1 ~ R-N)**: 섹션 1~8에서 추출한 핵심 제약을 긍정문 + If-Then 형태로 통합 정리
   - **Non-automatable situations**: flowchart 🔴 escalation cases (기존 섹션 9 내용)
   - **3계층 Fallback 방어**: Tier 1 (지정 규칙) → Tier 2 (일반 규칙 + RAG) → Tier 3 (에스컬레이션, 명시적 실패 조건 리스트)
   - **CoT 자가 검증 문구**: 섹션 최하단에 배치
   - 블록 인용(`>`) + 구분선(`---`)으로 구조적 격리

**⚠️ 글자 수 제한 (필수)**:
- 채널톡 ALF Rules API는 `instruction` 필드 **최대 2,000자** 제한
- rules_draft.md의 **각 섹션이 2,000자를 초과하지 않도록** 작성
- 초과 예상 시: 불필요한 마크다운 테이블을 불렛으로 변환, 예시를 1개로 축소, 장황한 블록 인용 제거
- 섹션 9(필수 응대 규칙)는 내용이 많으므로 "지정 규칙 + 자동화 불가 상황"과 "Fallback 방어 + CoT 검증"으로 **2개 파일로 분할**되는 것을 전제로 작성

**Output format**: `templates/ALF_RULES_DRAFT_template.md` 구조를 따릅니다.

#### 2-B. rag_items.md — RAG Knowledge Items

List all items that the client needs to register in the vector knowledge DB.

Include:
1. **Priority 1 (immediate)**: FAQs, policies, guides — covering 지식응답/정책확인 dialog types
2. **Priority 2 (supplementary)**: Fallback info for Task failures, error code solutions
3. **고객사 추가 권장 항목**: Items expected to be needed but not found in the sample data

Each item MUST show two things separately:
- **등록해야 할 내용**: The ideal/complete scope the knowledge entry should cover
- **발견된 자료**: The specific content actually confirmed from the sample data

**Output format**: `templates/RAG_ITEMS_template.md` 구조를 따릅니다.

**Constraints:**
- Do NOT fabricate content not present in the SOPs — only use confirmed data for "발견된 자료"
- Prioritize Q/A pairs from faq.json for "발견된 자료"
- Only include patterns classified as 지식응답/정책확인 from patterns.json in Priority 1
- For "등록해야 할 내용", describe the FULL scope the entry should ideally cover (even if sample only shows part of it)
- For "고객사 추가 권장 항목", add items that are typical for this industry/service type but were not found in the sample — minimum 5 items, clearly marked as requiring the client to write from scratch

**Expected Output:**
```
✅ Step 2 complete
  - alf_setup/rules_draft.md: X escalation conditions extracted
  - alf_setup/rag_items.md: Priority 1: X items / Priority 2: X items / 고객사 추가 권장: X items
```

---

### 3. Dialog Type Classification + Cross-Analysis + Automation Feasibility

#### 3-A. 대화유형 분류 + 교차분석

`analyze_dialogs.py`를 실행하여 전체 대화를 7가지 유형으로 분류합니다.

**분류 모델**: Claude API 우선 (ANTHROPIC_API_KEY 설정 시), 없으면 Upstage Solar fallback.
- Claude Sonnet: 맥락 이해도 높음, 비용 ~$1-2/3000건
- Upstage Solar-mini: 저비용 (~$0.05/3000건), 맥락 이해도 중간

```bash
python3 scripts/analyze_dialogs.py \
    --messages results/{company}/01_clustering/{company}_messages.csv \
    --tags     results/{company}/01_clustering/{company}_tags.xlsx \
    --patterns results/{company}/02_extraction/patterns.json \
    --output   results/{company}/06_sales_report/analysis
```

> `--patterns` 옵션은 Stage 2의 `sop_topic_map`을 읽어 히트맵 Y축을 **Stage 1 클러스터가 아닌 Stage 2 재분류 토픽** 기준으로 집계합니다. 생략 시 Stage 1 클러스터 기준으로 동작합니다.

Script produces:
- `analysis/cross_analysis.json` — SOP토픽 × dialog_type 교차표 + 통계
- `analysis/heatmap.png` — 히트맵 PNG

**Expected Output:**
```
✅ analyze_dialogs.py complete
  - Classified: 3000 chats (Claude Sonnet)
  - heatmap.png saved
  - Top types: 1.지식응답 31.0% / 2.정보조회 20.3% / 3.단순실행 15.7%
```

#### 3-B. automation_analysis.md 생성 (에이전트 직접 작성)

Read `cross_analysis.json` and **Stage 2's `response_strategies.json` together** using the Read tool, then
**the agent directly writes** all 5 sections to `analysis/automation_analysis.md`. (No external API calls)

**두 데이터의 역할:**

| 데이터 | 역할 | 알 수 있는 것 |
|--------|------|-------------|
| `cross_analysis.json` | 의도 상한선 (낙관적) | 고객이 무엇을 원했나 (대화유형 분포). 유형 1~4 합계 |
| `response_strategies.json` (Stage 2) | 실제 해결 복잡도 | 해결하려면 실제로 무엇이 필요한가 (automation_opportunity, required_tools) |
| **결합** | **조정값 (보수적)** | 의도 상한선에서 해결 복잡도·에스컬레이션 가능성을 반영하여 하향 조정 |

> `response_strategies.json` 경로: `results/{company}/02_extraction/response_strategies.json`

Include:
1. **히트맵 해석** — 전체 대비 ≥10% 고빈도 셀의 의미 분석
2. **토픽별 2요소 결합 분석** (핵심 섹션) — 각 SOP 토픽마다:
   - 대화유형 분포에서 도출한 **의도 상한선 (낙관적)** = 유형 1~4 합계
   - Stage 2 `automation_opportunity` + `required_tools` 수에서 도출한 **해결 복잡도**
   - 두 요소를 결합한 **조정값 (보수적)** — 에스컬레이션 가능성, 본인 확인 필요 여부, 케이스별 판단 필요 등을 반영하여 하향 조정
   - **해결율 범위**: `조정값(보수적) ~ 의도 상한선(낙관적)` 형태로 표기
   - 조정 근거 한 줄 (예: "단순실행 60%이지만 사진 증빙 + 구매일 분기가 필수이므로 하향")
   - 전체 토픽 건수 가중 평균으로 최종 해결율 범위 산출
3. **대화유형별 ALF 처리 전략** — 7가지 유형 전부 커버 (비율%, 처리방법)
4. **Phase 우선순위** — 보수적 조정값 기준으로 Phase 로드맵 작성
5. **토픽별 인사이트** — 각 토픽의 지배 유형 + 권장 ALF 전략

**해결율 표기 원칙:**
- 단일 수치가 아닌 **조정값(보수적) ~ 의도 상한선(낙관적) 범위**로 항상 표기
- 토픽별: `55% ~ 82.8%` 형태
- 전체 가중 평균: `52.0% ~ 78.3%` 형태
- ROI 계산 (Step 4)에는 **보수적 조정값**을 사용 (보수적 ROI 산출)
- 보고서에는 "보수적 기준 ROI"임을 명시하고, 낙관적 시나리오의 추가 효과를 별도 기재

**Constraints:**
- Do NOT directly equate dialog type ratios from `cross_analysis.json` to automation rates — always combine with `automation_opportunity` from Stage 2 `response_strategies.json`
- **Always report resolution as a range: "조정값(보수적) ~ 의도 상한선(낙관적)"** — single figures are NOT allowed
- Calculate the final overall range as a topic-count **weighted average** (simple average is not allowed)
- Include all 7 dialog types without omission
- ROI calculation MUST use the conservative (조정값) figure, not the optimistic (의도 상한선)

**Expected Output:**
```
✅ automation_analysis.md complete
  - 해결율 범위: 조정값 XX.X% ~ 의도 상한선 XX.X%
  - ROI 기준: 보수적 XX.X% (조정값)
  - 자동화 불가 (상담사전환): X.X%
  - 주요 하향 조정 토픽: {토픽명} (사유)
```

---

### 4. ROI Calculation (Python)

#### 4-A. Write sales_report_config.json

Compile results from Step 2 (SOP analysis) and Step 3 (automation analysis) into the config JSON.

**Required config fields:**
```json
{
  "company": "lowercase_id",
  "company_name": "공식 회사명",
  "report_date": "YYYY-MM-DD",
  "base_params": {
    "monthly_volume": 0,
    "sample_size": 0,
    "agent_hourly_wage": 15100,
    "avg_handling_time_min": 8,
    "alf_chat_cost_per_conversation": 500,
    "alf_task_cost_per_execution": 200
  },
  "development_cost": {
    "phase1_cost_krw": 0,
    "phase2_min_krw": 0,
    "phase2_max_krw": 0,
    "phase2_duration": "약 X~Y개월"
  },
  "sop_groups": [...],
  "resource_table": [...],
  "non_automatable": [...],
  "phase1_notes": [...],
  "phase2_notes": [...],
  "phase2_description": "..."
}
```

#### 4-B. Run generate_sales_report.py

```bash
python3 scripts/generate_sales_report.py \
    --config results/{company}/06_sales_report/sales_report_config.json
```

**Constraints:**
- You MUST run this script — never manually calculate ROI figures
- `sample_size` MUST come from `metadata.json`

**Expected Output:**
```
✅ ROI calculation complete
  Phase 1: monthly net savings ~XXX만원 | annual ~X,XXX만원 | breakeven: immediate
  Full:    monthly net savings ~XXX만원 | annual ~X,XXX만원 | breakeven: ~X~X months
```

---

### 5. Task Definitions + API Requirements (LLM)

Based on the SOP and automation_analysis.md analysis results, generate two documents.

#### 5-A. 05_tasks/ — Task Flowchart Files

Separate scenarios that include API calls into individual task files, one file per task.

**태스크 선정 기준:**
- API 호출 노드가 1개 이상 포함된 시나리오
- 고객 응답 기반 분기가 3단계 이상인 복잡한 플로우
- 상담사 연결 조건이 명확하게 정의된 시나리오

**앱함수(앱태스크) 연동 시 추가 분석 (`app_functions=true`):**

`app_functions=true`이면 [APP_FUNCTIONS.md](APP_FUNCTIONS.md)를 Read로 로드하여 다음을 수행:
- 서비스별 앱함수 스펙 표(이지어드민/사방넷/카페24/스프레드시트)를 참조하여 각 태스크를 `앱함수` / `코드노드` / `앱함수 + 코드노드`로 **일괄 분류** (배치 처리, 태스크별 개별 LLM 호출 금지)
- 분류 결과를 각 태스크 파일 상단 요약표의 "처리 방식" 열에 기재

`app_functions=false`이면: 모든 태스크를 코드노드 기준으로 기획, "처리 방식" 열 생략.

**각 태스크 파일 형식**: `templates/TASK_template.md` 구조를 따릅니다.

SVG 생성 (mmdc 설치 시):
```bash
mmdc -i results/{company}/05_tasks/TASK{N}_{이름}.md -o results/{company}/05_tasks/TASK{N}_{이름}.svg -b transparent
```

#### 5-B. {company}_api_requirements.md — API Requirements Document

Define the APIs used in tasks so that the development team can review them.

**포함 섹션:**
1. API 필요 태스크: 각 API별 호출 시점, 필요 입력/응답, 챗봇 처리 결과, 비고
2. 처리 방식 선택 항목: API 없이도 처리 가능한 케이스 (방식 A/B 선택지)
3. API 불필요 태스크: 지식 응답만으로 처리 가능한 태스크 + 사유
4. 전체 요약 표: API명, 필수/선택, 핵심 응답값, 연결 태스크
5. 공통 전제 사항: 고객 식별자, 응답 속도, 오류 fallback

**각 API 항목 형식**: `templates/API_REQUIREMENTS_template.md` 구조를 따릅니다.

**Constraints:**
- Extract API requirements only from the SOPs and task flowcharts — no guessing
- Write APIs (POST/PUT/DELETE) MUST be separately marked as "optional" or "secondary review"

**Expected Output:**
```
✅ Step 5 complete
  - 05_tasks/: TASK 파일 {X}개 생성
    - 앱함수 처리: {N}개 / 코드노드 처리: {M}개 / 혼합: {K}개  [app_functions=true일 때만 출력]
  - {company}_api_requirements.md: 필수 API {X}개 / 선택 API {X}개
```

---

### 6. Final Integrated Report (LLM)

Compose `{company}_alf_implementation_guide.md` using all outputs.

**Source files:**
- `rules_draft.md`, `rag_items.md` (Step 2)
- `cross_analysis.json`, `heatmap.png`, `automation_analysis.md` (Step 3)
- ROI figures from Step 4 script output
- `05_tasks/*.md`, `{company}_api_requirements.md` (Step 5)

**Report sections:**

| Section | Content | Source |
|---------|---------|--------|
| **요약** | ALF 참여율 최저~최고 범위 + ALF 설정 현황 (✅/🔧) | Step 3, 4 |
| **현황: 상담 유형 분포** | 카테고리별 월 건수·비율·주요 처리 방식 | cross_analysis.json |
| **유형별 하위 흐름 → ALF 처리 매핑** | 세부 흐름을 지식/태스크/상담사로 매핑 | SOPs + Step 5 |
| **ALF 세팅 구성** | 규칙·지식·태스크 현황 + 태스크 목록 + API 개발 목록 | Step 2, 5 |
| **예상 커버리지** | 카테고리별 최저→최고 ALF 참여율 + 기여 분해 | Step 3, 5 |
| **준비 사항** | CS팀·개발팀·채널톡 역할별 작업 목록 | LLM composition |

**시간 절감 표기 (요약 섹션):**
- **4-Layer ALF 관여 모델** 사용:
  - 완전 해결 (100% 시간 절감) / 승인노드 (~90%) / 초벌 상담 (70-80%) / 주제 분류 (30-50%)
- 단일 수치가 아닌 **보수적 ~ 낙관적 범위**로 표기
  - 보수적 = automation_analysis.md의 시간 절감 가중평균 (에스컬레이션·복잡도 반영 하향 조정)
  - 낙관적 = 대화유형 1~4 합계 기준 최대 시간 절감
- ALF 설정 구성 테이블: `상태` 열에 `✅ 세팅 완료` 또는 `🔧 구축 필요` 표시
  - 세팅 완료 여부는 Step 1에서 사용자에게 확인하여 반영

**카테고리별 예상 처리 결과 표기:**
- `해결율 (보수적~낙관적)`, `하향 조정 사유`, `직접 상담사` 열 포함
- 보수적 = 에스컬레이션·본인확인·케이스별 판단 반영 / 낙관적 = 의도 상한선

**Constraints:**
- Resolution rate MUST NOT be a single figure — always express as **조정값(보수적) ~ 의도 상한선(낙관적) range**
- ROI calculation MUST use the conservative (조정값) figure
- Use the setup completion status exactly as confirmed in Step 1
- Use ONLY Step 4 script values for ROI figures (based on conservative rate)

**Expected Output:**
```
✅ Final report complete
  - File: results/{company}/{company}_alf_implementation_guide.md
  - Sections: 6
  - 해결율: 보수적 {X}% ~ 낙관적 {Y}% (ROI는 보수적 기준)
```

---

### 7. Final Analysis Report — Rosa Framework (LLM)


**목적**: `templates/최종 분석 리포트 템플릿.md` 구조를 따르는 상세 분석 리포트 생성.
ALF 패키지(`_alf_package.md`)가 영업/배포 중심이라면, 이 보고서는 **데이터 분석 중심**으로
고객사 내부 팀이 현황을 이해하고 개선 우선순위를 파악하는 용도입니다.

**Source files:**
- `cross_analysis.json` (Step 3) → 섹션 2, 3, 4
- `automation_analysis.md` (Step 3) → 섹션 5, 7
- `tags.xlsx` → 섹션 2 (클러스터 라벨/크기)
- `metadata.json` → 섹션 1 (데이터 규모)
- `patterns.json` → 섹션 6 (추가 인사이트)
- `heatmap.png` → 섹션 4-1

**Report sections** (템플릿 구조 그대로 따름):

| 섹션 | 내용 | 소스 | 데이터 없을 때 |
|------|------|------|--------------|
| **1. 데이터 개요** | 원천 데이터 수치, 운영 현황, 특이사항 | metadata.json, messages.csv | 확인된 수치만 기재, 나머지 `(데이터 미제공)` |
| **2. 상담주제 분포** | 클러스터별 건수·비율·키워드 + 핵심 인사이트 | cross_analysis.json + tags.xlsx | — |
| **3. 대화유형 분포** | 7가지 유형 건수·비율·AI 처리방식 + **의도 상한선 vs 실질 자동화율 비교** | cross_analysis.json + automation_analysis.md | — |
| **4. 교차분석** | 히트맵 + Top 10 조합 + 셀 해석 | cross_analysis.json + heatmap.png | — |
| **5. 자동화 전략** | **클러스터별 2요소 결합 분석** 기반 Phase 로드맵 + 예측 효과 (의도 상한선이 아닌 실질 자동화율 사용) | automation_analysis.md | — |
| **6. 추가 발견사항** | 데이터에서 발견된 특이 패턴 및 운영 인사이트 | patterns.json + SOPs | 최소 3개 이상 |
| **7. 우선순위 권고** | ROI 기준 순위 테이블 | cross_analysis.json + automation_analysis.md | — |
| **8. 요약** | 핵심 지표 요약 테이블 + 핵심 메시지 | 전체 | — |

**Output format**: `templates/최종 분석 리포트 템플릿.md` 구조를 따릅니다.

**Constraints:**
- Fields with no data MUST be marked `(데이터 미제공)` or `(확인 필요)` — never fill by guessing
- Numbers in sections 2, 3, and 4 MUST use only actual values read from `cross_analysis.json`
- **Section 3 automation summary**: Intent ceiling and actual automation rate MUST always be displayed separately — refer to `automation_analysis.md`
- **Section 5 Phase figures**: Use the actual automation rate from section 4 of `automation_analysis.md`, not dialog type ratios
- **Section 8 summary**: A single "automatable ratio" figure is not allowed — show intent ceiling and actual full-automation rate as separate rows
- Section 6 (additional findings) is LLM-written but MUST cite evidence from the data — unsupported statements like "generally…" are not allowed
- Heatmap image MUST be referenced by file path, not inline embedded: `![히트맵](../analysis/heatmap.png)`

**Expected Output:**
```
✅ Analysis report complete
  - File: results/{company}/06_sales_report/{company}_analysis_report.md
  - Sections: 8
  - 데이터 미제공 필드: X개 (운영 현황 일부 등)
```

---

## Related Documentation

- **Dialog Analysis Script**: [analyze_dialogs.py](../../../scripts/analyze_dialogs.py)
- **ROI Calculation Script**: [generate_sales_report.py](../../../scripts/generate_sales_report.py)
- **Rosa Analysis Framework**: [README_ver_rosa.md](../../../README_ver_rosa.md)
- **Analysis Report Template**: `templates/최종 분석 리포트 템플릿.md`

---

## Notes

### Dialog Type Definitions (7 types)

| # | Type | Definition | ALF Processing |
|---|------|------------|---------------|
| 1 | 지식응답 | FAQ, how-to, general info questions | RAG |
| 2 | 정보조회 | Personal order/delivery data lookup | Task (query API) |
| 3 | 단순실행 | Direct action requests (cancel, refund, resend) | Task (execution API) |
| 4 | 정책확인 | Conditional "is this possible?" questions | RAG + branching |
| 5 | 조건부실행 | Situation + action request combined | Task + policy logic |
| 6 | 의도불명확 | Too short or context-dependent utterances | Clarification question |
| 7 | 상담사전환 | Emotional escalation, legal mentions | Escalation |

### Filtering System Auto-Send Clusters

`messages.csv` may include bot/system auto-send clusters (e.g., QR code delivery notifications).
Identify and exclude before classification:
- Check tags.xlsx for clusters labeled "자동발송", "시스템 메시지", "결제 안내"
- Pass cluster IDs to exclude via `--exclude_clusters` option in analyze_dialogs.py
