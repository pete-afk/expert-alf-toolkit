# Userchat-to-SOP Complete Pipeline

## Overview
This SOP orchestrates the complete end-to-end pipeline for transforming Excel customer support data into a production-ready Agent SOP document. It integrates all three stages: Clustering (Python), Pattern Extraction (LLM), and SOP Generation (LLM).

**Language:** All user interactions MUST be conducted in Korean (한국어). Questions, confirmations, and outputs should be in Korean unless the user explicitly requests English.

**Pipeline Flow:**
```
Excel Input (고객 상담 데이터)
    ↓
Stage 1: Clustering (Python) [5-10 min]
    → clustered_data.xlsx, cluster_tags.xlsx, analysis_report.md
    ↓
Stage 2: Pattern Extraction (LLM) [10-30 min]
    → patterns.json, faq.json, response_strategies.json, keywords.json
    ↓
Stage 3: SOP Generation (LLM) [20-30 min]
    → {company}_support.sop.md, metadata.json
    ↓
Output: Ready-to-deploy Agent SOP
```

**Total Time**: 35-70 minutes (depends on data size and extraction depth)

## Parameters

### Required
- **input_file**: Path to Excel file with customer support chat data
  - Example: `data/raw/user_chat_meliens.xlsx`
  - Must have "UserChat data" and "Message data" sheets

- **company**: Company name
  - Example: "Meliens", "Assacom", "Usimsa"
  - Used throughout all stages for context

- **output_base_dir**: Base output directory
  - Example: `results/meliens`
  - Structure: `{output_base_dir}/{01_clustering,02_extraction,03_sop}/`

### Optional
- **sample_size** (default: 1000): Data sampling for Stage 1
  - 1000: Standard analysis (recommended default)
  - `"all"`: Full dataset (only if explicitly needed)

- **tagging_mode** (default: "agent"): Clustering tagging method (Stage 1)
  - `"agent"`: Fast unified tagging (5-15 sec, industry-adaptive, recommended)
  - `"api"`: Independent tagging (30 sec, hardcoded categories)

- **k** (default: "auto"): Number of clusters (Stage 1)
  - `"auto"`: Automatic optimal K selection
  - Integer: Fixed K value

- **extraction_depth** (default: "standard"): Pattern extraction detail (Stage 2)
  - `"quick"`: Basic patterns only
  - `"standard"`: Patterns + FAQ + strategies
  - `"deep"`: Full analysis with examples

- **sop_detail_level** (default: "standard"): SOP detail level (Stage 3)
  - `"concise"`: Minimal SOP (~500 lines)
  - `"standard"`: Balanced (~1000 lines)
  - `"comprehensive"`: Full detail (~2000 lines)

- **auto_proceed** (default: false): Automatic stage progression
  - `true`: Auto-proceed through stages without manual review
  - `false`: Pause after each stage for review

## Steps

### 1. Initialize Pipeline

Set up directory structure and validate inputs.

**Actions:**
- Verify input file exists and has correct format
- Create output directory structure: `{output_base_dir}/{01_clustering,02_extraction,03_sop}/`
- Validate Python clustering package is installed
- Print pipeline configuration
- Prompt user to confirm (if `auto_proceed=false`)

**Expected Output:**
```
✅ Pipeline initialized
  - Output directories created
  - Python package validated
  - Configuration confirmed

Ready to start Stage 1 (Clustering)...
```

### 2. Execute Stage 1: Clustering

Run Python clustering pipeline to analyze and cluster customer data.

**Documentation**: See [stage1-clustering.sop.md](stage1-clustering.sop.md)

**Execution:**
```bash
clustering-userchat \
  --input "$input_file" \
  --output "$output_base_dir/01_clustering" \
  --prefix "$company" \
  --sample "$sample_size" \
  --tagging-mode "$tagging_mode" \
  --k "$k"
```

**Outputs:**
- `{company}_clustered.xlsx` - Full dataset with cluster assignments
- `{company}_tags.xlsx` - Cluster summary
- `analysis_report.md` - Comprehensive analysis for Stage 2

**Quality Checks:**
- [ ] Clustering completed successfully
- [ ] Analysis report generated and readable
- [ ] Cluster distribution is balanced (no single cluster >50%)
- [ ] Silhouette score is reasonable (>0.05)
- [ ] Category labels are meaningful
- [ ] No critical data quality issues

**Pause for Review (if auto_proceed=false):**
```bash
echo "Review analysis report: $output_base_dir/01_clustering/analysis_report.md"
read -p "Proceed to Stage 2? (y/n) "
```

### 3. Execute Stage 2: Pattern Extraction

Use LLM to extract patterns, FAQs, and response strategies from clusters.

**Documentation**: See [stage2-extraction.sop.md](stage2-extraction.sop.md)

**Execution:**
```bash
# In Claude Code, execute:
/stage2-extraction

# With parameters:
# - clustering_output_dir: $output_base_dir/01_clustering
# - company: $company
# - extraction_depth: $extraction_depth
```

**Inputs:**
- Stage 1 outputs: `clustered_data.xlsx`, `tags.xlsx`, `analysis_report.md`

**Outputs:**
- `patterns.json` - Extracted patterns per cluster
- `faq.json` - FAQ pairs for common inquiries
- `response_strategies.json` - Response strategies and escalation rules
- `keywords.json` - Keyword taxonomy
- `extraction_summary.md` - Summary and recommendations

**Expected Duration:**
- Quick: ~10 minutes
- Standard: ~15-20 minutes
- Deep: ~30-40 minutes

**Quality Checks:**
- [ ] All JSON files generated and valid
- [ ] Patterns extracted for top 10 clusters
- [ ] FAQ pairs are specific and actionable
- [ ] Response strategies include escalation rules
- [ ] Keyword taxonomy is comprehensive
- [ ] Extraction summary highlights automation opportunities

**Pause for Review (if auto_proceed=false):**
```bash
echo "Review extraction summary: $output_base_dir/02_extraction/extraction_summary.md"
read -p "Proceed to Stage 3? (y/n) "
```

### 4. Execute Stage 3: SOP Generation

Use LLM to generate final Agent SOP document from extracted patterns.

**Documentation**: See [stage3-sop-generation.sop.md](stage3-sop-generation.sop.md)

**Execution:**
```bash
# In Claude Code, execute:
/stage3-sop-generation

# With parameters:
# - extraction_output_dir: $output_base_dir/02_extraction
# - company: $company
# - sop_title: "${company} Customer Support Assistant"
# - detail_level: $sop_detail_level
```

**Inputs:**
- Stage 2 outputs: `patterns.json`, `faq.json`, `response_strategies.json`, `keywords.json`

**Outputs:**
- `{company}_support.sop.md` - Complete Agent SOP document
- `metadata.json` - SOP metadata

**Expected Duration:**
- Concise: ~15 minutes
- Standard: ~20-25 minutes
- Comprehensive: ~30-40 minutes

**Quality Checks:**
- [ ] `{company}_support.sop.md` generated
- [ ] All required sections present (Overview, Parameters, Steps, Examples)
- [ ] RFC 2119 keywords used correctly
- [ ] Steps reference extracted patterns and FAQs
- [ ] Examples are concrete and realistic
- [ ] Troubleshooting section addresses common issues
- [ ] Korean text is natural and professional
- [ ] `metadata.json` is complete and accurate

### 5. Validate Complete Pipeline

Perform final validation of all outputs.

**Actions:**
- Verify all output files exist
- Validate file sizes are reasonable (not empty)
- Check JSON files are valid JSON
- Verify markdown files render correctly
- Generate pipeline summary report

**Files to Check:**
```
$output_base_dir/
├── 01_clustering/
│   ├── {company}_clustered.xlsx
│   ├── {company}_tags.xlsx
│   └── analysis_report.md
├── 02_extraction/
│   ├── patterns.json
│   ├── faq.json
│   ├── response_strategies.json
│   ├── keywords.json
│   └── extraction_summary.md
├── 03_sop/
│   ├── {company}_support.sop.md
│   └── metadata.json
└── pipeline_summary.md (generated in next step)
```

**Expected Output:**
```
✅ All output files validated
  - Stage 1: 3 files
  - Stage 2: 5 files
  - Stage 3: 2 files
Total: 10 files, pipeline complete
```

### 6. Generate Pipeline Summary

Create comprehensive summary of pipeline execution and results.

**Summary Contents:**
- Execution information (date, duration, parameters)
- Stage 1 statistics (records, clusters, silhouette score, top category)
- Stage 2 statistics (patterns, FAQs, automation opportunities)
- Stage 3 statistics (SOP size, steps, examples)
- Key insights from all stages
- Next steps for deployment
- Quality metrics

**Output:** `{output_base_dir}/pipeline_summary.md`

**Template:**
```markdown
# Userchat-to-SOP Pipeline Summary

## Execution Information
- Company: {company}
- Execution Date: {timestamp}
- Total Duration: {duration}

## Stage Results
### Stage 1: Clustering
- Records: {N}, Clusters: {K}, Score: {score}

### Stage 2: Pattern Extraction
- Patterns: {P}, FAQs: {F}, Strategies: {S}

### Stage 3: SOP Generation
- SOP Lines: {L}, Steps: {N}, Examples: {E}

## Key Insights
1. {insight_1}
2. {insight_2}
3. {insight_3}

## Next Steps
1. Review SOP: {sop_path}
2. Test with sample inquiries
3. Deploy to Claude Skills
4. Monitor metrics
```

### 7. Communicate Results

Present pipeline results to stakeholders.

**Communication Template:**
```
✅ Userchat-to-SOP Pipeline Complete: {Company}

📊 Pipeline Results
  - Total Records: {N:,}
  - Clusters: {K}
  - Patterns: {P}
  - FAQ Pairs: {F}
  - SOP Lines: {L}

💡 Key Insights
  1. {insight from analysis report}
  2. {insight from extraction}
  3. {automation opportunity}

📁 Output Files
  - Analysis Report: {path}/01_clustering/analysis_report.md
  - Extraction Summary: {path}/02_extraction/extraction_summary.md
  - Final SOP: {path}/03_sop/{company}_support.sop.md

🚀 Next Steps
  1. Review analysis report and SOP
  2. Test SOP with sample inquiries
  3. Deploy via Claude Skills
  4. Monitor key metrics
```

## Examples

### Example 1: Production Run (Meliens, Full Dataset)

**Scenario**: Complete pipeline for production SOP

**Parameters:**
```bash
input_file="data/raw/raw data_meliens.xlsx"
company="Meliens"
output_base_dir="results/meliens"
sample_size="all"  # 1,645 records
tagging_mode="api"
k="auto"
extraction_depth="standard"
sop_detail_level="standard"
auto_proceed=false  # Pause for review after each stage
```

**Timeline:**
- Stage 1 (Clustering): 6 minutes
- Review & Approve: 3 minutes
- Stage 2 (Extraction): 20 minutes
- Review & Approve: 5 minutes
- Stage 3 (SOP Generation): 25 minutes
- Validation & Summary: 2 minutes
- **Total**: 61 minutes

**Results:**
- 10 clusters, 37 patterns, 52 FAQ pairs
- 1,200-line Agent SOP
- Key insight: A/S inquiries dominate (48%)

### Example 2: Quick Test (Assacom, Sample)

**Scenario**: Quick validation before full run

**Parameters:**
```bash
input_file="data/raw/user_chat_assacom.xlsx"
company="Assacom"
output_base_dir="results/assacom_test"
sample_size=1000
tagging_mode="api"
k=20
extraction_depth="quick"
sop_detail_level="concise"
auto_proceed=true  # Automatic, no pauses
```

**Timeline:**
- Stage 1: 5 minutes
- Stage 2: 10 minutes
- Stage 3: 15 minutes
- **Total**: 30 minutes

**Results:**
- 20 clusters, 30 patterns
- 600-line concise SOP

## Troubleshooting

### Issue: Stage 1 Clustering Fails

**Solution:**
1. Verify Python package: `pip install -r requirements.txt`
2. Check input file format (required sheets present)
3. Verify environment variables (UPSTAGE_API_KEY)
4. Run Stage 1 independently: `/stage1-clustering`
5. Check logs for specific error messages

### Issue: Stage 2 Takes Too Long

**Solution:**
1. Reduce `extraction_depth` to "quick" or "standard"
2. Use `focus_clusters="top_10"` to analyze only top clusters
3. Consider re-running Stage 1 with lower K value

### Issue: Generated SOP is Too Generic

**Solution:**
1. Review Stage 2 extraction quality
2. Re-run Stage 2 with `extraction_depth="deep"`
3. Manually enhance Stage 3 output with company-specific details
4. Include more sample messages in extraction

### Issue: Pipeline Paused, Need to Resume

**Solution:**
Each stage is independent and can be resumed:

```bash
# Resume from Stage 2
/stage2-extraction
# (provide clustering_output_dir parameter)

# Resume from Stage 3
/stage3-sop-generation
# (provide extraction_output_dir parameter)
```

## Related Documentation

- **Stage 1 Clustering**: [stage1-clustering.sop.md](stage1-clustering.sop.md)
- **Stage 2 Extraction**: [stage2-extraction.sop.md](stage2-extraction.sop.md)
- **Stage 3 SOP Generation**: [stage3-sop-generation.sop.md](stage3-sop-generation.sop.md)
- **Detailed Clustering Guide**: `../docs/clustering-guide.md`

## Notes

### Why Hybrid Approach (Python + LLM)?

**Python (Stage 1):**
- Embedding generation: Computational, benefits from caching
- K-Means clustering: Statistical algorithm, fast and reliable
- Results in 5-10 minutes (vs 30+ min if done by LLM)

**LLM (Stage 2, 3):**
- Pattern extraction: Requires language understanding
- FAQ generation: Natural language composition
- SOP writing: Structured document creation with domain reasoning

**Hybrid = Best of Both Worlds**

### Pipeline Customization

Choose configuration based on use case:

**Quick Prototype** (30 min):
- sample_size: 1000
- extraction_depth: "quick"
- sop_detail_level: "concise"

**Standard Production** (60 min):
- sample_size: "all"
- extraction_depth: "standard"
- sop_detail_level: "standard"

**Comprehensive Analysis** (90 min):
- sample_size: "all"
- extraction_depth: "deep"
- sop_detail_level: "comprehensive"

### Cost Estimates (per 1000 records)

**Stage 1 (Upstage Solar):**
- Embeddings: $0.05
- Tagging: $0.01-0.02

**Stage 2 & 3 (Claude Sonnet 4.5):**
- Varies by depth
- Typical: $0.50-2.00 per full pipeline run

**Total**: ~$0.60-2.50 per 1000 records

### Monitoring & Iteration

After SOP deployment:

1. **Week 1-2**: Pilot with small team
2. **Week 3-4**: Refine based on feedback
3. **Month 2**: Full rollout, track metrics
4. **Quarterly**: Re-run pipeline with new data

**Metrics to Track:**
- First-contact resolution rate
- Average response time
- Escalation rate
- Customer satisfaction score
- Agent feedback on SOP usability

---

**This is an orchestration SOP**. For detailed implementation of each stage, refer to the stage-specific SOPs linked above.
