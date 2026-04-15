# Clustering Module

Excel 고객 상담 데이터를 클러스터링하는 모듈입니다.

## 모듈 구조

```
clustering/
├── __init__.py           # 모듈 export
├── data_loader.py        # Excel 데이터 로딩
├── text_enhancer.py      # 텍스트 품질 향상
├── embeddings.py         # 임베딩 생성 & 캐싱
├── clustering.py         # K-Means 클러스터링
├── tagging.py            # LLM 자동 태깅
└── output.py             # 결과 저장
```

## 설계 결정 사항

### 기술 선택

1. 어떻게 분류할까?
- LLM이 직접 상담 내역을 읽고 분석하면 데이터가 너무 많아서 read/write에 소요시간 및 콘텍스트가 너무 커짐
-> 단순 분류 단계는 기술적으로 접근하여 재현성 높이기
-> 머신러닝 모델로 군집화

2. 모델이 input을 하기 위해서는 임베딩이 필요
-> 임베딩 API는 저렴하기 때문에 API로 빠르게 구현
**Upstage Solar API**
- **임베딩**: `embedding-passage` - 한국어 고객 상담 데이터에 최적화된 성능
- **LLM 태깅**: `solar-mini` - 빠른 응답 속도와 비용 효율성
- **선택 이유**: OpenAI 대비 한국어 처리 품질 우수, API 안정성, 국내 서비스 지원

3. 군집화(유사도 것끼리 라벨링)
-> 모델 선택 필요
**K-Means 클러스터링 모델**
- **HDBSCAN 대신 K-Means 선택 이유**:
  - 노이즈 데이터 0% (모든 고객 문의가 클러스터에 할당됨)
  - 클러스터 개수 명시적 제어 가능 (최적 개수 측정가능 = Silhouette score)
    *Silhouette score: 클러스터링 품질 평가 지표 (-1~1). 1에 가까울수록 클러스터 간 분리가 명확함. 각 데이터가 자신의 클러스터와 얼마나 잘 맞고, 다른 클러스터와 얼마나 떨어져 있는지 측정 
  - 안정적인 재현성 (random_state 고정)
  - 빠른 수렴 속도 (1000개 기준 ~5초)
- **최적 K 자동 선택**: Silhouette score 기준으로 [8, 10, 12, 15, 20, 25] 범위 테스트


## 주요 기능

### 1. 데이터 로딩 (`data_loader.py`)
- Excel에서 UserChat data + Message data 로드
- 샘플링 옵션 지원

### 2. 텍스트 향상 (`text_enhancer.py`)
- 3-level fallback 전략으로 텍스트 품질 개선
- summarizedMessage → first_message → 3턴 결합

### 3. 임베딩 생성 (`embeddings.py`)
- Upstage Solar `embedding-passage` (4096차원)
- 병렬 처리 (max_workers=3)
- 자동 캐싱 (재실행 시 캐시 사용)
- Exponential backoff 재시도

### 4. 클러스터링 (`clustering.py`)
- K-Means 알고리즘
- 최적 K 자동 선택 (silhouette score)

### 5. LLM 태깅 (`tagging.py`)
- Solar-mini로 클러스터 자동 라벨링
- 카테고리, 키워드 추출

### 6. 결과 저장 (`output.py`)
- clustered_data.xlsx - 전체 데이터 + 클러스터 정보
- cluster_tags.xlsx - 클러스터별 메타데이터

## 사용 예시

```python
from scripts.clustering import (
    load_data,
    enhance_text,
    generate_embeddings,
    cluster_data,
    tag_clusters,
    save_results
)

# 1. 데이터 로딩
df_chat, df_msg = load_data('data.xlsx', sample_size=1000)

# 2. 텍스트 향상
df_chat = enhance_text(df_chat, df_msg)

# 3. 임베딩 생성
texts = df_chat['enhanced_text'].tolist()
embeddings = generate_embeddings(texts)

# 4. 클러스터링
labels, silhouette = cluster_data(embeddings, n_clusters=20)
df_chat['cluster_id'] = labels

# 5. LLM 태깅
tags_df = tag_clusters(df_chat)

# 6. 결과 저장
save_results(df_chat, tags_df, 'results', 'output')
```

## 성능

- **임베딩 생성**: 1000개당 ~30초 (병렬 처리)
- **K-Means**: 1000개당 ~5초
- **LLM 태깅**: 20개 클러스터당 ~1분
- **총 소요 시간**: 1000개 기준 ~2-3분

## 캐싱

임베딩은 자동으로 캐싱됩니다:
- 위치: `cache/embeddings_{model}_{hash}_{count}.pkl`
- 동일 데이터 재실행 시 즉시 로드 (~5초)
