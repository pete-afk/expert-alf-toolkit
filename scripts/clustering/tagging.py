import pandas as pd
import json
from openai import OpenAI
from ..config import (
    UPSTAGE_API_KEY,
    UPSTAGE_BASE_URL,
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_SAMPLES_PER_CLUSTER
)
from ..lang_config import L


def _get_upstage_client():
    return OpenAI(api_key=UPSTAGE_API_KEY, base_url=UPSTAGE_BASE_URL)


def _call_upstage(prompt, llm_model=None):
    client = _get_upstage_client()
    model = llm_model or LLM_MODEL
    print(f"   LLM: Solar ({model})")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=LLM_TEMPERATURE or 0.3
    )
    return response.choices[0].message.content


def _call_llm(prompt, llm_model=None):
    """Claude 우선, 실패 또는 키 없으면 Upstage fallback"""
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            client = anthropic.Anthropic()
            model = llm_model or ANTHROPIC_MODEL
            print(f"   LLM: Claude ({model})")
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
                temperature=LLM_TEMPERATURE or 0.3
            )
            return response.content[0].text
        except Exception as e:
            print(f"   ⚠️  Claude 실패 ({type(e).__name__}), Solar로 fallback")

    return _call_upstage(prompt, llm_model)

# ───────────────────────────────────────────────────────────── #
# 실제 대화 메시지 추출
# ───────────────────────────────────────────────────────────── #

def _get_conversation_samples(df_chat_cluster, df_msg, samples_per_cluster, max_turns=8, max_chars=150):
    """
    클러스터 내 샘플 상담건의 실제 대화를 추출한다.

    Args:
        df_chat_cluster: 해당 클러스터의 df_chat 슬라이스
        df_msg: 전체 Message 데이터프레임 (chatId, plainText, createdAt)
        samples_per_cluster: 샘플 상담 건수
        max_turns: 상담 1건당 최대 메시지 수
        max_chars: 메시지 1개당 최대 문자수

    Returns:
        list[str]: 포맷된 대화 문자열 목록
    """
    sampled_ids = df_chat_cluster['id'].dropna().head(samples_per_cluster).tolist()
    conversations = []

    for chat_id in sampled_ids:
        msgs = df_msg[df_msg['chatId'] == chat_id].sort_values('createdAt')
        if msgs.empty:
            continue

        lines = []
        for _, row in msgs.head(max_turns).iterrows():
            text = str(row.get('plainText', '')).strip()
            if not text or text.lower() in ('nan', 'none', ''):
                continue
            lines.append(f"  - {text[:max_chars]}")

        if lines:
            conversations.append("\n".join(lines))

    return conversations


# ───────────────────────────────────────────────────────────── #
# 공개 인터페이스
# ───────────────────────────────────────────────────────────── #

def tag_clusters(df, df_msg=None, mode='agent', llm_model=None, samples_per_cluster=None):
    """
    Args:
        df: cluster_id 컬럼이 포함된 df_chat
        df_msg: Message 데이터프레임 (제공 시 실제 대화 내용으로 태깅, 미제공 시 enhanced_text 사용)
        mode: 'agent' (Solar-pro 통합 분석) | 'api' (Solar-mini 개별 분석)
    """
    if mode == 'agent':
        return _tag_with_agent(df, df_msg, llm_model, samples_per_cluster)
    else:
        return _tag_with_api(df, df_msg, llm_model, samples_per_cluster)


# ───────────────────────────────────────────────────────────── #
# API 방식 (개별 클러스터 순차 호출)
# ───────────────────────────────────────────────────────────── #

def _tag_with_api(df, df_msg=None, llm_model=None, samples_per_cluster=None):
    if samples_per_cluster is None:
        samples_per_cluster = LLM_SAMPLES_PER_CLUSTER

    cluster_tags = []

    for cluster_id in sorted(df['cluster_id'].unique()):
        cluster_df = df[df['cluster_id'] == cluster_id]

        if df_msg is not None:
            samples = _get_conversation_samples(cluster_df, df_msg, samples_per_cluster)
        else:
            samples = cluster_df['enhanced_text'].dropna().head(samples_per_cluster).tolist()

        if len(samples) == 0:
            cluster_tags.append({
                'cluster_id': cluster_id,
                'cluster_size': len(cluster_df),
                'label': L.tagging.empty_label,
                'category': L.tagging.empty_category,
                'keywords': L.tagging.empty_keywords.split(', '),
            })
            print(f"  ℹ️  {L.tagging.empty_log.format(cluster_id=cluster_id, size=len(cluster_df))}")
            continue

        sample_text = "\n\n".join([
            f"{L.tagging.conv_block_header.format(i=i+1)}\n{conv}"
            for i, conv in enumerate(samples)
        ])
        source_label = L.tagging.source_real_short if df_msg is not None else L.tagging.source_summary

        prompt = L.tagging.api_prompt.format(
            source_label=source_label,
            cluster_size=len(cluster_df),
            n_samples=len(samples),
            sample_text=sample_text,
            label_instruction=L.tagging.label_instruction,
        )

        try:
            result_text = _call_llm(prompt, llm_model)
            result_json = json.loads(result_text)
            cluster_tags.append({
                'cluster_id': cluster_id,
                'cluster_size': len(cluster_df),
                'label': result_json.get('label', L.tagging.default_label.format(cluster_id=cluster_id)),
                'category': result_json.get('category', L.tagging.default_category),
                'keywords': ', '.join(result_json.get('keywords', [])),
            })
        except Exception:
            cluster_tags.append({
                'cluster_id': cluster_id,
                'cluster_size': len(cluster_df),
                'label': L.tagging.default_label.format(cluster_id=cluster_id),
                'category': L.tagging.default_category,
                'keywords': '',
            })

    return pd.DataFrame(cluster_tags)


# ───────────────────────────────────────────────────────────── #
# Agent 방식 (전체 클러스터 일괄 분석)
# ───────────────────────────────────────────────────────────── #

def _tag_with_agent(df, df_msg=None, llm_model=None, samples_per_cluster=None):
    if samples_per_cluster is None:
        samples_per_cluster = LLM_SAMPLES_PER_CLUSTER

    cluster_summaries = []
    empty_cluster_tags = []

    source_label = L.tagging.source_real if df_msg is not None else L.tagging.source_summary

    for cluster_id in sorted(df['cluster_id'].unique()):
        cluster_df = df[df['cluster_id'] == cluster_id]

        # 실제 대화 또는 enhanced_text 중 선택
        if df_msg is not None:
            samples = _get_conversation_samples(cluster_df, df_msg, samples_per_cluster)
        else:
            raw = cluster_df['enhanced_text'].dropna().head(samples_per_cluster).tolist()
            samples = [f"  - {text[:150]}" for text in raw]

        if len(samples) == 0:
            empty_cluster_tags.append({
                'cluster_id': cluster_id,
                'cluster_size': len(cluster_df),
                'label': L.tagging.empty_label,
                'category': L.tagging.empty_category,
                'keywords': L.tagging.empty_keywords,
            })
            print(f"  ℹ️  {L.tagging.empty_log.format(cluster_id=cluster_id, size=len(cluster_df))}")
            continue

        if df_msg is not None:
            conv_blocks = "\n\n".join([
                f"  {L.tagging.conv_block_header.format(i=i+1)}\n{conv}"
                for i, conv in enumerate(samples[:10])
            ])
        else:
            conv_blocks = "\n".join(samples[:10])

        cluster_summaries.append(
            f"\n{L.tagging.cluster_block_header.format(cluster_id=cluster_id, size=len(cluster_df))}\n{conv_blocks}\n"
        )

    if len(cluster_summaries) == 0:
        return pd.DataFrame(empty_cluster_tags)

    all_clusters_text = "\n".join(cluster_summaries)

    prompt = L.tagging.agent_prompt.format(
        source_label=source_label,
        all_clusters_text=all_clusters_text,
    )

    try:
        result_text = _call_llm(prompt, llm_model).strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()

        result_json = json.loads(result_text)

        if empty_cluster_tags:
            result_json.extend(empty_cluster_tags)

        tags_df = pd.DataFrame(result_json)
        tags_df = tags_df.sort_values('cluster_id').reset_index(drop=True)
        return tags_df

    except Exception as e:
        print(f"\n⚠️  {L.tagging.agent_fallback_log.format(error=e)}")
        return _tag_with_api(df, df_msg, llm_model, samples_per_cluster)
