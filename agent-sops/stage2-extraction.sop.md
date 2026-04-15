# Stage 2: Pattern & FAQ Extraction

## Overview
This SOP guides the **real sample-based LLM extraction** of patterns, FAQs, and response strategies from clustered customer support data. This is **Stage 2** of the Userchat-to-SOP pipeline, combining Python sample extraction with AI agent natural language analysis.

**Language:** All user interactions MUST be conducted in Korean (한국어). Questions, confirmations, and outputs should be in Korean unless the user explicitly requests English.

**Stage Flow:**
- **Input**: Stage 1 clustering results (Excel files + analysis report)
- **Process**:
  1. Python extracts 20 random samples per cluster
  2. LLM reads actual samples and identifies patterns
  3. LLM extracts real customer expressions (NOT generic phrases!)
  4. **LLM classifies HT vs TS based on samples** (NEW!)
- **Output**: Structured JSON files with patterns, keywords, FAQ pairs, **HT/TS classification**

**Key Capabilities:**
- Extract common inquiry patterns from **actual customer messages**
- Generate FAQ pairs using **real customer expressions**
- Identify company-specific tone and brand messaging
- Discover unexpected patterns and edge cases
- Build knowledge base with verified accuracy

**Critical Philosophy:**
- ❌ DO NOT guess or infer patterns from cluster labels
- ✅ DO read actual samples and extract verbatim customer expressions
- ✅ DO measure frequency by counting occurrences in samples
- ✅ DO preserve company tone from actual responses

## Parameters

### Required
- **clustering_output_dir**: Directory containing Stage 1 results
  - Example: `results/meliens`
  - Must contain: `{prefix}_clustered.xlsx`, `{prefix}_tags.xlsx`, `analysis_report.md`

- **company**: Company name for context
  - Example: "Meliens", "Assacom", "Usimsa"
  - Used to understand industry and customer domain

### Optional
- **focus_clusters** (default: "all"): Which clusters to prioritize
  - `"all"`: Extract from all clusters
  - `"top_10"`: Extract from top 10 largest clusters
  - List of IDs: e.g., `"0,2,5,7"` for specific clusters

- **n_samples_per_cluster** (default: 20): Number of samples to analyze per cluster
  - Example: `10`, `20`, `30`, `50`
  - Recommended: 20 (충분한 패턴 파악 + 합리적인 실행 시간)
  - 더 많은 샘플이 필요하면 이 값을 조정하세요
  - Enrichment (patterns_enriched.json) is always generated

- **output_format** (default: "json"): Output file format
  - `"json"`: Structured JSON (recommended for Stage 3)
  - `"markdown"`: Human-readable markdown
  - `"both"`: Generate both formats

## Steps

### 1. Load and Review Stage 1 Results

Read the clustering results to understand the data structure and context.

**Constraints:**
- You MUST read all three files from Stage 1:
  1. `{prefix}_clustered.xlsx`: Full data with cluster assignments
  2. `{prefix}_tags.xlsx`: Cluster summary
  3. `analysis_report.md`: Analysis insights
- You MUST verify that all clusters have meaningful labels (not "클러스터 X")
- You SHOULD prioritize clusters identified in "Next Steps" section of analysis report
- You MAY skip system/error clusters (e.g., "데이터_오류", "내부_티켓")
- You MUST understand the company domain and industry before extraction

**Reading Process:**
```bash
# In Claude Code
Read results/meliens/meliens_clustered.xlsx
Read results/meliens/meliens_tags.xlsx
Read results/meliens/analysis_report.md
```

**What to Extract:**
1. **From tags.xlsx:**
   - Cluster ID, label, category, keywords, count
   - Rank clusters by count (largest first)

2. **From clustered.xlsx:**
   - Sample messages per cluster (10-20 samples)
   - Distribution of text lengths
   - Common phrases and terminology

3. **From analysis_report.md:**
   - Top customer issues
   - Recommended focus areas
   - Industry-specific context
   - Quality concerns or special cases

**Expected Understanding:**
```
Company: Meliens (Electronics - home appliances)
Total Clusters: 10
Focus Clusters: [2, 0, 1, 9, 6] (Top 5 by size)
Top Categories: A/S (48%), 일반_상담 (19%), 배송 (12%)
Key Insight: A/S inquiries dominate, need detailed response templates
```

### 2. Extract Patterns per Cluster

For each cluster, identify common patterns, inquiry types, and response needs by analyzing **actual customer messages**.

**Constraints:**
- You MUST analyze 20 sample messages per cluster using Python
- You MUST identify 3-8 distinct patterns within each cluster
- You MUST extract actual customer phrases from samples (DO NOT paraphrase or guess!)
- You MUST NOT infer or assume patterns based on cluster labels alone
- You MUST categorize patterns by: `정보_요청`, `문제_신고`, `프로세스_문의`, `불만_제기`
- You SHOULD measure frequency by counting pattern occurrences in 20 samples
- You MAY group similar patterns together
- You MUST output patterns in Korean (original customer language)

**Critical Requirement:**
❌ **DO NOT** create patterns based on general business knowledge or assumptions
✅ **DO** read actual sample messages and extract real customer expressions

**Sample Extraction (Required First Step):**

Use Python to extract 20 random samples per cluster:

```python
# Extract samples for each cluster
import pandas as pd

df = pd.read_excel('{clustering_output_dir}/{prefix}_clustered.xlsx')

for cluster_id in target_clusters:
    cluster_data = df[df['cluster_id'] == cluster_id]
    samples = cluster_data.sample(n=20, random_state=42)

    print(f"\n=== Cluster {cluster_id} Samples ===")
    for i, (_, row) in enumerate(samples.iterrows(), 1):
        print(f"{i}. {row['enhanced_text'][:250]}")
```

**Pattern Analysis Framework:**

After reading samples, extract for each cluster:
1. **Pattern Name**: Short descriptive label (Korean)
2. **Pattern Type**: `정보_요청`, `문제_신고`, `프로세스_문의`, `불만_제기`
3. **Common Phrases**: 3-5 actual phrases from samples (verbatim!)
4. **Intent**: What the customer wants to achieve
5. **Frequency**: Measured from 20 samples (high: ≥30%, medium: 20-29%, low: <20%)
6. **Dialog Type**: Rosa 7가지 대화유형 중 하나 (아래 매핑 표 참고)
7. **SOP Type**: dialog_type에서 자동 도출 (`HT` or `TS`)

**Dialog Type 매핑 표:**

| dialog_type | sop_type | 처리 방식 | 예시 |
|-------------|----------|----------|------|
| `1.지식응답` | HT | RAG (FAQ 문서 검색) | "배송 기간이 얼마나 되나요?" |
| `2.정보조회` | TS | 코드 노드 (조회 API) | "내 주문 배송 언제 오나요?" |
| `3.단순실행` | TS | 코드 노드 (실행 API) | "재발송 해주세요" |
| `4.정책확인` | HT | RAG + 조건 분기 | "환불 정책이 어떻게 되나요?" |
| `5.조건부실행` | TS | 에이전트 + 코드 노드 | "파손됐는데 교환 가능한가요?" |
| `6.의도불명확` | - | 명확화 질문 | "문제가 있어요" |
| `7.상담사전환` | TS | 에스컬레이션 (해결율 0%) | "너무 화가 나요, 책임자 연결" |

**Example Analysis (Cluster 6: 견적/구매 상담 - Assacom):**

**Step 1: Read actual samples**
```
Sample 1: "하드디스크와 SATA SSD 추가 장착 가능..."
Sample 2: "고사양 게임에 적합한 PC 여부 확인..."
Sample 3: "전화 상담 요청..."
Sample 4: "SSD, RAM 미포함 주문 확인..."
...
Sample 20: ...
```

**Step 2: Extract patterns from actual samples**
```json
{
  "cluster_id": 6,
  "label": "견적/구매 상담",
  "category": "견적_구매",
  "patterns": [
    {
      "pattern_name": "부품_추가_변경_요청",
      "pattern_type": "프로세스_문의",
      "dialog_type": "3.단순실행",
      "sop_type": "TS",
      "common_phrases": [
        "하드디스크 추가 장착 가능",           ← Sample 1
        "SSD, RAM 추가하고 싶어요",          ← Sample 4
        "케이스 교체 요청",                  ← Sample 9
        "메인보드 변경 요청"                 ← Sample 9
      ],
      "intent": "기본 견적에 부품 추가 또는 변경 요청",
      "frequency": "high"  ← 20개 중 8개 = 40%
    },
    {
      "pattern_name": "용도별_PC_추천",
      "pattern_type": "정보_요청",
      "dialog_type": "1.지식응답",
      "sop_type": "HT",
      "common_phrases": [
        "고사양 게임에 적합한 PC",            ← Sample 2
        "윈도우+게이밍/그래픽작업용",        ← Sample 11
        "포토샵 작업용 PC"                  ← Sample 15
      ],
      "intent": "용도에 맞는 PC 사양 추천 요청",
      "frequency": "high"  ← 20개 중 6개 = 30%
    },
    {
      "pattern_name": "전화_상담_요청",
      "pattern_type": "프로세스_문의",
      "dialog_type": "7.상담사전환",
      "sop_type": "TS",
      "common_phrases": [
        "전화 상담 요청",                    ← Sample 3
        "전화 상담 가능 날짜"                ← Sample 3
      ],
      "intent": "채팅보다 전화 상담 선호",
      "frequency": "low"  ← 20개 중 3개 = 15%
    }
  ]
}
```

**Extraction Process (Updated):**

For each target cluster:
1. **Use Python to extract 20 random samples** (DO NOT read sequentially!)
   ```python
   samples = cluster_data.sample(n=20, random_state=42)
   ```
2. **Read ALL 20 samples** and print them for LLM analysis
3. **Identify patterns** by manually grouping similar messages
4. **Extract common phrases** from actual samples (copy-paste, do not rephrase!)
5. **Measure frequency** by counting: (pattern occurrences / 20) × 100%
6. **Classify pattern type** based on customer intent
7. **Document in JSON structure** with actual customer expressions

### 2.5. SOP 분리 결정 (dialog_type 분포 기반)

Step 2에서 각 패턴에 부여한 `dialog_type`과 `sop_type`을 집계하여, 이 클러스터가 **1개 SOP**으로 충분한지 **2개 SOP(HT + TS)으로 분리**해야 하는지 결정한다.

**Constraints:**
- You MUST count HT-type and TS-type patterns separately (6.의도불명확 제외)
- You MUST recommend split (`split: true`) if TS 패턴 비율 ≥ 25%
- You MUST recommend no split (`split: false`) if TS 패턴 비율 < 25%
- You MUST list which patterns belong to each SOP when split is recommended
- You SHOULD read `templates/HT_template.md` and `templates/TS_template.md` if uncertain about template structure
- You MAY override the 25% threshold with reasoning if the TS patterns are highly significant

**Split Decision Rule:**

```
전체 패턴 수 (의도불명확 제외) 중 TS 패턴 비율 계산

TS 비율 ≥ 25%  →  split: true  (HT SOP + TS SOP 각각 생성)
TS 비율 < 25%  →  split: false (단일 SOP, 소수 TS는 에스컬레이션 섹션으로 처리)
```

**SOP Type별 구조 참고:**

| sop_type | 구조 | 포함할 패턴 |
|----------|------|-----------|
| **HT** | 목적 → 주의사항 → **주제별 내용** → 톤앤매너 | 1.지식응답, 4.정책확인 |
| **TS** | 목적 → 주의사항 → **문제확인** → **케이스별 해결책** | 2.정보조회, 3.단순실행, 5.조건부실행, 7.상담사전환 |

**Output 형식:**

```json
{
  "sop_split_recommendation": {
    "split": true,
    "reasoning": "전체 5개 패턴 중 TS 패턴 3개(60%) — 분리 권장",
    "sops": [
      {
        "type": "HT",
        "suggested_title": "용도별_PC_추천_안내",
        "patterns": ["용도별_PC_추천", "제품_사양_문의"],
        "dialog_types": ["1.지식응답", "1.지식응답"],
        "coverage_ratio": "40%"
      },
      {
        "type": "TS",
        "suggested_title": "부품_추가변경_처리",
        "patterns": ["부품_추가_변경_요청", "전화_상담_요청", "주문_취소_요청"],
        "dialog_types": ["3.단순실행", "7.상담사전환", "5.조건부실행"],
        "coverage_ratio": "60%"
      }
    ]
  }
}
```

**No-split 예시:**

```json
{
  "sop_split_recommendation": {
    "split": false,
    "reasoning": "전체 4개 패턴 중 TS 패턴 1개(25% 미만) — 단일 HT SOP 권장. TS 패턴은 에스컬레이션 섹션으로 처리",
    "sops": [
      {
        "type": "HT",
        "suggested_title": "보풀제거기_전문_가이드",
        "patterns": ["모델_비교", "칼날_구매", "배터리_QA", "대량구매_안내"],
        "dialog_types": ["1.지식응답", "1.지식응답", "1.지식응답", "7.상담사전환"],
        "coverage_ratio": "100%",
        "escalation_note": "대량구매(100개+) → B2B 담당자 연결은 에스컬레이션 섹션에 명시"
      }
    ]
  }
}
```

### 3. Generate FAQ Pairs

Create question-answer pairs for each common pattern **based on actual sample analysis**.

**Constraints:**
- You MUST generate at least 3-5 FAQ pairs per cluster (more for complex clusters)
- You MUST write questions using actual customer language from samples (NOT generic questions!)
- You MUST write answers following company's actual tone from samples
- You MUST ensure answers are actionable with specific steps, timeframes, and contact info
- You SHOULD prioritize high-frequency patterns first
- You SHOULD include edge cases and exceptions
- You MAY use placeholders (e.g., `[고객명]`, `[제품명]`) for templates
- You MUST NOT create generic FAQ pairs without reading actual samples

**Critical Requirement:**
❌ **DO NOT** write generic FAQs like "이 문제는 어떻게 해결하나요?"
✅ **DO** extract real questions from samples: "퀵으로 변경 가능한가요?", "TPM 설정은 어떻게 하나요?"

**Company Tone Analysis:**
Before generating FAQs, identify the company's tone from actual samples:
- Greeting style (formal/casual, emoji usage)
- Response structure (numbered steps, bullet points)
- Brand messaging ("최고의 품질과 합리적인 가격" for Assacom)
- Closing style ("추가 문의 있으시면", "감사합니다!")

**FAQ Structure:**
```json
{
  "cluster_id": 2,
  "label": "충전_AS",
  "faq_pairs": [
    {
      "faq_id": "faq_2_1",
      "question": "충전이 안 되는데 어떻게 해야 하나요?",
      "answer": "충전 문제는 다음 단계로 확인해주세요:\n1. 케이블과 어댑터가 제품과 전원에 제대로 연결되었는지 확인\n2. 충전 포트에 이물질이나 먼지가 없는지 확인\n3. 다른 케이블로 교체 테스트\n4. 문제가 지속되면 AS 접수를 진행해드립니다. (1544-XXXX)",
      "related_patterns": ["충전기_고장_증상"],
      "escalation": "3회 이상 문의 시 즉시 AS 접수",
      "keywords": ["충전", "불량", "AS", "케이블"],
      "frequency": "high"
    },
    {
      "faq_id": "faq_2_2",
      "question": "충전기를 새로 받을 수 있나요?",
      "answer": "충전기 교체는 AS 접수 후 가능합니다. \n- AS 접수: 1544-XXXX 또는 홈페이지\n- 검수 후 교체 여부 결정 (1-2일)\n- 교체품 발송 (3-5일 소요)\n무상 교체 기준: 구매 후 1년 이내, 제품 결함으로 인한 고장",
      "related_patterns": ["충전기_교체_요청"],
      "escalation": "warranty 기간 확인 필요",
      "keywords": ["충전기", "교체", "AS", "무상"],
      "frequency": "high"
    },
    {
      "faq_id": "faq_2_3",
      "question": "충전 시간이 얼마나 걸리나요?",
      "answer": "[제품명] 제품의 표준 충전 시간은 약 3-4시간입니다.\n- 완전 방전 상태: 4시간\n- 일반 충전: 2-3시간\n만약 5시간 이상 소요되거나 평소보다 현저히 느려진 경우 배터리 문제일 수 있으니 AS 센터로 문의 바랍니다.",
      "related_patterns": ["충전_속도_문의"],
      "keywords": ["충전시간", "완충", "배터리"],
      "frequency": "medium"
    }
  ]
}
```

**Generation Guidelines:**
- **Questions**: Use casual, conversational Korean (customers' actual language)
- **Answers**: Professional but friendly tone, step-by-step format preferred
- **Escalation**: When to transfer to human agent or specialized team
- **Keywords**: For search and categorization
- **Related Patterns**: Link to patterns from Step 2

### 4. Identify Response Strategies

Define response strategies, escalation rules, and process flows.

**Constraints:**
- You MUST identify response strategy for each cluster
- You MUST define escalation triggers (when to transfer to human)
- You SHOULD document standard response time expectations
- You SHOULD identify automation opportunities (self-service, chatbot)
- You MAY create decision trees for complex issues
- You MUST specify required agent knowledge or tools

**Response Strategy Structure:**
```json
{
  "cluster_id": 2,
  "label": "충전_AS",
  "response_strategy": {
    "primary_approach": "troubleshooting_guide",
    "description": "단계별 문제 해결 가이드 제공 후 AS 접수 진행",
    "standard_response_time": "즉시 (자동 응답 가능)",
    "escalation_triggers": [
      "고객이 트러블슈팅 3회 이상 시도",
      "보증 기간 확인 필요",
      "배터리 교체 요청"
    ],
    "escalation_target": "AS 센터",
    "required_knowledge": [
      "제품 충전 사양 (시간, 전압)",
      "무상 AS 기준 (1년, 결함)",
      "교체 프로세스 (검수 1-2일, 발송 3-5일)"
    ],
    "required_tools": [
      "AS 접수 시스템",
      "고객 구매 이력 조회",
      "재고 확인 시스템"
    ],
    "automation_opportunity": "high",
    "automation_suggestion": "트러블슈팅 가이드를 챗봇으로 자동 응답, AS 접수만 상담원 처리",
    "template_needed": true,
    "template_type": "troubleshooting_steps"
  }
}
```

**Decision Tree Example (Complex Issues):**
```markdown
## 충전_AS 대응 흐름

1. **초기 증상 파악**
   - 충전이 전혀 안 됨 → [케이블 체크]
   - 충전이 느림 → [배터리 수명 확인]
   - 간헐적 충전 → [접촉 불량 확인]

2. **케이블 체크**
   - 다른 케이블로 테스트 요청
   - 성공 → 케이블 교체 안내
   - 실패 → [AS 접수]

3. **AS 접수**
   - 구매 날짜 확인
   - 1년 이내 → 무상 AS 안내
   - 1년 이후 → 유상 AS 안내 (비용 10,000원)
   - 접수 완료 → 예상 처리 기간 안내 (5-7일)
```

### 5. Build Keyword Taxonomy

Create a structured keyword taxonomy for search and categorization.

**Constraints:**
- You MUST extract keywords from all analyzed clusters
- You MUST group keywords hierarchically (category → subcategory → keywords)
- You SHOULD identify synonyms and variations
- You MAY include common typos or abbreviations
- You MUST use Korean keywords (customer language)

**Keyword Taxonomy Structure:**
```json
{
  "company": "Meliens",
  "taxonomy": {
    "A/S": {
      "충전": {
        "primary_keywords": ["충전", "충전기", "케이블", "어댑터"],
        "synonyms": ["충천", "충진", "전원", "배터리"],
        "related_terms": ["완충", "충전시간", "충전속도", "충전불량"],
        "product_specific": ["타입C", "USB", "무선충전"]
      },
      "수리": {
        "primary_keywords": ["수리", "AS", "고장", "불량"],
        "synonyms": ["에이에스", "a/s", "AS접수"],
        "related_terms": ["무상수리", "유상수리", "수리비용", "수리기간"]
      },
      "교체": {
        "primary_keywords": ["교체", "교환", "새제품"],
        "related_terms": ["재발송", "반품교환"]
      }
    },
    "배송": {
      "조회": {
        "primary_keywords": ["배송", "배송조회", "송장", "운송장"],
        "related_terms": ["언제도착", "배송기간", "배송현황"],
        "carrier_names": ["CJ", "로젠", "우체국"]
      }
    }
  }
}
```

### 6. Save Extraction Results

Save all extracted data in structured JSON and/or Markdown format.

**Constraints:**
- You MUST create output directory if it doesn't exist
- You MUST save at least one output format (JSON recommended)
- You SHOULD include metadata (timestamp, source files, cluster count)
- You MAY split output into multiple files for readability
- You MUST NOT overwrite existing files without confirmation

**Output Files:**

1. **`patterns.json`**: All extracted patterns with HT/TS classification
```json
{
  "metadata": {
    "company": "Meliens",
    "generated_at": "2024-01-28T18:30:00",
    "source_files": [
      "results/meliens/meliens_clustered.xlsx",
      "results/meliens/meliens_tags.xlsx"
    ],
    "total_clusters": 10,
    "analyzed_clusters": 10,
    "n_samples_per_cluster": 20
  },
  "clusters": [
    {
      "cluster_id": 2,
      "label": "충전_AS",
      "category": "A/S",
      "cluster_size": 120,
      "patterns": [...],
      "faq_pairs": [...],
      "response_strategy": {...},
      "sop_split_recommendation": {
        "split": false,
        "reasoning": "전체 3개 패턴 모두 TS — 단일 TS SOP 권장",
        "sops": [
          {
            "type": "TS",
            "suggested_title": "충전_AS_처리",
            "patterns": ["충전기_고장_증상", "충전기_교체_요청", "충전_속도_문의"],
            "dialog_types": ["5.조건부실행", "3.단순실행", "1.지식응답"],
            "coverage_ratio": "100%"
          }
        ]
      }
    },
    ...
  ]
}
```

2. **`faq.json`**: All FAQ pairs
```json
{
  "metadata": {...},
  "faq_pairs": [
    {
      "faq_id": "faq_2_1",
      "cluster_id": 2,
      "cluster_label": "충전_AS",
      "question": "...",
      "answer": "...",
      ...
    },
    ...
  ]
}
```

3. **`response_strategies.json`**: Response strategies and escalation rules
```json
{
  "metadata": {...},
  "strategies": [
    {
      "cluster_id": 2,
      "label": "충전_AS",
      "response_strategy": {...}
    },
    ...
  ]
}
```

4. **`keywords.json`**: Keyword taxonomy
```json
{
  "metadata": {...},
  "taxonomy": {...}
}
```

5. **`extraction_summary.md`**: Human-readable summary
```markdown
# Stage 2 Extraction Summary: Meliens

## Overview
- Company: Meliens (Electronics)
- Clusters Analyzed: 10
- Total Patterns: 37
- Total FAQ Pairs: 52
- Extraction Depth: Standard

## Top Patterns by Cluster
### Cluster 2: 충전_AS (120건, 7.3%)
1. 충전기_고장_증상 (high frequency)
2. 충전기_교체_요청 (high frequency)
3. 충전_속도_문의 (medium frequency)

[Continue for top 5 clusters...]

## Automation Opportunities
1. **충전 트러블슈팅** (Cluster 2): High automation potential
   - Chatbot can handle initial troubleshooting
   - Only escalate after 3 failed attempts

2. **배송 조회** (Cluster 7): Very high automation potential
   - Fully automate with tracking link
   - No human intervention needed

## Next Steps for Stage 3
1. Focus on top 5 clusters for SOP generation
2. Create response templates for high-frequency patterns
3. Design decision trees for complex issues (충전_AS, 배송_문의)
```

**File Creation:**
```bash
# In Claude Code
Write results/meliens/02_extraction/patterns.json
Write results/meliens/02_extraction/faq.json
Write results/meliens/02_extraction/response_strategies.json
Write results/meliens/02_extraction/keywords.json
Write results/meliens/02_extraction/extraction_summary.md
```

### 7. Enrich Patterns with Conversation Samples

Embed representative conversation samples into patterns.json for Stage 3 optimization.

**Constraints:**
- You MUST run this step after Step 6 (patterns.json saved)
- You MUST use `enrich_patterns.py` Python script
- You MUST select 20 representative conversations per cluster
- You MUST include both sample conversations and tone-and-manner examples
- Stage 3에서 반드시 이 파일을 사용한다 — clustered.xlsx 재로드 불필요

**Execution:**
```bash
python3 scripts/enrich_patterns.py \
  --patterns results/{company}/02_extraction/patterns.json \
  --messages results/{company}/{company}_messages.csv \
  --output results/{company}/02_extraction/patterns_enriched.json
  --n-samples 20
```

**Sample Selection Strategy:**
1. **Simple case** (1개): 가장 짧은 대화 (3+ 턴, 간단한 케이스)
2. **Complex case** (1개): 가장 긴 대화 (15+ 턴, 복잡한 케이스)
3. **Representative cases** (3개): 중간 길이 대화 (median ± 1)
4. **Additional samples** (나머지): 전체 대화에서 균등 간격 샘플링으로 20건 채움

**Tone-and-Manner Extraction:**
- 상담원 메시지 20개 추출
- 자동 분류: greeting, empathy, closing, proactive
- 길이 10-200자, 중복 제거

**Expected Output:**
```
✅ Enrichment 완료!
총 클러스터: 10개
파일 크기: 125 KB → 488 KB (3.9x)
출력: patterns_enriched.json
```

**Benefits for Stage 3:**
- clustered.xlsx 재로드 불필요
- 샘플 선정 전략 일관성
- 파일 의존성 단순화
- 약간의 속도 향상 (~8초/SOP)

## Examples

### Example 1: Standard Extraction (Assacom - Top 10 Clusters)

**Parameters:**
- clustering_output_dir: `results/assacom`
- company: "Assacom"
- focus_clusters: "top_10"
- n_samples_per_cluster: 20 (기본값)

**Execution Method:**
1. Use Bash + Python to extract 20 samples per cluster
2. Analyze clusters sequentially in main agent (순차 처리)
3. Save results to JSON files after each analysis step

**Actual Execution Time**: **~8-12 minutes**

**Output:**
- 10 clusters analyzed (645건, 64.5% coverage)
- 56 patterns extracted (실제 고객 표현 기반!)
- 39 FAQ pairs generated (3-5 per cluster)
- 10 response strategies
- Company tone reflected (Assacom: "최고의 품질과 합리적인 가격", 이모지 사용)

**Key Learnings:**
- Real customer expressions discovered: "안심번호로 배송조회 불가", "11번가 할인구매가 적용"
- Unexpected patterns found: "전화 상담 선호" (15%), "부품 추가/변경" (40%)
- Brand-specific tone: Assacom uses friendly emojis (🙌😊) and emphasizes quality
- patterns_enriched.json generated with conversation samples and tone-and-manner examples

### Example 2: Higher Sample Count (More Thorough Analysis)

**Parameters:**
- clustering_output_dir: `results/meliens`
- company: "Meliens"
- focus_clusters: "all"
- n_samples_per_cluster: 30 (더 많은 샘플)

**Execution Time**: ~20-25 minutes

**Output:**
- All 20 clusters analyzed with 30 samples each
- 80+ patterns extracted (4-6 per cluster)
- 70+ FAQ pairs generated (5-7 per cluster)
- More comprehensive pattern coverage
- Edge cases and exceptions better captured
- patterns_enriched.json with richer sample diversity

## Troubleshooting

### Issue 1: Patterns are too generic

**Symptom**: Extracted patterns lack specificity
- Example: "조립 PC 견적 부탁드립니다" ← Generic (guessed)
- Problem: No actual customer used this exact phrase!

**Root Cause**: LLM created patterns based on cluster label without reading actual samples

**Solution:**
1. **ALWAYS read 20 actual sample messages first** using Python
2. **Extract phrases verbatim** from samples (copy-paste, don't paraphrase!)
3. **Compare before/after**:
   - ❌ Generic (guessed): "견적 요청해주세요"
   - ✅ Actual (from samples): "하드디스크 추가 장착 가능", "케이스 교체 요청"
4. **Identify company-specific patterns**:
   - Example: Assacom customers say "11번가 할인구매가 적용" (not generic "할인 되나요")
5. **Measure frequency accurately**: Count occurrences in 20 samples, not estimate

**Real Example (Assacom Cluster 6):**
```
❌ 잘못된 방식 (추측):
"common_phrases": ["조립 PC 견적 부탁드립니다"]

✅ 올바른 방식 (실제 샘플):
"common_phrases": [
  "하드디스크와 SATA SSD 추가 장착 가능",  ← Sample 1
  "SSD, RAM 미포함 주문 확인",           ← Sample 4
  "케이스 교체 요청"                     ← Sample 9
]
```

### Issue 2: FAQ answers are incomplete

**Symptom**: Answers don't provide actionable steps

**Solution:**
- Reference company's existing support documentation
- Include specific phone numbers, URLs, timeframes
- Add decision logic ("IF warranty expired, THEN...")
- Review with domain expert if available

### Issue 3: Too many patterns per cluster

**Symptom**: 10+ patterns per cluster, hard to manage

**Solution:**
- Group similar patterns under umbrella pattern
- Focus on top 3-5 highest frequency patterns
- Save minor patterns as "edge cases" separately

## Related Documentation

- **Stage 1**: `agent-sops/stage1-clustering.sop.md` (Prerequisite)
- **Stage 3**: `agent-sops/stage3-sop-generation.sop.md` (Next step)
- **Analysis Report Template**: `rules/analysis-report-template.md`

## Notes

### Why No Python Scripts?

Stage 2 is intentionally LLM-based because:
- Pattern extraction requires language understanding (not statistical)
- FAQ generation needs natural language generation
- Response strategies require domain reasoning
- Claude Code can analyze Excel and generate JSON directly

### Extraction Quality Tips

1. **Read diverse samples**: Don't just read first 10 messages, sample throughout cluster
2. **Preserve customer voice**: Use actual phrases, don't paraphrase
3. **Think operationally**: Consider what agents need to respond effectively
4. **Validate with domain knowledge**: If available, review with customer support team

### Time Estimates (Updated based on actual execution)

| Samples/Cluster | Clusters | Time | Notes |
|-----------------|----------|------|-------|
| 10 | 10 | ~5-8 min | 빠른 분석, enrichment 포함 |
| 20 (기본값) | 10 | ~8-15 min | 균형잡힌 분석, enrichment 포함 |
| 30 | 10 | ~15-25 min | 심층 분석, enrichment 포함 |

**Actual Performance (Assacom Case):**
- 10 clusters analyzed with real samples: **~8-12 minutes**
- Sequential analysis in main agent: **안정적이고 빠름** (서브에이전트 사용 시 hanging 발생)
- Sample collection (Python): < 1 second
- Pattern extraction per cluster: ~1-2분
- FAQ generation (통합): 2-3분
- Enrichment (Step 7): 1-2분

**Efficiency Tips:**
1. ⚠️ **서브에이전트 사용 금지** - Task agent 사용 시 성능 저하 및 hanging 발생
2. **메인 에이전트에서 순차 처리** - 각 클러스터를 순차적으로 분석 (더 빠르고 안정적)
3. Use `random_state=42` for consistent sampling
4. Focus on top 10 clusters first (covers 60-70% of data)
5. Enrichment는 마지막에 한 번만 실행 (Step 7)

*Note: Time varies based on cluster complexity and domain familiarity.*
