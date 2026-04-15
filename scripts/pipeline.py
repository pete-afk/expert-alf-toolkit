#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.clustering import (
    load_data,
    enhance_text,
    generate_embeddings,
    find_optimal_k,
    cluster_data,
    tag_clusters,
    save_results,
    save_messages
)
from scripts.config import DEFAULT_K_RANGE, DEFAULT_CACHE_DIR, DEFAULT_OUTPUT_DIR, DEFAULT_OUTPUT_PREFIX

def print_header(text):
    print(f"\n{text}")

def main():
    parser = argparse.ArgumentParser(
        description='Customer Support Chat Clustering Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--input', '-i', required=True, help='입력 Excel 파일')
    parser.add_argument('--sample', '-s', help='샘플링할 데이터 수 (기본: 1000, 예: 1000 또는 all)')
    parser.add_argument('--k', help='클러스터 개수 (기본: auto, 예: auto 또는 10)')
    parser.add_argument('--k-range', help='테스트할 K 값들 (쉼표 구분, 예: 10,15,20,25)')
    parser.add_argument('--tagging-mode', default='api', choices=['api', 'agent', 'skip'],
                        help='태깅 방식 (api: Solar-mini 개별, agent: Solar-pro 통합, skip: 건너뛰기, 기본: api)')
    parser.add_argument('--skip-tagging', action='store_true',
                        help='태깅을 건너뛰고 클러스터링만 수행 (Claude 수동 태깅용)')
    parser.add_argument('--output', '-o', default=DEFAULT_OUTPUT_DIR, help=f'출력 디렉토리 (기본: {DEFAULT_OUTPUT_DIR})')
    parser.add_argument('--prefix', '-p', default=DEFAULT_OUTPUT_PREFIX, help=f'출력 파일명 접두사 (기본: {DEFAULT_OUTPUT_PREFIX})')
    parser.add_argument('--cache-dir', default=DEFAULT_CACHE_DIR, help=f'캐시 디렉토리 (기본: {DEFAULT_CACHE_DIR})')
    parser.add_argument('--umap', action='store_true', default=True, help='UMAP 차원 축소 적용 (기본: 활성화)')
    parser.add_argument('--no-umap', action='store_true', help='UMAP 비활성화 (원본 4096D로 클러스터링)')
    parser.add_argument('--umap-components', type=int, default=30, help='UMAP 목표 차원 수 (기본: 30)')
    
    args = parser.parse_args()

    # Handle skip-tagging flag
    if args.skip_tagging:
        args.tagging_mode = 'skip'

    # Parse sample size
    sample_size = None
    if args.sample:
        if args.sample == 'all':
            sample_size = None
        else:
            sample_size = int(args.sample)
    else:
        sample_size = 3000  # Default: 3000

    print_header("🎯 Userchat-to-SOP Pipeline")
    print(f"   입력: {args.input}")
    print(f"   샘플: {sample_size if sample_size else '전체'}개")

    print_header("1️⃣ 데이터 로딩...")
    df_chat, df_msg = load_data(args.input, sample_size)
    print(f"   UserChat: {len(df_chat):,}개, Message: {len(df_msg):,}개")

    print_header("2️⃣ 텍스트 향상...")
    df_chat = enhance_text(df_chat, df_msg)
    print(f"   완료")

    print_header("3️⃣ 임베딩 생성...")
    texts = df_chat['enhanced_text'].tolist()
    embeddings = generate_embeddings(texts, cache_dir=args.cache_dir)
    print(f"   완료: {embeddings.shape}")

    print_header("4️⃣ K-Means 클러스터링...")
    use_umap = args.umap and not args.no_umap
    umap_components = args.umap_components

    if args.k and args.k != 'auto':
        # Fixed K value
        k_value = int(args.k)
        labels, silhouette = cluster_data(embeddings, k_value, use_umap=use_umap, umap_components=umap_components)
        print(f"   K={k_value}, Silhouette={silhouette:.3f}")
    else:
        # Auto: find optimal K
        k_range = None
        if args.k_range:
            k_range = [int(k) for k in args.k_range.split(',')]
        else:
            k_range = DEFAULT_K_RANGE

        best_k, labels, results = find_optimal_k(embeddings, k_range, use_umap=use_umap, umap_components=umap_components)
        best_result = next(r for r in results if r['n_clusters'] == best_k)
        print(f"   선택: K={best_k}, Silhouette={best_result['silhouette']:.3f}")

    df_chat['cluster_id'] = labels

    # Tagging step (conditional)
    if args.tagging_mode == 'skip':
        print_header("5️⃣ LLM 태깅...")
        print("   건너뜀 (수동 태깅 필요)")

        # Create placeholder tags
        df_chat['label'] = '[Unlabeled]'
        df_chat['category'] = '[Uncategorized]'
        df_chat['keywords'] = ''

        tags_df = pd.DataFrame({
            'cluster_id': sorted(df_chat['cluster_id'].unique()),
            'cluster_size': [len(df_chat[df_chat['cluster_id'] == cid]) for cid in sorted(df_chat['cluster_id'].unique())],
            'label': ['[Unlabeled]'] * df_chat['cluster_id'].nunique(),
            'category': ['[Uncategorized]'] * df_chat['cluster_id'].nunique(),
            'keywords': [''] * df_chat['cluster_id'].nunique()
        })
    else:
        print_header(f"5️⃣ LLM 태깅...")
        tags_df = tag_clusters(df_chat, df_msg=df_msg, mode=args.tagging_mode)

        # 간단한 요약만 출력
        category_dist = tags_df.groupby('category')['cluster_size'].sum().sort_values(ascending=False)
        top_categories = [f"{cat}({count/len(df_chat)*100:.1f}%)"
                         for cat, count in category_dist.head(3).items()]
        print(f"   완료: {len(tags_df)}개 클러스터 - {', '.join(top_categories)}")

    print_header("6️⃣ 결과 저장...")
    result_file, tags_file = save_results(df_chat, tags_df, args.output, args.prefix)
    print(f"   ✅ {result_file}")
    print(f"   ✅ {tags_file}")

    # Save message data for sampled chats
    messages_file = save_messages(df_chat, df_msg, args.output, args.prefix)

    print_header("✅ 완료")

if __name__ == '__main__':
    main()
