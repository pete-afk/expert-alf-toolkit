import numpy as np
import pickle
import hashlib
import os
import time
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..config import (
    UPSTAGE_API_KEY,
    UPSTAGE_BASE_URL,
    EMBEDDING_MODEL,
    EMBEDDING_BATCH_SIZE,
    LOCAL_EMBEDDING_MODEL,
    LOCAL_EMBEDDING_AVAILABLE
)

# 캐시 키 생성
def get_cache_key(texts, model_name):
    text_hash = hashlib.md5(''.join(texts).encode()).hexdigest()
    return f"{model_name}_{text_hash}_{len(texts)}"

# 텍스트 전처리
def _clean_texts(texts):
    cleaned = []
    for text in texts:
        text = str(text).strip()
        if len(text) < 3:
            text = "빈 텍스트"
        cleaned.append(text)
    return cleaned

# ── Upstage Solar API 임베딩 ──
def _generate_embeddings_api(cleaned_texts):
    from openai import OpenAI  # pyright: ignore[reportMissingImports]
    client = OpenAI(api_key=UPSTAGE_API_KEY, base_url=UPSTAGE_BASE_URL)

    def embed_batch_with_retry(batch, max_retries=3):
        """배치 임베딩 생성 (재시도 로직 포함)"""
        for attempt in range(max_retries):
            try:
                response = client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=batch
                )
                return [item.embedding for item in response.data]
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"\n   ⚠️  배치 임베딩 실패 (시도 {attempt + 1}/{max_retries}), {wait_time}초 후 재시도...")
                    time.sleep(wait_time)
                else:
                    print(f"\n   ❌ 배치 임베딩 최종 실패: {e}")
                    raise

    batch_size = EMBEDDING_BATCH_SIZE
    batches = [cleaned_texts[i:i+batch_size] for i in range(0, len(cleaned_texts), batch_size)]

    embeddings = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(embed_batch_with_retry, batch): idx
                   for idx, batch in enumerate(batches)}

        results = {}
        for future in tqdm(as_completed(futures), total=len(futures), desc="   Embedding"):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                raise RuntimeError(f"배치 {idx} 임베딩 실패 - 전체 작업 중단") from e

        for idx in sorted(results.keys()):
            embeddings.extend(results[idx])

    return np.array(embeddings)

# ── 로컬 모델 임베딩 (BGE-m3-ko) ──
def _generate_embeddings_local(cleaned_texts):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise RuntimeError(
            "❌ sentence-transformers 패키지가 필요합니다.\n"
            "   pip install sentence-transformers"
        )

    print(f"   모델 로딩: {LOCAL_EMBEDDING_MODEL}")
    device = _get_best_device()
    print(f"   디바이스: {device}")
    model = SentenceTransformer(LOCAL_EMBEDDING_MODEL, device=device)

    embeddings = model.encode(
        cleaned_texts,
        show_progress_bar=True,
        batch_size=64,
        normalize_embeddings=True
    )

    return np.array(embeddings)

def _get_best_device():
    """Mac MPS > CUDA > CPU 순으로 최적 디바이스 선택"""
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    return "cpu"

# ── 메인 함수 ──
def generate_embeddings(texts, cache_dir='cache'):
    # 우선순위: 로컬 (BGE-m3-ko) → Solar API fallback
    use_local = LOCAL_EMBEDDING_AVAILABLE
    if use_local:
        model_name = LOCAL_EMBEDDING_MODEL.split("/")[-1]
    else:
        model_name = EMBEDDING_MODEL
        print("   ⚠️  sentence-transformers 미설치 → Solar API로 fallback")

    os.makedirs(cache_dir, exist_ok=True)
    cache_key = get_cache_key(texts, model_name)
    cache_file = Path(cache_dir) / f"embeddings_{cache_key}.pkl"

    if cache_file.exists():
        with open(cache_file, 'rb') as f:
            cache_data = pickle.load(f)
            return cache_data['embeddings']

    cleaned_texts = _clean_texts(texts)

    if use_local:
        print(f"   로컬 모델: {LOCAL_EMBEDDING_MODEL}")
        embeddings = _generate_embeddings_local(cleaned_texts)
    else:
        embeddings = _generate_embeddings_api(cleaned_texts)

    with open(cache_file, 'wb') as f:
        pickle.dump({
            'embeddings': embeddings,
            'model': model_name,
            'n_samples': len(texts)
        }, f)

    return embeddings
