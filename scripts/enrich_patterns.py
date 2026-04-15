#!/usr/bin/env python3
"""
Stage 2.5: patterns.json에 대표 대화 샘플 추가

입력:
  - results/assacom/02_extraction/patterns.json
  - results/assacom/assacom_messages.csv

출력:
  - results/assacom/02_extraction/patterns_enriched.json

목적:
  - Stage 4 (SOP 생성)에서 CSV 로드를 제거하기 위해
  - 각 클러스터의 대표 대화와 톤앤매너 샘플을 patterns.json에 포함
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List
import numpy as np
import argparse


def select_representative_conversations(
    cluster_messages: pd.DataFrame,
    cluster_id: int,
    n_samples: int = 20
) -> List[Dict]:
    """
    클러스터에서 대표 대화 선정

    전략:
    1. 가장 짧은 대화 1개 (간단한 케이스)
    2. 가장 긴 대화 1개 (복잡한 케이스, 15턴 이상)
    3. 중간 길이 대화 3개 (대표 케이스)
    4. 나머지를 균등 간격 샘플링으로 채움 (n_samples까지)
    """
    chat_ids = cluster_messages['chatId'].unique()

    if len(chat_ids) == 0:
        return []

    # 각 대화의 메시지 수 계산
    chat_lengths = []
    for cid in chat_ids:
        conv = cluster_messages[cluster_messages['chatId'] == cid]
        chat_lengths.append({
            'chat_id': cid,
            'message_count': len(conv),
            'messages': conv.sort_values('createdAt').to_dict('records')
        })

    # 길이 순 정렬
    chat_lengths.sort(key=lambda x: x['message_count'])

    selected = []
    selected_ids = set()

    def add(item, reason):
        if item['chat_id'] not in selected_ids:
            selected.append({**item, 'selection_reason': reason})
            selected_ids.add(item['chat_id'])

    # 1. 가장 짧은 대화 (3턴 이상)
    for item in chat_lengths:
        if item['message_count'] >= 3:
            add(item, 'simple')
            break

    # 2. 가장 긴 대화 (15턴 이상)
    if chat_lengths[-1]['message_count'] > 15:
        add(chat_lengths[-1], 'complex')

    # 3. 중간 길이 대화 3개
    median_idx = len(chat_lengths) // 2
    for offset in [0, -1, 1, -2, 2]:
        idx = median_idx + offset
        if 0 <= idx < len(chat_lengths):
            add(chat_lengths[idx], 'representative')
        if len(selected) >= 5:
            break

    # 4. 나머지를 균등 간격 샘플링으로 채움
    if len(chat_lengths) > len(selected) and len(selected) < n_samples:
        remaining = [c for c in chat_lengths if c['chat_id'] not in selected_ids]
        need = n_samples - len(selected)
        if len(remaining) <= need:
            for item in remaining:
                add(item, 'additional')
        else:
            step = len(remaining) / need
            for i in range(need):
                idx = int(i * step)
                add(remaining[idx], 'additional')

    # 최대 n_samples개로 제한
    selected = selected[:n_samples]

    # 턴 형식으로 변환
    for conv in selected:
        turns = []
        for i, msg in enumerate(conv['messages'], 1):
            plain_text = msg.get('plainText')
            if pd.isna(plain_text):
                plain_text = ''

            turns.append({
                'turn_number': i,
                'person_type': msg['personType'],
                'message': plain_text,
                'created_at': str(msg['createdAt'])
            })

        conv['turns'] = turns
        del conv['messages']

        # Summary 생성 (첫 유저 메시지 기반)
        user_msgs = [t['message'] for t in turns if t['person_type'] == 'user' and t['message']]
        if user_msgs:
            conv['summary'] = user_msgs[0][:100]
        else:
            conv['summary'] = "상담 내역"

    return selected


def extract_tone_samples(
    cluster_messages: pd.DataFrame,
    n_samples: int = 20
) -> List[Dict]:
    """상담원 메시지에서 톤앤매너 샘플 추출"""
    manager_msgs = cluster_messages[
        cluster_messages['personType'] == 'manager'
    ]['plainText'].dropna()

    if len(manager_msgs) == 0:
        return []

    # 길이 200자 이내, 중복 제거
    valid_msgs = manager_msgs[
        (manager_msgs.str.len() > 10) & (manager_msgs.str.len() <= 200)
    ].drop_duplicates().tolist()

    # 랜덤 샘플링
    if len(valid_msgs) > n_samples:
        np.random.seed(42)  # 재현성을 위해
        valid_msgs = np.random.choice(valid_msgs, n_samples, replace=False).tolist()

    # 카테고리 자동 분류 (단순 키워드 기반)
    samples = []
    for msg in valid_msgs:
        category = "informative"
        context = ""

        if any(kw in msg for kw in ['안녕하세요', '최고의 품질', '합리적인 가격', '아싸컴입니다']):
            category = "greeting"
            context = "초기 인사"
        elif any(kw in msg for kw in ['죄송', '불편', '양해']):
            category = "empathy"
            context = "문제 발생 시"
        elif any(kw in msg for kw in ['감사', '추가 문의', '좋은 하루']):
            category = "closing"
            context = "상담 종료"
        elif any(kw in msg for kw in ['확인', '처리', '도와드리', '안내']):
            category = "proactive"
            context = "적극적 응대"

        samples.append({
            'message': msg,
            'category': category,
            'context': context
        })

    return samples


def enrich_patterns(patterns_path: str, messages_path: str, output_path: str, n_samples: int = 20):
    """patterns.json에 대표 대화 샘플 추가"""

    print(f"📂 파일 로드 중...")
    print(f"   - patterns.json: {patterns_path}")
    print(f"   - messages.csv: {messages_path}")
    print()

    # 로드
    with open(patterns_path, 'r', encoding='utf-8') as f:
        patterns_data = json.load(f)

    messages_df = pd.read_csv(messages_path)

    print(f"✅ 로드 완료")
    print(f"   - 클러스터: {len(patterns_data['clusters'])}개")
    print(f"   - 메시지: {len(messages_df):,}행")
    print()

    # CSV의 cluster_id 분포 확인
    csv_cluster_ids = messages_df['cluster_id'].unique()
    print(f"📊 CSV cluster_id 분포: {sorted(csv_cluster_ids)}")

    # patterns.json의 cluster_id 확인
    patterns_cluster_ids = [c['cluster_id'] for c in patterns_data['clusters']]
    print(f"📊 patterns.json cluster_id: {sorted(patterns_cluster_ids)}")
    print()

    # 각 클러스터 enrichment
    enriched_count = 0
    failed_count = 0

    for cluster in patterns_data['clusters']:
        cluster_id = cluster['cluster_id']

        # CSV에서 해당 클러스터 메시지 필터링
        cluster_messages = messages_df[messages_df['cluster_id'] == cluster_id]

        if len(cluster_messages) == 0:
            print(f"⚠️  Cluster {cluster_id} ({cluster['label']})")
            print(f"   ❌ CSV에 데이터 없음 (클러스터 ID 불일치)")
            print()

            # 빈 샘플 추가
            cluster['sample_conversations'] = []
            cluster['tone_and_manner_samples'] = []
            failed_count += 1
            continue

        print(f"🔄 Cluster {cluster_id} ({cluster['label']})")
        print(f"   메시지: {len(cluster_messages):,}개")

        # 대표 대화 선정
        sample_convs = select_representative_conversations(
            cluster_messages, cluster_id, n_samples=n_samples
        )
        cluster['sample_conversations'] = sample_convs
        print(f"   ✅ 대표 대화: {len(sample_convs)}개 선정")

        # 톤앤매너 샘플
        tone_samples = extract_tone_samples(cluster_messages, n_samples=20)
        cluster['tone_and_manner_samples'] = tone_samples
        print(f"   ✅ 톤앤매너: {len(tone_samples)}개 추출")
        print()

        enriched_count += 1

    # 저장
    print(f"💾 저장 중: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(patterns_data, f, ensure_ascii=False, indent=2)

    # 파일 크기 비교
    import os
    original_size = os.path.getsize(patterns_path) / 1024
    enriched_size = os.path.getsize(output_path) / 1024

    print()
    print("="*60)
    print("✅ Enrichment 완료!")
    print("="*60)
    print(f"총 클러스터: {len(patterns_data['clusters'])}개")
    print(f"  - 성공: {enriched_count}개")
    print(f"  - 실패: {failed_count}개 (cluster_id 불일치)")
    print()
    print(f"파일 크기:")
    print(f"  - 원본: {original_size:.1f} KB")
    print(f"  - Enriched: {enriched_size:.1f} KB ({enriched_size / original_size:.1f}x)")
    print()
    print(f"출력 파일: {output_path}")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(description='patterns.json에 대표 대화 샘플 추가')
    parser.add_argument(
        '--patterns',
        default='results/assacom/02_extraction/patterns.json',
        help='patterns.json 경로'
    )
    parser.add_argument(
        '--messages',
        default='results/assacom/assacom_messages.csv',
        help='messages.csv 경로'
    )
    parser.add_argument(
        '--output',
        default='results/assacom/02_extraction/patterns_enriched.json',
        help='출력 파일 경로'
    )
    parser.add_argument(
        '--n-samples',
        type=int,
        default=20,
        help='클러스터당 대표 대화 수 (기본값: 20)'
    )

    args = parser.parse_args()

    # 프로젝트 루트 기준 경로 변환
    base_dir = Path(__file__).parent.parent

    patterns_path = base_dir / args.patterns
    messages_path = base_dir / args.messages
    output_path = base_dir / args.output

    print("="*60)
    print("Stage 2.5: patterns.json Enrichment")
    print("="*60)
    print()

    # 파일 존재 확인
    if not patterns_path.exists():
        print(f"❌ patterns.json 파일이 없습니다: {patterns_path}")
        return

    if not messages_path.exists():
        print(f"❌ messages.csv 파일이 없습니다: {messages_path}")
        return

    enrich_patterns(
        str(patterns_path),
        str(messages_path),
        str(output_path),
        n_samples=args.n_samples
    )


if __name__ == "__main__":
    main()
