---
name: userchat-to-alf-setup
description: Complete end-to-end pipeline for transforming Excel customer support data into production-ready Agent SOP documents, flowcharts, ALF implementation package, individual ALF registration files, and client-facing deployment scenario through 7 stages.
---

# Userchat-to-ALF-Setup Complete Pipeline

## Overview

Orchestrates the complete pipeline: Excel data → Clustering → Pattern Extraction → SOP Generation → Flowcharts → ALF Package → ALF Document Export → Deployment Scenario.

**Language:** Detect the language from the user's first message and respond in that language throughout. Support Korean (한국어) and Japanese (日本語). Default to Korean if language is unclear.

**Pipeline Flow:**
```
Excel Input (고객 상담 데이터)
    ↓
Stage 1: Clustering (Python) [~3 min]
    → clustered_data.xlsx, cluster_tags.xlsx, analysis_report.md
    ↓
Stage 2: Pattern Extraction (LLM) [~8 min]
    → patterns.json (with sop_topic_map), faq.json, patterns_enriched.json
    ↓
Stage 3: SOP Generation + Verification (LLM) [~12 min]
    → TS_*.sop.md, HT_*.sop.md (verified against real conversations)
    ↓
Stage 4: Flowchart Generation (LLM) [~4 min, optional]
    → *_FLOWCHART.md (Mermaid markdown)
    ↓
Stage 5: ALF Implementation Package (LLM + Python) [~25 min]
    → rules_draft.md, rag_items.md, tasks, api_requirements,
      alf_implementation_guide.md, analysis_report.md
    ↓
Stage 6: ALF Document Export (LLM) [~10 min]
    → 07_alf_documents/rules/ (individual rule files), 07_alf_documents/rag/ (individual RAG docs)
    ↓
Stage 7: Deployment Scenario (LLM) [~5 min]
    → deployment_qa_set.html, deployment_qa_set.md (+ optional Notion)
```

**Total Time**: ~65-80 minutes

## Parameters

### Required
- **language** (default: "ko"): `"ko"` (Korean) or `"ja"` (Japanese)

### Stage 1 Parameters (자동 수집)
- `input_file`: data/ 디렉토리에서 자동 감지
- `company`: 파일명에서 자동 추출
- `output_dir`: `results/{company}`로 자동 설정
- `sample_size`: 기본값 3000
- `k`: 기본값 "auto"

### Optional
- **auto_proceed** (default: true): `true` = 단계 간 자동 진행, `false` = 단계마다 확인
- **generate_flowcharts** (default: true): Stage 4 실행 여부
- **flowchart_target** (default: "all"): `"all"`, `"ts_only"`, `"ht_only"`
- **flowchart_format** (default: "markdown"): `"markdown"`, `"svg"`, `"both"`
- **generate_alf_package** (default: true): Stage 5 실행 여부
- **generate_alf_export** (default: true): Stage 6 실행 여부
- **generate_deployment_scenario** (default: true): Stage 7 실행 여부
- **notion_parent_page** (default: none): Notion 부모 페이지 URL/ID (Stage 7에서 사용)

## Steps

### 1. Initialize Pipeline

**Actions:**
- Detect language from user's first message
- Set `LANGUAGE={language}` for all Python script executions
- Check `.env` for `UPSTAGE_API_KEY`:
  - If missing: run `/request-api-key` flow inline (send Channel.io message, wait for reply, write to .env)
  - MUST NOT proceed until key is confirmed valid
- Validate: `pip install -r requirements.txt`

---

### 2. Execute Stage 1: Clustering

Run `/stage1-clustering` with auto-detected parameters.

**Outputs:**
- `results/{company}/01_clustering/{company}_clustered.xlsx`
- `results/{company}/01_clustering/{company}_tags.xlsx`
- `results/{company}/01_clustering/{company}_messages.csv`
- `results/{company}/01_clustering/analysis_report.md`

**Quality Checks:** Clustering succeeded, no single cluster >50%, silhouette score >0.05

**Transition:** If `auto_proceed=true`, proceed immediately. Otherwise ask user.

---

### 3. Execute Stage 2: Pattern Extraction

Run `/stage2-extraction` with auto-detected parameters.

**Key defaults (updated):**
- `min_total_samples`: **500** (increased from 300)
- `n_samples_per_cluster`: `max(25, ceil(500 / K))`

**Outputs:** `patterns.json` (with `sop_topic_map`), `faq.json`, `keywords.json`, `patterns_enriched.json`

**Quality Checks:** All JSON valid, patterns extracted, FAQ pairs are specific

**Transition:** If `auto_proceed=true`, proceed immediately. Otherwise ask user.

---

### 4. Execute Stage 3: SOP Generation + Verification

Run `/stage3-sop-generation` with auto-detected parameters.

**Key change:** Stage 3 now includes a **verification loop** — each SOP is tested against 3-5 real conversations from enriched data, and gaps are fixed before finalizing.

**Outputs:**
- `results/{company}/03_sop/HT_*.sop.md` (multiple files)
- `results/{company}/03_sop/TS_*.sop.md` (multiple files)
- `results/{company}/03_sop/metadata.json`

**Quality Checks:** Template structure followed, Cases include concrete details, verification coverage >70%

**Transition:** If `auto_proceed=true`, proceed immediately. Otherwise ask user.

---

### 5. Execute Stage 4: Flowchart Generation (optional, default enabled)

Run `/stage4-flowchart-generation`.

**Skip if:** `generate_flowcharts=false` or user declines during review.

**Outputs:** `*_FLOWCHART.md`, optionally `*_flowchart.svg`

---

### 6. Execute Stage 5: ALF Implementation Package (default enabled)

Run `/stage5-sop-to-guide` with the following **pipeline-mode overrides**:

**Skip if:** `generate_alf_package=false`

**Note:** Steps 3-A (cross_analysis + heatmap) and 3-B (automation_analysis) run as **intermediate inputs** for Steps 6-7, but are NOT listed as pipeline deliverables.

**Pipeline deliverables (final outputs):**
- `results/{company}/06_sales_report/alf_setup/rules_draft.md`
- `results/{company}/06_sales_report/alf_setup/rag_items.md`
- `results/{company}/05_tasks/TASK{N}_{name}.md`
- `results/{company}/{company}_api_requirements.md`
- `results/{company}/{company}_alf_implementation_guide.md`
- `results/{company}/06_sales_report/{company}_analysis_report.md`

**Intermediate files (generated but not deliverables):**
- `06_sales_report/analysis/cross_analysis.json`
- `06_sales_report/analysis/heatmap.png`
- `06_sales_report/analysis/automation_analysis.md`
- `06_sales_report/sales_report_config.json`

**Quality Checks:** Rules draft has 9 sections, RAG items have Priority 1+2, ROI figures generated

**Transition:** If `auto_proceed=true`, proceed immediately. Otherwise ask user.

---

### 7. Execute Stage 6: ALF Document Export (default enabled)

Run `/stage6-alf-document-export`.

**Skip if:** `generate_alf_export=false` or Stage 5 was skipped.

**Outputs:**
- `results/{company}/07_alf_documents/rules/01~09_*.md` (9 individual rule files)
- `results/{company}/07_alf_documents/rag/*.md` (individual RAG knowledge documents)

**Quality Checks:** Rule file count matches sections, RAG doc count matches rag_items

---

### 8. Execute Stage 7: Deployment Scenario (default enabled)

Run `/stage7-deployment-scenario`.

**Skip if:** `generate_deployment_scenario=false` or Stage 6 was skipped.

**Outputs:**
- `results/{company}/08_deployment/deployment_qa_set.html` (고객사 공유용)
- `results/{company}/08_deployment/deployment_qa_set.md` (로컬 보관용)
- Notion pages (if `notion_parent_page` provided)

**Quality Checks:** All categories mapped, each has test queries, Step 1/2 classification consistent with api_requirements

---

### 9. Validate and Summarize

**Verify all outputs exist:**
```
results/{company}/
├── 01_clustering/  (clustered.xlsx, tags.xlsx, messages.csv, analysis_report.md)
├── 02_extraction/  (patterns.json, faq.json, keywords.json, patterns_enriched.json)
├── 03_sop/         (HT_*.sop.md, TS_*.sop.md, metadata.json, *_FLOWCHART.md)
├── 05_tasks/       (TASK{N}_{name}.md)
├── 06_sales_report/
│   ├── alf_setup/  (rules_draft.md, rag_items.md)
│   └── {company}_analysis_report.md
├── 07_alf_documents/  (rules/ + rag/)
├── 08_deployment/  (deployment_qa_set.html, deployment_qa_set.md)
├── {company}_api_requirements.md
├── {company}_alf_implementation_guide.md
└── pipeline_summary.md
```

**Generate `pipeline_summary.md`** with execution info, statistics per stage, verification results, key insights, and next steps.

**Communicate results:**
```
✅ Userchat-to-SOP Pipeline Complete: {Company}

📊 Results
  - Records: {N}, Clusters: {K}
  - Patterns: {P}, FAQ Pairs: {F}
  - SOP Files: {count} (TS: {ts}, HT: {ht})
  - Verification Coverage: {X}%
  - Flowcharts: {fc_count}
  - Rules: 9 sections → {rule_files} individual files
  - RAG Items: Priority 1: {p1} / Priority 2: {p2} → {rag_docs} documents
  - Tasks: {task_count} / APIs: {api_count}
  - 해결율: 보수적 {X}% ~ 낙관적 {Y}%
  - QA 세트: Step 1 {s1}건 + Step 2 {s2}건

📁 Output: results/{company}/
📄 Key reports:
  - {company}_alf_implementation_guide.md (ALF 도입 가이드)
  - {company}_analysis_report.md (데이터 분석 리포트)
  - 08_deployment/deployment_qa_set.html (배포 시나리오 & QA 세트)
```

---

## Pipeline Defaults

| Stage | Parameter | Default |
|-------|-----------|---------|
| 1 | sample_size | 3000 |
| 1 | k_range | 8,10,12,15,20,25 |
| 2 | min_total_samples | **500** |
| 2 | n_samples_per_cluster | max(25, ceil(500/K)) |
| 3 | verification | **enabled** (3-5 conversations per SOP) |
| 4 | flowchart_target | all |
| 4 | flowchart_format | markdown |
| 5 | intermediate_artifacts | generated but not deliverables |
| 6 | enabled | true (requires Stage 5) |
| 7 | enabled | true (requires Stage 6) |
| 7 | notion_parent_page | none (local files only) |

## Pipeline-mode vs Standalone-mode Differences

When running Stage 5 as part of the full pipeline (`/userchat-to-alf-setup`), the following are skipped or demoted:

| Artifact | Pipeline mode | Standalone (`/stage5-sop-to-guide`) |
|----------|--------------|--------------------------------------|
| `cross_analysis.json` | Generated (intermediate) | Deliverable |
| `heatmap.png` | Generated (intermediate) | Deliverable |
| `automation_analysis.md` | Generated (intermediate) | Deliverable |
| `sales_report_config.json` | Generated (intermediate) | Deliverable |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Stage 1 fails | `pip install -r requirements.txt`, check UPSTAGE_API_KEY |
| Stage 2 too slow | Reduce `min_total_samples` to 300, or `focus_clusters="top_10"` |
| SOPs too generic | Stage 3 verification should catch this; if not, increase Stage 2 samples |
| Stage 5 fails | Check ANTHROPIC_API_KEY (for dialog classification), verify Stage 1-3 outputs exist |
| Stage 6 fails | Verify `rules_draft.md` and `rag_items.md` exist from Stage 5 |
| Stage 7 fails | Verify `cross_analysis.json`, `rag_items.md`, `api_requirements.md` exist from Stage 5-6 |
| Need to resume | Each stage runs independently: `/stage2-extraction`, `/stage5-sop-to-guide`, `/stage7-deployment-scenario`, etc. |
| Flowchart fails | Use `flowchart_format="markdown"` (no CLI needed) |

## Notes

- **Hybrid approach**: Python for clustering (fast, deterministic), LLM for extraction and composition (language understanding)
- **Stage 2: sequential processing in main agent** — no subagents (causes hanging)
- **Stage 3 verification loop** is the key quality improvement — invests tokens in checking rather than elaborate prompts
- **Stage 5 pipeline mode**: Skips QA scenarios; intermediate analysis files are generated for report input but not listed as deliverables
- **Stage 6** depends on Stage 5 — if Stage 5 is skipped, Stage 6 is also skipped
- **Stage 7** depends on Stage 6 — generates client-facing deployment scenario + QA set from existing outputs (~5 min)
- Cost: ~$2-5 per 1000 records (Upstage + Claude, full pipeline including Stage 5-7)
- Each stage is independent and can be resumed separately
