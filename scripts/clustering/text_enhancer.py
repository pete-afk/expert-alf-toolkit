import pandas as pd
from tqdm import tqdm
from ..config import (
    TEXT_STRATEGY_MIN_SUMMARY_LENGTH,
    TEXT_STRATEGY_MIN_FIRST_MSG_LENGTH
)


def enhance_text(df_chat, df_msg):
    """
    텍스트 향상 전략 (개선된 fallback)

    전략:
    1. summarizedMessage ≥50자 → 사용
    2. first_message 있으면 → 사용 (길이 무관)
    3. 첫 유저 메시지 → 사용 (길이 무관)

    3_turns 결합 제거 (형식 차이 최소화)
    """
    enhanced_texts = []
    strategy_used = []

    for idx, row in tqdm(df_chat.iterrows(), total=len(df_chat), desc="   Processing"):
        chat_id = row['id']
        raw_summary = row.get('summarizedMessage', None)

        # 1. summarizedMessage 우선
        if pd.notna(raw_summary) and len(str(raw_summary)) >= TEXT_STRATEGY_MIN_SUMMARY_LENGTH:
            enhanced_texts.append(str(raw_summary))
            strategy_used.append('summary')
        else:
            # 메시지 가져오기
            messages = df_msg[df_msg['chatId'] == chat_id]['plainText'].astype(str).tolist()

            if len(messages) == 0:
                # 메시지 없음 → 빈 문자열
                enhanced_texts.append(str(raw_summary) if pd.notna(raw_summary) else '')
                strategy_used.append('empty')
            else:
                # 2. 첫 메시지 사용 (길이 무관)
                # 형식 통일을 위해 3_turns 결합 대신 first_message 사용
                first_msg = str(messages[0])

                if len(first_msg) >= TEXT_STRATEGY_MIN_FIRST_MSG_LENGTH:
                    # 첫 메시지가 충분히 긴 경우
                    enhanced_texts.append(first_msg)
                    strategy_used.append('first_msg')
                else:
                    # 첫 메시지가 짧아도 사용 (3_turns 결합보다 형식 일관성 중요)
                    # 단, 너무 짧으면 (5자 미만) 두 번째 메시지도 결합
                    if len(first_msg) < 5 and len(messages) > 1:
                        second_msg = str(messages[1])
                        combined = f"{first_msg} {second_msg}"
                        enhanced_texts.append(combined)
                        strategy_used.append('first_two')
                    else:
                        enhanced_texts.append(first_msg)
                        strategy_used.append('first_msg_short')

    df_chat['enhanced_text'] = enhanced_texts
    df_chat['text_strategy'] = strategy_used

    # 전략별 분포 출력
    strategy_dist = df_chat['text_strategy'].value_counts()
    print(f"   전략 분포: {dict(strategy_dist)}")

    return df_chat
