import pandas as pd
from tqdm import tqdm


def load_data(filepath, sample_size=None):
    """
    Excel 파일에서 UserChat 및 Message 데이터 로딩

    Args:
        filepath: Excel 파일 경로
        sample_size: 샘플링 크기 (None이면 전체 데이터)

    샘플링 전략 (sample_size 지정 시):
        - first_message 길이 기준으로 정렬 (긴 것 우선)
        - 상위 sample_size개 선택
        - 형식 일관성 향상 (first_msg_short 최소화)
    """
    print(f"   Excel 로딩 중... ({filepath})")
    xl = pd.ExcelFile(filepath)
    chat_sheet = 'UserChat data' if 'UserChat data' in xl.sheet_names else 'UserChat'
    df_chat = pd.read_excel(xl, sheet_name=chat_sheet)
    df_msg = pd.read_excel(xl, sheet_name='Message data')

    print(f"   원본: UserChat {len(df_chat):,}건, Message {len(df_msg):,}건")

    if sample_size and sample_size < len(df_chat):
        print(f"   샘플링 전략: first_message 길이 기준 정렬")

        # 각 상담 건의 first_message 길이 계산
        first_msg_lengths = []
        for _, row in tqdm(df_chat.iterrows(), total=len(df_chat), desc="   분석 중", leave=False):
            chat_id = row['id']
            messages = df_msg[df_msg['chatId'] == chat_id]['plainText'].tolist()

            if messages and len(messages) > 0:
                first_msg = str(messages[0])
                first_msg_lengths.append(len(first_msg))
            else:
                first_msg_lengths.append(0)

        df_chat['first_msg_len'] = first_msg_lengths

        # first_message 긴 것 우선 정렬
        df_chat_sorted = df_chat.sort_values('first_msg_len', ascending=False)

        # 상위 sample_size개 선택
        df_chat = df_chat_sorted.head(sample_size).copy()

        # first_msg_len 컬럼 제거
        df_chat = df_chat.drop(columns=['first_msg_len'])

        print(f"   샘플링 완료: {len(df_chat):,}건 (긴 first_message 우선)")

        # 선택된 chat_id에 해당하는 메시지만 필터링
        chat_ids = df_chat['id'].tolist()
        df_msg = df_msg[df_msg['chatId'].isin(chat_ids)].copy()

    # 메시지 시간순 정렬
    df_msg = df_msg.sort_values(['chatId', 'createdAt'])

    return df_chat, df_msg
