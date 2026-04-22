---
name: userchat-to-alf-setup
description: Complete end-to-end pipeline for transforming Excel customer support data into production-ready ALF setup files (rules, RAG documents, tasks). Optimized for minimal token usage — generates only the artifacts needed for Channel.io ALF registration.
---

# Userchat-to-ALF-Setup Pipeline

## Overview

Excel 상담 데이터 → 클러스터링 → 패턴 추출 → SOP 생성 → ALF 세팅 파일 (규칙 + RAG + 태스크) 생성.

**보고서/분석 산출물은 생성하지 않습니다.** 보고서가 필요하면 `/stage5-sop-to-guide` 를 standalone으로 실행하세요.

**Language:** Detect the language from the user's first message and respond in that language throughout. Support Korean (한국어) and Japanese (日本語). Default to Korean if language is unclear.

**Pipeline Flow:**
```
Excel Input (고객 상담 데이터)
    ↓
Stage 1: Clustering (Python) [~3 min]
    → clustered_data.xlsx, cluster_tags.xlsx, messages.csv
    ↓
Stage 2: Pattern Extraction (LLM) [~8 min]
    → patterns.json, faq.json, patterns_enriched.json
    ↓
Stage 3: SOP Generation + Verification (LLM) [~12 min]
    → TS_*.sop.md, HT_*.sop.md
    ↓
Stage 5: ALF Setup Files (Python + LLM) [~10 min]
    → rules_draft.md, rag_items.md, TASK*.md, api_requirements.md
    ↓
Stage 6: ALF Document Export (LLM) [~10 min]
    → rules/ (individual rule files), rag/ (individual RAG docs)
    ↓
Value Proposition Slide (LLM) [~5 min]
    → {company}_ALF전환_가치제안.html (Reveal.js 프레젠테이션)
```

**Total Time**: ~40-50 minutes

## Parameters

### Required
- **language** (default: "ko"): `"ko"` (Korean) or `"ja"` (Japanese)

### Stage 1 Parameters (자동 수집)
- `input_file`: data/ 디렉토리에서 자동 감지
- `company`: 파일명에서 자동 추출
- `output_dir`: `results/{company}`로 자동 설정
- `sample_size`: 기본값 3000
- `k`: 기본값 "auto"

### App Functions (앱태스크 연동)
- **app_functions** (default: false): 앱태스크(앱함수) 연동 여부. Stage 5에 전달됨 — 상세 설명은 `/stage5-sop-to-guide` Parameters 참조
- **app_functions_services** (default: `[]`): 연동된 앱 서비스 목록. Stage 5에 전달됨

### Optional
- **auto_proceed** (default: true): `true` = 단계 간 자동 진행, `false` = 단계마다 확인

## Steps

### 1. Initialize Pipeline

**Actions:**
- Detect language from user's first message
- Set `LANGUAGE={language}` for all Python script executions
- Check `.env` for `UPSTAGE_API_KEY`:
  - If missing: run `/request-api-key` flow inline (send Channel.io message, wait for reply, write to .env)
  - MUST NOT proceed until key is confirmed valid
- Validate: `pip install -r requirements.txt`
- **Collect app function info**: Ask whether the client uses app task functions (앱태스크):
  - "이 고객사는 이지어드민, 카페24, 사방넷 등 **앱태스크(앱함수) 연동**을 사용하고 있나요?"
  - If yes: ask which services are connected (이지어드민 / 카페24 / 사방넷 / 기타)
  - Store as `app_functions=true` and `app_functions_services=[...]`
  - This will be passed to Stage 5 so that task planning uses app functions where applicable instead of custom code nodes

---

### 2. Execute Stage 1: Clustering

Run `/stage1-clustering` with auto-detected parameters.

**Pipeline-mode override:**
- `analysis_report.md` 생성 생략 (후속 스테이지에서 미사용)

**Outputs:**
- `results/{company}/01_clustering/{company}_clustered.xlsx`
- `results/{company}/01_clustering/{company}_tags.xlsx`
- `results/{company}/01_clustering/{company}_messages.csv`

**Quality Checks:** Clustering succeeded, no single cluster >50%, silhouette score >0.05

---

### 3. Execute Stage 2: Pattern Extraction

Run `/stage2-extraction` with auto-detected parameters.

**Key defaults:**
- `min_total_samples`: **500**
- `n_samples_per_cluster`: `max(25, ceil(500 / K))`

**Outputs:** `patterns.json` (with `sop_topic_map`), `faq.json`, `patterns_enriched.json`

**Quality Checks:** All JSON valid, patterns extracted, FAQ pairs are specific

---

### 4. Execute Stage 3: SOP Generation + Verification

Run `/stage3-sop-generation` with auto-detected parameters.

**Outputs:**
- `results/{company}/03_sop/HT_*.sop.md` (multiple files)
- `results/{company}/03_sop/TS_*.sop.md` (multiple files)
- `results/{company}/03_sop/metadata.json`

**Quality Checks:** Template structure followed, Cases include concrete details, verification coverage >70%

---

### 5. Execute Stage 5: ALF Setup Files

Run `/stage5-sop-to-guide` with **pipeline-mode overrides**.

**Pipeline-mode overrides passed to Stage 5:**
- `app_functions` = value collected in Step 1 (skip stage5's own question)
- `app_functions_services` = list collected in Step 1

**⚠️ Pipeline-mode: Step 2 + Step 5만 실행. 나머지 스킵.**

| Step | 실행 여부 | 사유 |
|------|-----------|------|
| Step 1 (파라미터 수집) | ✅ 실행 | 회사명, 파일 경로 확인 필요. 단, `monthly_volume`, `hourly_wage` 등 ROI 관련 파라미터는 수집하지 않음 |
| Step 2 (rules_draft + rag_items) | ✅ 실행 | **핵심 산출물** |
| Step 3 (교차분석 + 자동화분석) | ❌ 스킵 | 보고서용. ALF 세팅에 불필요 |
| Step 4 (ROI 계산) | ❌ 스킵 | 보고서용 |
| Step 5 (태스크 + API 요건) | ✅ 실행 | **핵심 산출물**. SOP만으로 태스크 생성 (automation_analysis 없이) |
| Step 6 (도입 가이드) | ❌ 스킵 | 영업 보고서 |
| Step 7 (분석 리포트) | ❌ 스킵 | 데이터 분석 보고서 |

**Outputs:**
- `results/{company}/06_sales_report/alf_setup/rules_draft.md`
- `results/{company}/06_sales_report/alf_setup/rag_items.md`
- `results/{company}/05_tasks/TASK{N}_{name}.md`
- `results/{company}/{company}_api_requirements.md`

---

### 6. Execute Stage 6: ALF Document Export

Run `/stage6-alf-document-export`.

**Outputs:**
- `results/{company}/07_alf_documents/rules/01~09_*.md` (9 individual rule files)
- `results/{company}/07_alf_documents/rag/*.md` (individual RAG knowledge documents)

**Quality Checks:** Rule file count matches sections, RAG doc count matches rag_items

---

### 7. Generate Value Proposition Slide (LLM)

파이프라인 산출물 데이터를 기반으로 고객사 맞춤 ALF 가치 제안 프레젠테이션을 생성합니다.

**Template**: `templates/ALF_VALUE_PROPOSITION_template.html` (Reveal.js)

**Source data:**
- `01_clustering/`: 분석 건수, 클러스터 수, 날짜 범위
- `02_extraction/patterns.json`: 상위 문의 유형, 빈도, 패턴
- `02_extraction/faq.json`: FAQ 항목 수
- `03_sop/*.sop.md`: SOP 수, 주요 시나리오
- `06_sales_report/alf_setup/rules_draft.md`: 규칙 수, 주요 규칙 내용
- `06_sales_report/alf_setup/rag_items.md`: 지식 항목 수, 항목 목록
- `05_tasks/TASK*.md`: 태스크 수, 태스크 목록
- `07_alf_documents/rules/`, `07_alf_documents/rag/`: 개별 파일 수

**슬라이드 구성** (템플릿 구조 기반, 데이터에 맞게 조정):

| # | 슬라이드 | 내용 | 소스 |
|---|---------|------|------|
| S1 | **커버** | "{Company} 상담 X건 중 Y건, ALF가 해결할 수 있습니다" + 분석 건수/유형 수/ALF 해결률/첫 응답 시간 | 전체 |
| S2 | **현재 상황** | 현행 봇의 한계 (해결률, 전환률) — 데이터에서 봇 메시지 패턴 분석 | clustering, patterns |
| S3 | **반복 문의 패턴** | 야간/주말 비율 + Top 문의 유형 바 차트 | patterns, clustering |
| S4 | **ALF 세팅 완료** | 규칙/지식/태스크 수량 + 항목 pill 목록 | rules, rag_items, tasks |
| S5~S7 | **ALF 데모** (Top 2~3 시나리오) | 주요 문의 유형별 Before/After + 채팅 위젯 데모 | SOPs, patterns |
| S8 | **숫자로 보는 차이** | ALF 해결 가능 비율, 주요 유형별 커버리지 | patterns, SOPs |
| S9 | **ALF 관여 레이어** | 완전해결/승인노드/초벌상담/주제분류 4단계 | SOPs, tasks |
| S10 | **ALF가 못 하는 것** | 상담사 필요 케이스 (데이터 기반) | SOPs escalation |
| S11 | **도입 로드맵** | Phase 1 (즉시) → Phase 2 (API 연동) 타임라인 | tasks, api_requirements |
| S12 | **CTA** | 다음 단계 안내 + 연락처 | — |

**작성 규칙:**
- 템플릿의 CSS/스타일을 그대로 사용 (Reveal.js CDN, Pretendard 폰트, 컬러 변수)
- 모든 수치는 파이프라인 산출물에서 추출한 실제 데이터 사용 — 추측/가공 금지
- 데모 슬라이드의 채팅 위젯(`ct-widget`)에는 SOP에서 추출한 실제 시나리오 사용
- `{company}` 이름은 공식 회사명 (한글) 사용
- 슬라이드 수는 데이터에 따라 10~15개 범위로 조정 (데모 시나리오 수에 따라 유동적)

**Output:**
- `results/{company}/{company}_ALF전환_가치제안.html`

---

### 8. Validate and Summarize

**Verify all outputs exist:**
```
results/{company}/
├── 01_clustering/  (clustered.xlsx, tags.xlsx, messages.csv)
├── 02_extraction/  (patterns.json, faq.json, patterns_enriched.json)
├── 03_sop/         (HT_*.sop.md, TS_*.sop.md, metadata.json)
├── 05_tasks/       (TASK{N}_{name}.md)
├── 06_sales_report/
│   └── alf_setup/  (rules_draft.md, rag_items.md)
├── 07_alf_documents/
│   ├── rules/      (01~09_*.md)
│   └── rag/        (*.md)
├── {company}_api_requirements.md
└── {company}_ALF전환_가치제안.html  ← NEW
```

**Communicate results:**
```
✅ ALF Setup Complete: {Company}

📊 Results
  - Records: {N}, Clusters: {K}
  - Patterns: {P}, FAQ Pairs: {F}
  - SOP Files: {count} (TS: {ts}, HT: {ht})
  - Rules: 9 sections → {rule_files} individual files
  - RAG Items: Priority 1: {p1} / Priority 2: {p2} → {rag_docs} documents
  - Tasks: {task_count} / APIs: {api_count}

📁 Output: results/{company}/
📊 Value Proposition: {company}_ALF전환_가치제안.html
🚀 다음 단계:
  - /settings-rules 로 규칙 업로드
  - /settings-rag 로 RAG 문서 업로드
  - /settings-task 로 태스크 업로드
```

---

## Skipped Stages (pipeline-mode)

아래는 이 파이프라인에서 생략됩니다. 필요 시 standalone으로 개별 실행하세요.

| 생략 항목 | Standalone 명령 | 용도 |
|-----------|----------------|------|
| Stage 1 analysis_report | `/stage1-clustering` | 클러스터링 분석 요약 |
| Stage 4 Flowcharts | `/stage4-flowchart-generation` | Mermaid 플로우차트 |
| Stage 5 교차분석/ROI/보고서 | `/stage5-sop-to-guide` | 영업 보고서 + 데이터 분석 리포트 |
| Stage 7 배포 시나리오 | `/stage7-deployment-scenario` | 고객사 공유용 QA 세트 |

## Pipeline Defaults

| Stage | Parameter | Default |
|-------|-----------|---------|
| 1 | sample_size | 3000 |
| 1 | k_range | 8,10,12,15,20,25 |
| 2 | min_total_samples | **500** |
| 2 | n_samples_per_cluster | max(25, ceil(500/K)) |
| 3 | verification | **enabled** (3-5 conversations per SOP) |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Stage 1 fails | `pip install -r requirements.txt`, check UPSTAGE_API_KEY |
| Stage 2 too slow | Reduce `min_total_samples` to 300, or `focus_clusters="top_10"` |
| SOPs too generic | Stage 3 verification should catch this; if not, increase Stage 2 samples |
| Stage 5 fails | Verify Stage 1-3 outputs exist |
| Stage 6 fails | Verify `rules_draft.md` and `rag_items.md` exist from Stage 5 |
| Need full reports | Run `/stage5-sop-to-guide` standalone (all steps enabled) |
| Need flowcharts | Run `/stage4-flowchart-generation` standalone |
| Need deployment QA | Run `/stage7-deployment-scenario` standalone |

## Notes

- **Hybrid approach**: Python for clustering (fast, deterministic), LLM for extraction and composition (language understanding)
- **Stage 2: sequential processing in main agent** — no subagents (causes hanging)
- **Stage 3 verification loop** is the key quality improvement — invests tokens in checking rather than elaborate prompts
- **Pipeline-mode vs Standalone**: This pipeline generates ONLY ALF setup files. For reports/analysis, use `/stage5-sop-to-guide` standalone
- Cost: ~$1-3 per 1000 records (Upstage + Claude, setup-only pipeline)
- Each stage is independent and can be resumed separately
