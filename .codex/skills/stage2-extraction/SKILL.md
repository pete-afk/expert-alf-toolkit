---
name: stage2-extraction
description: Extract patterns, FAQs, and SOP topic map from clustered customer support data by reading full conversation transcripts. Stage 2 of the Userchat-to-SOP pipeline. **Language:** Auto-detects Korean (한국어) or Japanese (日本語) from user input.
---

# Stage 2: Pattern & FAQ Extraction

## Overview

Extract patterns, FAQs, and define SOP topics by reading **full conversation transcripts** from Stage 1 clustered data.

**Language:** Detect the language from the user's first message and respond in that language throughout. Support Korean (한국어) and Japanese (日本語). Default to Korean if language is unclear.

**Input**: Stage 1 results (`{prefix}_clustered.xlsx`, `{prefix}_tags.xlsx`, `{prefix}_messages.csv`, `analysis_report.md`)
**Output**: `patterns.json` (with `sop_topic_map`), `faq.json`, `keywords.json`, `patterns_enriched.json`

**Core Principle:** Read actual conversation turns, not summaries. Summaries lose customer tone, agent response patterns, and escalation moments.

## Parameters

### Required
- **clustering_output_dir**: Directory with Stage 1 results (e.g., `results/kamoa/01_clustering`)
- **company**: Company name (e.g., "kamoa")

### Optional
- **min_total_samples** (default: 500): Minimum total conversation samples across all clusters
  - Formula: `n_samples_per_cluster = max(25, ceil(min_total_samples / K))`
- **focus_clusters** (default: "all"): `"all"`, `"top_10"`, or list `"0,2,5,7"`

## Steps

### 1. Load Stage 1 Results and Run Enrichment

Read tags and analysis report, then run enrichment to get full conversation transcripts.

**Actions:**
1. Read `{prefix}_tags.xlsx` and `analysis_report.md`
2. Calculate `n_samples = max(25, ceil(500 / K))`
3. Create bootstrap `patterns.json` from tags, then run enrichment:

```bash
mkdir -p results/{company}/02_extraction

python3 -c "
import pandas as pd, json, math
tags = pd.read_excel('results/{company}/01_clustering/{prefix}_tags.xlsx')
K = len(tags)
n_samples = max(25, math.ceil(500 / K))
print(f'K={K}, n_samples_per_cluster={n_samples}, total={K * n_samples}')
data = {'metadata': {'company': '{company}', 'bootstrap': True}, 'clusters': []}
for _, r in tags.iterrows():
    data['clusters'].append({'cluster_id': int(r['cluster_id']), 'label': r['label'], 'category': r['category'], 'cluster_size': int(r['cluster_size'])})
with open('results/{company}/02_extraction/patterns.json', 'w') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
"

python3 scripts/enrich_patterns.py \
  --patterns results/{company}/02_extraction/patterns.json \
  --messages results/{company}/01_clustering/{prefix}_messages.csv \
  --output results/{company}/02_extraction/conversations_by_cluster.json \
  --n-samples {n_samples}
```

**Fallback:** If enrichment fails, fall back to `enhanced_text` from `clustered.xlsx` and mark `"data_source": "summary_fallback"`.

---

### 2. Analyze Conversations per Cluster

For each cluster, read full conversation transcripts and extract:

1. **Patterns** (3-8 per cluster): name, type (`정보_요청`/`문제_신고`/`프로세스_문의`/`불만_제기`), verbatim customer phrases, frequency
2. **HT vs TS**: HT = information/guidance, TS = problem resolution
3. **Mixed topics**: Flag if conversations cover multiple distinct topics
4. **Company tone**: Greeting style, response structure, closing from agent messages

**Constraints:**
- MUST read actual `turns` from enrichment output, NOT `enhanced_text`
- MUST process clusters sequentially in main agent (no subagents — causes hanging)
- MUST extract customer phrases **verbatim** from conversations
- MUST flag mixed clusters where >30% of conversations don't match the label

---

### 3. Define SOP Topics (Re-classification)

After analyzing ALL clusters, define SOP topics independent of cluster boundaries.

**Handle these cases:**
- **Mixed cluster** → Split into 2+ topics with conversation IDs assigned per topic
- **Duplicate clusters** → Merge into one topic
- **Mislabeled cluster** → Use actual content
- **Noise cluster** → Absorb into "초기 응대" or exclude

**Output `sop_topic_map`** (Stage 3 follows this exactly):
```json
{
  "sop_topic_map": {
    "topics": [
      {
        "topic_id": "TS_HARDWARE_AS",
        "title": "A/S 접수 및 하드웨어 불량 처리",
        "type": "TS",
        "journey_stage": "사용 중",
        "source_clusters": [
          {"cluster_id": 0, "portion": "partial", "conversation_ids": [1,3,5], "reason": "하드웨어 관련만"},
          {"cluster_id": 6, "portion": "full"}
        ],
        "estimated_records": 500,
        "key_patterns": ["블루스크린", "택배_AS_접수"]
      }
    ],
    "merge_log": [...],
    "label_corrections": [...]
  }
}
```

**Constraints:**
- MUST aim for 8-15 SOP topics
- MUST validate: all clusters mapped, total estimated records ≈ input total
- SHOULD organize by customer journey (구매 전 → 사용 중 → AS → 기타)

---

### 4. Generate FAQ Pairs and Keywords

**FAQ** (3-5 per SOP topic):
- Questions MUST use actual customer language from conversations (verbatim)
- Answers MUST follow company's agent tone and include specific steps/contact info observed in conversations

**Keywords**: Hierarchical taxonomy (category → subcategory → keywords) from actual conversations, including synonyms and common typos.

---

### 5. Save Results and Run Final Enrichment

Save to `results/{company}/02_extraction/`:
1. `patterns.json` — patterns + `sop_topic_map`
2. `faq.json` — FAQ pairs by SOP topic
3. `keywords.json` — keyword taxonomy
4. `extraction_summary.md` — human-readable summary

Then run final enrichment on the completed patterns:
```bash
python3 scripts/enrich_patterns.py \
  --patterns results/{company}/02_extraction/patterns.json \
  --messages results/{company}/01_clustering/{prefix}_messages.csv \
  --output results/{company}/02_extraction/patterns_enriched.json \
  --n-samples {n_samples}
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Enrichment fails (messages.csv missing) | Fall back to `enhanced_text` from `clustered.xlsx`, mark `"data_source": "summary_fallback"` |
| Patterns too generic | Re-read conversations, copy-paste exact customer phrases |
| Too many topics (>15) | Merge related topics (e.g., "SSD 인식" + "HDD 연결" → "저장장치 문제") |

## Notes

- **No subagents** — process sequentially in main agent for stability
- **min_total_samples=500** ensures broader coverage than previous default of 300
- Stage 3 MUST follow the `sop_topic_map` defined here — it does not redefine topics
