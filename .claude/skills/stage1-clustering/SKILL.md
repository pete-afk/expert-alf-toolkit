---
name: stage1-clustering
description: This sop executes automated clustering and tagging of customer support chat data through a Python pipeline, producing clustered data, cluster tags, and a comprehensive analysis report for Stage 2 (Pattern Extraction). The agent orchestrates the Python clustering script, monitors execution, validates outputs, and generates an analysis report to guide subsequent extraction work.  **Language:** Auto-detects Korean (한국어) or Japanese (日本語) from user input.
---

# Stage 1: Customer Support Chat Clustering

## Overview

This sop executes automated clustering and tagging of customer support chat data through a Python pipeline, producing clustered data, cluster tags, and a comprehensive analysis report for Stage 2 (Pattern Extraction). The agent orchestrates the Python clustering script, monitors execution, validates outputs, and generates an analysis report to guide subsequent extraction work.

**Language:** Detect the language from the user's first message and respond in that language throughout. Support Korean (한국어) and Japanese (日本語). Default to Korean if language is unclear.

## Parameters

- **input_file** (required): Path to Excel file containing UserChat data with "UserChat data" and "Message data" sheets
- **output_dir** (required): Output directory path where results will be saved
- **company** (required): Company name for analysis context and file naming
- **sample_size** (optional, default: 3000): Number of records to process - use up to 3000 by default, or "all" for complete dataset
- **tagging_mode** (optional, default: "agent"): Cluster tagging method:
  - "agent": Solar-pro unified tagging (5-15 sec, industry-adaptive, recommended)
  - "api": Solar-mini independent tagging (30 sec, basic quality)
  - "skip": Skip tagging for manual Claude tagging later
- **k** (optional, default: "auto"): Number of clusters - use "auto" for optimal selection or integer for fixed count
- **k_range** (optional, default: "8,10,12,15,20,25"): K values to test when k="auto"
- **umap** (optional, default: true): UMAP 차원 축소 적용 (4096D → 30D, silhouette 대폭 개선)
- **umap_components** (optional, default: 30): UMAP 목표 차원 수
- **cache_dir** (optional, default: "cache"): Embedding cache directory
**Constraints for parameter acquisition:**
- You MUST scan data/ directory for Excel files and auto-select if only one exists
- You MUST extract company name from filename (e.g., "user_chat_assacom.xlsx" → "assacom")
- You MUST auto-set output_dir to `results/{company}` unless user specifies otherwise
- You MUST use tagging_mode="agent" always (Solar-pro unified tagging)
- You MUST validate that selected input_file exists and has correct Excel format
- You MUST create output_dir if it doesn't exist
- You MUST NOT ask the user about mode, tagging_mode, or other optional parameters — use defaults
- You SHOULD only ask the user to confirm input_file and company name if ambiguous (multiple files)

## Steps

### 1. Gather Parameters and Setup

Scan available files and gather parameters through interactive selection.

**Constraints:**
- You MUST scan data/ directory for Excel files: `find data -name "*.xlsx" -type f`
- You MUST use AskUserQuestion tool to present file options
- You MUST extract company name from selected filename (e.g., "user_chat_assacom.xlsx" → "assacom")
- You MUST suggest output_dir based on company name (e.g., "results/assacom")
- You MUST verify .env file exists: `test -f .env`
- You MUST create output subdirectory: `mkdir -p {output_dir}/01_clustering`
- You MUST NOT proceed if input validation fails
- Note: Python dependencies are validated automatically when script runs
- You SHOULD display file size for selected file
- You MAY provide custom path option in addition to scanned files

**Parameter Selection Example:**
```
데이터 파일을 선택해주세요:
[ ] data/user_chat_assacom.xlsx (2.3 MB)
[ ] data/user_chat_usimsa.xlsx (1.8 MB)
[ ] data/raw data_meliens.xlsx (3.1 MB)
[ ] 기타 (직접 입력)

출력 디렉토리:
[ ] results/assacom (추천)
[ ] results/assacom_test
[ ] 기타 (직접 입력)

회사명:
[ ] assacom (파일명에서 추출, 추천)
[ ] 기타 (직접 입력)
```

**Expected Outputs:**
```
✅ 파라미터 수집 완료:
  - 입력 파일: data/user_chat_assacom.xlsx (2.3 MB)
  - 출력 경로: results/assacom
  - 회사명: assacom
  - 샘플 크기: 1000
  - 태깅 방식: agent (Solar-pro)

✅ 환경 검증:
  - API 키 설정됨
  - Python 의존성 설치됨
  - 출력 디렉토리 생성됨
```

### 2. Execute Clustering and Tagging Pipeline

Run the Python clustering script with Solar-pro agent tagging and monitor execution.

**Constraints:**
- You MUST change to sop-agent directory: `cd sop-agent`
- You MUST execute clustering script with agent tagging (Solar-pro unified analysis):
  ```bash
  python3 scripts/pipeline.py \
    --input {input_file} \
    --output {output_dir}/01_clustering \
    --prefix {company} \
    --sample {sample_size} \
    --tagging-mode agent \
    --k {k} \
    --umap
  ```
- You MUST capture and display all output from the script
- You MUST detect and report errors immediately if script fails
- You MUST NOT proceed to next step if clustering fails
- You SHOULD display progress indicators (loading data, generating embeddings, clustering)
- You SHOULD estimate time remaining based on sample size
- You MAY offer to retry with different parameters if clustering fails


**Expected Outputs:**
```
Customer Support Chat Clustering Pipeline
=====================================================

[1/6] Loading data...
✓ Loaded 1,000 records

[2/6] Enhancing text...
✓ Text enhancement complete (93.0% summary, 3.2% first_message, 3.0% combined)

[3/6] Generating embeddings...
✓ Generated 1,000 embeddings in 60 seconds (or: Loaded from cache in 2 seconds)

[4/6] Performing clustering...
K=8: Silhouette=0.051
K=10: Silhouette=0.056
K=15: Silhouette=0.060
K=20: Silhouette=0.064
✓ Optimal K=20, Silhouette=0.064

[5/6] Tagging clusters (Solar-pro agent mode)...
✓ Tagging complete in 8 seconds

[6/6] Saving results...
✓ Results saved:
  - results/company/01_clustering/company_clustered.xlsx (with tags)
  - results/company/01_clustering/company_tags.xlsx

📊 Category Distribution:
  - 구매 상담: 214건 (21.4%)
  - 배송/조립: 211건 (21.1%)
  - AS/배송: 200건 (20.0%)
  - 기술 지원: 192건 (19.2%)
  ...

"기타" rate: 7%
```

### 3. Verify Results

Validate output files with tags and check data quality.

**Constraints:**
- You MUST verify both output files exist:
  - `test -f {output_dir}/01_clustering/{company}_clustered.xlsx`
  - `test -f {output_dir}/01_clustering/{company}_tags.xlsx`
- You MUST check file sizes are non-zero: `ls -lh {output_dir}/01_clustering/{company}_*.xlsx`
- You MUST read and display cluster distribution from tags file
- You MUST check for data quality issues:
  - Empty cluster labels
  - High "기타" (Other) category rate (>20%)
  - Severely imbalanced clusters (one cluster >50%)
- You SHOULD display top 5 clusters with labels and sizes
- You SHOULD flag any quality concerns
- You MAY suggest re-running with different parameters if quality is poor


**Quality Checklist:**
- [ ] Both Excel files generated successfully
- [ ] Cluster distribution is balanced (no single cluster >50%)
- [ ] Silhouette score is reasonable (>0.05)
- [ ] Category labels are meaningful (not "클러스터 X")
- [ ] "기타" rate is acceptable (<20%)

**Expected Outputs:**
```
✅ Output files validated:
  - 01_clustering/company_clustered.xlsx (1.2 MB, 1,645 rows)
  - 01_clustering/company_tags.xlsx (12 KB, 10 rows)

📊 Cluster Distribution:
  1. AS_접수 (A/S): 120건 (7.3%)
  2. 배송_조회 (배송): 96건 (5.8%)
  3. 제품_문의 (일반_상담): 92건 (5.6%)
  ...

✓ Quality checks passed
⚠️  Note: Detected 117 empty records in Cluster 3
```

### 4. Generate Analysis Report

Create comprehensive analysis report for Stage 2 guidance.

**Constraints:**
- You MUST read both output Excel files to gather statistics
- You MUST create analysis report at: `{output_dir}/01_clustering/analysis_report.md`
- You MUST include the following sections:
  - Executive Summary (3-5 sentences in the detected language)
  - Cluster Distribution (category breakdown, size statistics)
  - Top 10 Customer Issues (with keywords and response strategies)
  - Quality Metrics (silhouette score, text enhancement rate)
  - Insights & Recommendations (operational insights, automation opportunities)
  - Next Steps for Stage 2 (focus areas, priorities)
- You MUST extract 3-5 sample messages per top cluster
- You MUST write all analysis content in the detected language (except section titles)
- You SHOULD calculate useful metrics (average cluster size, category concentration)
- You SHOULD identify patterns and trends in the data
- You MAY include visualization suggestions


**Report Structure:**
```markdown
# Customer Support Clustering Analysis Report: {Company}

## Executive Summary
[3-5 sentences in the detected language summarizing key findings]

## 1. Cluster Distribution
### 1.1 Category Breakdown
[Table with categories, counts, percentages]

### 1.2 Cluster Size Distribution
- Largest: {max_size}건
- Smallest: {min_size}건
- Average: {avg_size}건
- Median: {median_size}건

## 2. Top Customer Issues (Top 10)
[For each cluster: label, count, keywords, typical question, response strategy]

## 3. Quality Metrics
- Silhouette Score: {score}
- Text Enhancement Success: {rate}%
- Cluster Balance: {metric}

## 4. Insights & Recommendations
### 4.1 Operational Insights
- High-Priority Issues
- Automation Opportunities
- Training Needs

### 4.2 Customer Support Strategy
- Response Templates needed
- Escalation Rules
- Self-Service opportunities

## 5. Next Steps for Stage 2
[Focus areas, extraction priorities, data quality checks]

## Appendix
### A. Cluster Summary Table
[Complete cluster listing]

### B. Sample Messages
[Representative examples per cluster]

## Metadata
- Generated: {timestamp}
- Total Records: {N}
- Clusters (K): {K}
- Silhouette Score: {score}
```

**Expected Outputs:**
```
✅ Analysis report generated:
   results/company/01_clustering/analysis_report.md (15 KB)

📋 Report highlights:
  - 10 clusters identified
  - Top issue: A/S 접수 (7.3%)
  - 3 automation opportunities identified
  - Stage 2 focus: Top 8 clusters (covers 85% of data)
```



### 5. Review and Communicate Results

Present results and confirm readiness for Stage 2.

**Constraints:**
- You MUST display summary of key findings
- You MUST provide file paths for all outputs
- You MUST highlight any quality concerns or special cases
- You MUST confirm whether to proceed to Stage 2
- You SHOULD suggest next actions based on results
- You MAY offer to re-run clustering with adjusted parameters if quality is suboptimal


**Communication Template:**
```
✅ Stage 1 Clustering Complete: {Company}

📊 Results Summary:
  - Total Records: {N:,}
  - Clusters: {K}
  - Silhouette Score: {score:.3f}
  - Top Category: {category} ({percentage}%)

📁 Output Files:
  1. Clustered Data: {output_dir}/01_clustering/{company}_clustered.xlsx
  2. Cluster Tags: {output_dir}/01_clustering/{company}_tags.xlsx
  3. Analysis Report: {output_dir}/01_clustering/analysis_report.md

💡 Key Findings:
  - {finding_1}
  - {finding_2}
  - {finding_3}

🔄 Next Steps:
  - Review analysis report for detailed insights
  - Proceed to Stage 2: /stage2-extraction
  - Or re-run with adjusted parameters if needed
```

## Examples

### Example 1: Default Run (1000 records)

**Input Parameters:**
```
input_file: data/raw/user_chat_assacom.xlsx
output_dir: results/assacom
company: assacom
sample_size: 1000
tagging_mode: agent
k: auto
```

**Results:**
- 20 clusters identified
- Silhouette: 0.064
- Top issue: AS문의 (33.8%)
- Time: ~2-3 minutes

### Example 2: Full Dataset Run

**Input Parameters:**
```
input_file: data/raw/raw data_meliens.xlsx
output_dir: results/meliens
company: meliens
sample_size: all
tagging_mode: agent
k: auto
```

**Results:**
- 10 clusters, 1,645 records
- Silhouette: 0.132
- A/S inquiries dominate (48%)
- Time: ~10-15 minutes

## Troubleshooting

### Issue: Missing API Key

**Symptom:** Script fails with "UPSTAGE_API_KEY not found"

**Solution:**
- You MUST check if .env file exists: `test -f .env`
- You MUST verify API key is set: `grep UPSTAGE_API_KEY .env`
- You MUST suggest running `/request-api-key` skill to automatically request the key via Channel.io
- You MUST wait for user to complete `/request-api-key` flow before retrying clustering

### Issue: Python Dependencies Missing

**Symptom:** ImportError or ModuleNotFoundError

**Solution:**
- You MUST check requirements: `pip3 show pandas numpy scikit-learn`
- You MUST install missing packages: `pip3 install -r requirements.txt --user`
- You MUST verify installation succeeded
- You MUST retry clustering after installation

### Issue: Low Clustering Quality

**Symptom:** High "기타" rate (>20%) or poor silhouette score (<0.03)

**Solution:**
- You SHOULD suggest trying different tagging_mode (api → agent → skip+manual)
- You MAY suggest adjusting k parameter (try k_range values)
- You MAY recommend using `/tag-clusters-manual` for production quality
- You SHOULD document quality concerns in analysis report

### Issue: Clustering Takes Too Long

**Symptom:** Script runs >10 minutes on sample data

**Solution:**
- You MUST check if embeddings are cached (should be fast on re-runs)
- You SHOULD suggest reducing sample_size for initial testing
- You MAY check system resources (memory, CPU)
- You SHOULD display progress to reassure user

## Related Documentation

- **Detailed Clustering Guide**: `../docs/clustering-guide.md` - Algorithm details, troubleshooting, and optimization
- **Next Stage**: `/stage2-extraction` - Pattern extraction workflow
- **Full Pipeline**: `/userchat-to-sop-pipeline` - End-to-end orchestration

## Notes

### Execution Environment

This SOP requires:
- Python 3.9+ with dependencies (pandas, numpy, scikit-learn, openpyxl, openai, tqdm, python-dotenv)
- Upstage Solar API key (for embeddings and optional tagging)
- Excel input file with specific sheet structure
- File system access for reading/writing

### Output for Stage 2

The analysis report (`analysis_report.md`) is critical for Stage 2:
- Provides context about industry and customer needs
- Prioritizes clusters for pattern extraction
- Identifies automation opportunities
- Flags data quality issues

### Performance Expectations

- 1,000 records: ~2-3 minutes (< 1 min embedding, 1 min clustering, 1 min report)
- 10,000 records: ~10-15 minutes
- Embedding cache makes re-runs much faster (< 1 min)

### Cost Estimates

- Upstage Solar embeddings: $0.05 per 1000 records
- Agent tagging: $0.02 per 1000 records
- Total: ~$0.07 per 1000 records
