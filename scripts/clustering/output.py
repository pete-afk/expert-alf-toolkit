import pandas as pd
import os
from pathlib import Path

def save_results(df, tags_df, output_dir='results', prefix='output'):
    os.makedirs(output_dir, exist_ok=True)

    tags_file = Path(output_dir) / f"{prefix}_tags.xlsx"
    tags_df.to_excel(tags_file, index=False)

    result_df = df.merge(tags_df, on='cluster_id', how='left', suffixes=('', '_tag'))
    result_file = Path(output_dir) / f"{prefix}_clustered.xlsx"
    result_df.to_excel(result_file, index=False)

    return result_file, tags_file

def save_messages(df_chat, df_msg, output_dir='results', prefix='output'):
    """
    샘플링된 유저챗 데이터와 해당하는 메시지 데이터를 CSV로 저장합니다.

    Args:
        df_chat: UserChat DataFrame (with cluster_id)
        df_msg: Message DataFrame
        output_dir: Output directory path
        prefix: File prefix (e.g., 'assacom')

    Returns:
        Path to saved CSV file
    """
    os.makedirs(output_dir, exist_ok=True)

    # Get sampled UserChat IDs
    sample_chat_ids = df_chat['id'].tolist()

    # Filter messages for sampled chats
    # Check column name (might be 'userChatId' or 'chatId')
    id_col = 'userChatId' if 'userChatId' in df_msg.columns else 'chatId'
    sample_messages = df_msg[df_msg[id_col].isin(sample_chat_ids)].copy()

    # Add cluster_id for convenience
    # Create mapping: chat_id -> cluster_id
    chat_to_cluster = df_chat.set_index('id')['cluster_id'].to_dict()
    sample_messages['cluster_id'] = sample_messages[id_col].map(chat_to_cluster)

    # Save to CSV
    messages_file = Path(output_dir) / f"{prefix}_messages.csv"
    sample_messages.to_csv(messages_file, index=False, encoding='utf-8-sig')

    print(f"   ✅ {messages_file}")
    print(f"      Messages: {len(sample_messages):,}개 ({len(sample_chat_ids)}개 상담)")

    return messages_file
