import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize
from ..config import DEFAULT_K_RANGE


def reduce_with_umap(embeddings, n_components=30, n_neighbors=15, min_dist=0.1):
    """UMAP으로 고차원 임베딩을 저차원으로 축소"""
    import umap
    reducer = umap.UMAP(
        n_components=n_components,
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        metric='cosine',
        random_state=42
    )
    reduced = reducer.fit_transform(embeddings)
    return reduced


def _prepare_embeddings(embeddings, use_umap=False, umap_components=30):
    """임베딩 전처리: UMAP 차원 축소(선택) + L2 정규화(UMAP 미사용 시만)"""
    if use_umap:
        print(f"   UMAP 차원 축소: {embeddings.shape[1]}D → {umap_components}D ...")
        return reduce_with_umap(embeddings, n_components=umap_components)
    return normalize(embeddings, norm='l2')


# 최적의 군집 개수 찾기
def find_optimal_k(embeddings, k_range=None, use_umap=False, umap_components=30):
    if k_range is None:
        k_range = DEFAULT_K_RANGE

    normalized = _prepare_embeddings(embeddings, use_umap=use_umap, umap_components=umap_components)
    results = []
    for n_clusters in k_range:
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(normalized)

        silhouette = silhouette_score(normalized, labels)

        cluster_sizes = pd.Series(labels).value_counts()
        min_size = cluster_sizes.min()
        max_size = cluster_sizes.max()
        avg_size = cluster_sizes.mean()

        results.append({
            'n_clusters': n_clusters,
            'silhouette': silhouette,
            'min_size': min_size,
            'max_size': max_size,
            'avg_size': avg_size,
            'labels': labels
        })

    best = max(results, key=lambda x: x['silhouette'])

    return best['n_clusters'], best['labels'], results

# 최종 군집화 수행
def cluster_data(embeddings, n_clusters, use_umap=False, umap_components=30):
    normalized = _prepare_embeddings(embeddings, use_umap=use_umap, umap_components=umap_components)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(normalized)
    silhouette = silhouette_score(normalized, labels)

    return labels, silhouette
