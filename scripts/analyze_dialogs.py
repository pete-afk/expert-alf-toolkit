#!/usr/bin/env python3
"""
Dialog Analyzer — 대화유형 분류 + 교차분석 히트맵
====================================================
messages.csv와 tags.xlsx를 읽어 대화유형을 LLM으로 분류하고
클러스터 × 대화유형 교차분석 결과를 생성합니다.

대화유형 7가지:
  1.지식응답   — FAQ, 사용법 문의 ("어떻게", "뭔가요")
  2.정보조회   — 개인 데이터 확인 요청 ("내 주문", "배송 언제")
  3.단순실행   — 직접 처리 요청 ("취소해주세요", "재발송")
  4.정책확인   — 조건부 가능 여부 ("~도 되나요?", "가능한가요?")
  5.조건부실행 — 정책 + 실행 복합 ("~인데 해주세요")
  6.의도불명확 — 짧거나 맥락 참조 발화 ("ㅇㅇ", "네", 이모지만)
  7.상담사전환 — 감정 격화, 분쟁, 특수 상황
발화 추출 전략:
  시간 순으로 최대 6개 메시지(user/manager 합산)를 수집.
  "[고객] ...\n[상담사] ..." 형태로 연결하여 LLM에 전달.

입력:
  {result_dir}/01_clustering/{prefix}_messages.csv
  {result_dir}/01_clustering/{prefix}_tags.xlsx

출력:
  {output_dir}/cross_analysis.json
  {output_dir}/heatmap.png

Usage:
    python3 scripts/analyze_dialogs.py \\
        --messages results/usimsa/01_clustering/usimsa_messages.csv \\
        --tags     results/usimsa/01_clustering/usimsa_tags.xlsx \\
        --output   results/usimsa/05_sales_report

    # 병렬 처리 수 조정 (기본 5)
    python3 scripts/analyze_dialogs.py \\
        --messages results/usimsa/01_clustering/usimsa_messages.csv \\
        --tags     results/usimsa/01_clustering/usimsa_tags.xlsx \\
        --output   results/usimsa/05_sales_report \\
        --workers 3
"""

import os
import json
import argparse
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import numpy as np
from openai import OpenAI


# ─────────────────────── LLM 클라이언트 ──────────────────────────────────── #

def _use_claude():
    """Prism Gateway 경유 Claude API 사용 가능 여부"""
    return bool(os.environ.get("PRISM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))


def _get_upstage_client():
    api_key = os.environ.get("UPSTAGE_API_KEY", "")
    if not api_key:
        raise ValueError("UPSTAGE_API_KEY 환경변수가 설정되지 않았습니다.")
    return OpenAI(api_key=api_key, base_url="https://api.upstage.ai/v1")


def _call_llm(prompt: str, max_tokens: int = 2048) -> str:
    """Prism Gateway 경유 Claude 우선, 없으면 Upstage Solar fallback"""
    if _use_claude():
        import anthropic
        prism_key = os.environ.get("PRISM_API_KEY")
        api_key = prism_key or os.environ["ANTHROPIC_API_KEY"]
        base_url = os.environ.get("PRISM_BASE_URL", "https://prism.ch.dev") if prism_key else None
        client = anthropic.Anthropic(
            api_key=api_key,
            **({"base_url": base_url} if base_url else {})
        )
        model = os.environ.get("ANTHROPIC_MODEL", "anthropic/claude-haiku-4-5-20251001")
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.content[0].text

    client = _get_upstage_client()
    response = client.chat.completions.create(
        model="solar-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


# ─────────────────────────── 상수 ────────────────────────────────────────── #

class DialogType:
    KNOWLEDGE          = "1.지식응답"
    INFO_QUERY         = "2.정보조회"
    SIMPLE_ACTION      = "3.단순실행"
    POLICY_CHECK       = "4.정책확인"
    CONDITIONAL_ACTION = "5.조건부실행"
    UNCLEAR            = "6.의도불명확"
    ESCALATE           = "7.상담사전환"

    ALL = [KNOWLEDGE, INFO_QUERY, SIMPLE_ACTION, POLICY_CHECK, CONDITIONAL_ACTION, UNCLEAR, ESCALATE]

DIALOG_DESCRIPTIONS = """
1.지식응답   : 서비스/상품 정보, 사용법, 절차를 묻는 질문. 예) "어떻게 설치하나요?", "유효기간이 얼마나 되나요?"
2.정보조회   : 고객 본인의 주문·배송·결제 등 개인 데이터 확인 요청. 예) "제 주문 배송이 언제 오나요?", "결제 확인해주세요"
3.단순실행   : 조건 없이 처리를 요청하는 발화. 예) "취소해주세요", "환불 원합니다", "재발송 부탁드려요"
4.정책확인   : 특정 조건에서 가능한지 묻는 질문. 예) "개봉해도 환불되나요?", "해외에서도 사용 가능한가요?"
5.조건부실행 : 정책 확인 + 처리 요청이 결합된 발화. 예) "이미 개봉했는데 환불해주세요", "여행 중인데 유심 교체해주세요"
6.의도불명확 : 너무 짧거나 이전 맥락을 참조해야 파악 가능한 발화. 예) "ㅇㅇ", "네", "그거요", 이모지만 있는 경우
7.상담사전환 : 감정 격화, 법적 분쟁 언급, 즉각적 상담사 연결이 필요한 상황. 예) "정말 화가 나네요", "소비자원에 신고하겠습니다"
"""

CLASSIFY_PROMPT = """당신은 고객 상담 대화를 분류하는 전문가입니다.

아래 {n}개의 대화를 각각 분류하세요.

**분류 기준: 고객이 상담을 시작한 최초 의도**
- 대화 전체가 주어지지만, 반드시 **고객의 첫 번째 발화 또는 상담 초반 의도**를 기준으로 분류하세요.
- 상담이 진행되면서 고객이 "네", "감사합니다" 등 마무리 발화를 해도 무시하세요.
- [상담사] 발화는 고객 의도 파악의 맥락으로만 활용하고, 분류 기준으로 삼지 마세요.

{descriptions}

**판단 팁:**
- 첫 [고객] 발화에 "어떻게", "언제", "왜", "뭔가요" → 주로 1.지식응답 또는 4.정책확인
- 첫 [고객] 발화에 "취소", "환불", "재발송", "해주세요" → 3.단순실행
- 첫 [고객] 발화에 "확인해주세요", "조회해주세요" → 2.정보조회
- 첫 [고객] 발화에 조건("~인데") + 요청("~해주세요") 동시 포함 → 5.조건부실행
- 첫 [고객] 발화가 "네", "안녕하세요", 이모지만 있거나 3단어 이하 → 6.의도불명확

[대화 목록]
{items}

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{"1": "유형", "2": "유형", ...}}

유형 값은 반드시 다음 중 하나: 1.지식응답 / 2.정보조회 / 3.단순실행 / 4.정책확인 / 5.조건부실행 / 6.의도불명확 / 7.상담사전환"""


# ─────────────────────── 첫 발화 추출 ────────────────────────────────────── #

def extract_first_turn(chat_df: pd.DataFrame) -> str:
    """
    chatId별 대화에서 분류용 텍스트 추출.

    전략: 시간 순으로 최대 8개 메시지(user/manager 합산)를 수집하여
    "[고객] ...\n[상담사] ...\n" 형태로 연결.
    빈 메시지(nan, 공백)는 제외하고 카운트.
    """
    msgs = chat_df.sort_values("createdAt")

    parts = []
    for _, row in msgs.iterrows():
        if len(parts) >= 8:
            break

        ptype = str(row.get("personType", "")).lower()
        text  = str(row.get("plainText",  "")).strip()

        if not text or text == "nan":
            continue

        if ptype == "user":
            parts.append(f"[고객] {text[:200]}")
        elif ptype == "manager":
            parts.append(f"[상담사] {text[:200]}")

    return "\n".join(parts)[:600]


def extract_first_turn_user_only(chat_df: pd.DataFrame) -> str:
    """유저 연속 발화만 수집 (첫 상담사 메시지 이전까지)."""
    msgs = chat_df.sort_values("createdAt")
    user_parts    = []
    manager_parts = []
    found_manager = False
    for _, row in msgs.iterrows():
        ptype = str(row.get("personType", "")).lower()
        text  = str(row.get("plainText",  "")).strip()
        if not text or text == "nan":
            continue
        if ptype == "user" and not found_manager:
            user_parts.append(text)
        elif ptype == "manager":
            found_manager = True
            if len(text) > 50:
                manager_parts.append(text)
                break
    user_text = " ".join(user_parts)[:300]
    if len(user_text) < 30 and manager_parts:
        return (user_text + " [상담사 응답] " + manager_parts[0])[:400]
    return user_text


# ─────────────────────── LLM 분류 ────────────────────────────────────────── #

def _parse_type(answer: str) -> str:
    """LLM 응답 문자열에서 유효한 대화유형 추출."""
    for dtype in DialogType.ALL:
        if dtype in answer or answer in dtype:
            return dtype
    for dtype in DialogType.ALL:
        if answer.startswith(dtype[0]):
            return dtype
    return DialogType.UNCLEAR


def classify_chunk(chunk: list, retry: int = 3) -> dict:
    """
    (chat_id, text) 리스트 최대 50건을 한 번의 API 호출로 분류.
    Returns: {chat_id: dialog_type}
    """
    import json as _json

    items_text = "\n".join(
        f"{i+1}: {text[:300]}" for i, (_, text) in enumerate(chunk)
    )
    prompt = CLASSIFY_PROMPT.format(
        n=len(chunk),
        descriptions=DIALOG_DESCRIPTIONS,
        items=items_text,
    )

    for attempt in range(retry):
        try:
            raw = _call_llm(prompt, max_tokens=len(chunk) * 25).strip()

            # JSON 파싱 — 마크다운 코드블록 제거 (Claude가 ```json ... ``` 로 감싸는 경우)
            import re as _re
            json_match = _re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, _re.DOTALL)
            if json_match:
                raw = json_match.group(1)
            elif raw.startswith('{'):
                # 순수 JSON이지만 뒤에 추가 텍스트가 붙은 경우
                brace_count = 0
                for idx, ch in enumerate(raw):
                    if ch == '{': brace_count += 1
                    elif ch == '}': brace_count -= 1
                    if brace_count == 0:
                        raw = raw[:idx+1]
                        break

            parsed = _json.loads(raw)
            result = {}
            for i, (chat_id, _) in enumerate(chunk):
                val = parsed.get(str(i + 1), DialogType.UNCLEAR)
                result[chat_id] = _parse_type(str(val))
            return result

        except Exception as e:
            if attempt < retry - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  ⚠️  청크 분류 실패 ({len(chunk)}건): {e}")
                return {chat_id: DialogType.UNCLEAR for chat_id, _ in chunk}

    return {chat_id: DialogType.UNCLEAR for chat_id, _ in chunk}


def classify_batch(chat_items: list, workers: int = 2, chunk_size: int = 50) -> dict:
    """
    (chat_id, text) 리스트를 chunk_size 단위로 묶어 병렬 분류.
    1000건 / 50 = 20 API 호출, workers=2로 동시 처리.
    Returns: {chat_id: dialog_type}
    """
    llm_label = "Claude" if _use_claude() else "Solar-mini"
    chunks = [chat_items[i:i+chunk_size] for i in range(0, len(chat_items), chunk_size)]
    total_chunks = len(chunks)
    total_items  = len(chat_items)
    results = {}

    print(f"\n🤖 LLM 대화유형 분류 ({llm_label}) — {total_items}건 → {total_chunks}개 청크 (workers={workers}, chunk={chunk_size})\n{'─'*50}")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(classify_chunk, chunk): i for i, chunk in enumerate(chunks)}
        done_chunks = 0
        for future in as_completed(futures):
            chunk_result = future.result()
            results.update(chunk_result)
            done_chunks += 1
            done_items = min(done_chunks * chunk_size, total_items)
            print(f"  청크 {done_chunks}/{total_chunks} 완료 ({done_items}/{total_items}건)...")

    return results


# ─────────────────────── 통계 계산 ───────────────────────────────────────── #

def compute_stats(df: pd.DataFrame) -> dict:
    """
    chatId별 통계 계산.
    Returns: {chat_id: {turns, handling_min, cluster_id}}
    """
    df = df.copy()
    df["createdAt"] = pd.to_datetime(df["createdAt"], errors="coerce")

    stats = {}
    for chat_id, group in df.groupby("chatId"):
        user_turns = (group["personType"] == "user").sum()
        time_range = group["createdAt"].max() - group["createdAt"].min()
        handling_min = time_range.total_seconds() / 60 if pd.notna(time_range) else 0
        cluster_id = group["cluster_id"].iloc[0]

        stats[chat_id] = {
            "turns":        int(user_turns),
            "handling_min": round(handling_min, 1),
            "cluster_id":   int(cluster_id) if pd.notna(cluster_id) else -1,
        }
    return stats


# ─────────────────────── 교차표 생성 ─────────────────────────────────────── #

def build_cross_table(
    chat_types: dict,      # {chat_id: dialog_type}
    chat_stats: dict,      # {chat_id: {cluster_id, turns, handling_min}}
    cluster_labels: dict,  # {cluster_id: label}
) -> dict:
    """
    cluster_id × dialog_type 교차표 + 통계 집계.
    """
    # 클러스터별, 유형별 집계
    cross: dict[int, dict[str, int]] = {}
    cluster_turn_sum:    dict[int, list] = {}
    cluster_time_sum:    dict[int, list] = {}

    for chat_id, dtype in chat_types.items():
        s = chat_stats.get(chat_id, {})
        cid = s.get("cluster_id", -1)

        if cid not in cross:
            cross[cid]            = {t: 0 for t in DialogType.ALL}
            cluster_turn_sum[cid] = []
            cluster_time_sum[cid] = []

        cross[cid][dtype] = cross[cid].get(dtype, 0) + 1
        cluster_turn_sum[cid].append(s.get("turns", 0))
        cluster_time_sum[cid].append(s.get("handling_min", 0))

    # 클러스터 통계
    cluster_stats = {}
    for cid in cross:
        turns = cluster_turn_sum[cid]
        times = cluster_time_sum[cid]
        cluster_stats[cid] = {
            "label":           cluster_labels.get(cid, f"Cluster {cid}"),
            "total_chats":     len(turns),
            "avg_turns":       round(sum(turns) / len(turns), 1) if turns else 0,
            "avg_handling_min": round(sum(times) / len(times), 1) if times else 0,
        }

    # 전체 유형별 합계
    type_totals: dict[str, int] = {t: 0 for t in DialogType.ALL}
    for cid_data in cross.values():
        for dtype, cnt in cid_data.items():
            type_totals[dtype] += cnt

    total_chats = sum(type_totals.values())

    return {
        "total_chats":   total_chats,
        "dialog_types":  DialogType.ALL,
        "type_totals":   type_totals,
        "type_pct":      {t: round(c / total_chats * 100, 1) if total_chats else 0
                          for t, c in type_totals.items()},
        "cross_table":   {str(k): v for k, v in sorted(cross.items())},
        "cluster_stats": {str(k): v for k, v in sorted(cluster_stats.items())},
    }


# ─────────────────────── 토픽 리매핑 ─────────────────────────────────────── #

def remap_to_topics(cross_data: dict, patterns_path: str) -> dict:
    """
    Stage 2 sop_topic_map을 읽어 cluster 기반 cross_data를 topic 기반으로 변환.

    partial 클러스터는 estimated_records 비율로 분배.
    """
    with open(patterns_path, encoding="utf-8") as f:
        patterns = json.load(f)

    topic_map = patterns.get("sop_topic_map", {})
    topics = topic_map.get("topics", [])
    if not topics:
        print("  ⚠️  sop_topic_map이 비어있음 — 클러스터 기준 유지")
        return cross_data

    cross_table    = cross_data["cross_table"]     # {str(cid): {dtype: count}}
    cluster_stats  = cross_data["cluster_stats"]    # {str(cid): {label, total_chats, ...}}

    # cluster_id → 소속 토픽 목록 (비율 포함)
    # 한 클러스터가 여러 토픽에 partial로 배정될 수 있음
    cluster_topic_shares: dict[int, list[tuple[str, str, float]]] = {}  # cid → [(topic_id, title, share)]

    for topic in topics:
        tid   = topic["topic_id"]
        title = topic["title"]
        srcs  = topic.get("source_clusters", [])

        for src in srcs:
            cid = src["cluster_id"]
            if cid not in cluster_topic_shares:
                cluster_topic_shares[cid] = []
            cluster_topic_shares[cid].append((tid, title, topic.get("estimated_records", 0)))

    # share 비율 계산: 같은 cluster를 공유하는 토픽들 사이에서 estimated_records 비율로 분배
    cluster_shares: dict[int, list[tuple[str, str, float]]] = {}
    for cid, entries in cluster_topic_shares.items():
        total_est = sum(e[2] for e in entries)
        if total_est == 0:
            # 균등 분배
            share = 1.0 / len(entries) if entries else 1.0
            cluster_shares[cid] = [(tid, title, share) for tid, title, _ in entries]
        else:
            cluster_shares[cid] = [(tid, title, est / total_est) for tid, title, est in entries]

    # 토픽별 집계
    topic_cross:  dict[str, dict[str, int]]   = {}   # tid → {dtype: count}
    topic_meta:   dict[str, dict]              = {}   # tid → {title, total_chats, ...}

    for topic in topics:
        tid = topic["topic_id"]
        topic_cross[tid] = {t: 0 for t in DialogType.ALL}
        topic_meta[tid]  = {
            "label":           topic["title"],
            "total_chats":     0,
            "avg_turns":       0,
            "avg_handling_min": 0,
            "source_clusters": [s["cluster_id"] for s in topic.get("source_clusters", [])],
        }

    # cross_table의 각 클러스터 데이터를 토픽에 분배
    for cid_str, type_counts in cross_table.items():
        cid = int(cid_str)
        shares = cluster_shares.get(cid)
        if not shares:
            continue  # sop_topic_map에 없는 클러스터 → 무시

        cstats = cluster_stats.get(cid_str, {})
        chats  = cstats.get("total_chats", 0)

        for dtype, cnt in type_counts.items():
            for tid, _, share in shares:
                topic_cross[tid][dtype] = topic_cross[tid].get(dtype, 0) + round(cnt * share)

        for tid, _, share in shares:
            topic_meta[tid]["total_chats"] += round(chats * share)

    # 0건 토픽 제거
    topic_cross = {tid: v for tid, v in topic_cross.items() if sum(v.values()) > 0}

    # 전체 유형별 합계 재계산
    type_totals: dict[str, int] = {t: 0 for t in DialogType.ALL}
    for tc in topic_cross.values():
        for dtype, cnt in tc.items():
            type_totals[dtype] += cnt

    total_chats = sum(type_totals.values())

    result = {
        "total_chats":   total_chats,
        "dialog_types":  DialogType.ALL,
        "type_totals":   type_totals,
        "type_pct":      {t: round(c / total_chats * 100, 1) if total_chats else 0
                          for t, c in type_totals.items()},
        "cross_table":   topic_cross,
        "cluster_stats": {tid: topic_meta.get(tid, {}) for tid in topic_cross},
        "y_axis":        "topic",  # 히트맵이 토픽 기준임을 표시
    }
    print(f"  ✅ sop_topic_map 기반 리매핑 완료: {len(topic_cross)}개 토픽")
    return result


# ─────────────────────── 히트맵 생성 ─────────────────────────────────────── #

def generate_heatmap(cross_data: dict, output_path: Path) -> None:
    """교차분석 히트맵 PNG 생성."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm
    except ImportError:
        print("  ⚠️  matplotlib 없음 — 히트맵 생성 건너뜀 (pip install matplotlib)")
        return

    # 한글 폰트 설정
    for font in ["AppleGothic", "NanumGothic", "Malgun Gothic", "DejaVu Sans"]:
        if any(font.lower() in f.name.lower() for f in fm.fontManager.ttflist):
            plt.rcParams["font.family"] = font
            break
    plt.rcParams["axes.unicode_minus"] = False

    cross_table  = cross_data["cross_table"]
    cluster_stats = cross_data["cluster_stats"]
    dtypes       = cross_data["dialog_types"]
    total        = cross_data["total_chats"]

    # 정렬된 클러스터/토픽 목록
    is_topic = cross_data.get("y_axis") == "topic"
    if is_topic:
        # 토픽 기반: total_chats 내림차순
        sorted_cids = sorted(
            cross_table.keys(),
            key=lambda x: sum(cross_table[x].values()),
            reverse=True,
        )
        row_labels = [
            f"{cluster_stats[cid]['label'][:18]}"
            for cid in sorted_cids
        ]
    else:
        sorted_cids = sorted(cross_table.keys(), key=lambda x: int(x))
        row_labels = [
            f"C{cid}: {cluster_stats[cid]['label'][:15]}"
            for cid in sorted_cids
        ]
    col_labels   = [d.split(".")[1] for d in dtypes]  # 숫자 제거

    # 데이터 행렬 (비율 %)
    n_rows, n_cols = len(sorted_cids), len(dtypes)
    data = np.zeros((n_rows, n_cols))

    for r, cid in enumerate(sorted_cids):
        row_total = sum(cross_table[cid].values())
        for c, dtype in enumerate(dtypes):
            cnt = cross_table[cid].get(dtype, 0)
            data[r, c] = round(cnt / total * 100, 1) if total else 0

    # 행 합계 / 열 합계 추가
    row_sums = data.sum(axis=1, keepdims=True)
    col_sums = data.sum(axis=0, keepdims=True)
    corner   = np.array([[100.0]])
    extended = np.hstack([data, row_sums])
    extended = np.vstack([extended, np.hstack([col_sums, corner])])

    ext_rows = row_labels + ["유형별 합계"]
    ext_cols = col_labels + ["주제별\n합계"]

    # 플롯
    fig_w = max(14, n_cols * 1.8)
    fig_h = max(8,  n_rows * 0.9)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    im = ax.imshow(extended, cmap="YlOrRd", aspect="auto", vmin=0, vmax=max(extended.max(), 1))

    ax.set_xticks(range(len(ext_cols)))
    ax.set_yticks(range(len(ext_rows)))
    ax.set_xticklabels(ext_cols, fontsize=10, fontweight="bold")
    ax.set_yticklabels(ext_rows, fontsize=10)

    # 값 표시
    for i in range(len(ext_rows)):
        for j in range(len(ext_cols)):
            val = extended[i, j]
            if val == 0:
                ax.text(j, i, "–", ha="center", va="center", fontsize=9, color="#cccccc")
                continue
            bold = "bold" if val >= 10 else "normal"
            # 턴/처리시간 부정보
            sub = ""
            if i < n_rows and j < n_cols:
                cid = sorted_cids[i]
                cnt = cross_table[cid].get(dtypes[j], 0)
                if cnt > 0:
                    st = cluster_stats[cid]
                    sub = f"{st['avg_turns']:.1f}턴"
            if sub:
                ax.text(j, i - 0.18, f"{val:.1f}%", ha="center", va="center",
                        fontsize=11, fontweight=bold, color="black")
                ax.text(j, i + 0.22, sub, ha="center", va="center",
                        fontsize=8, color="#444444", alpha=0.85)
            else:
                ax.text(j, i, f"{val:.1f}%", ha="center", va="center",
                        fontsize=11, fontweight=bold, color="black")

    # 구분선
    ax.axhline(y=n_rows - 0.5, color="#333", linewidth=2)
    ax.axvline(x=n_cols - 0.5, color="#333", linewidth=2)

    cbar = fig.colorbar(im, ax=ax, shrink=0.55, pad=0.02)
    cbar.set_label("비율 (%)", fontsize=10)

    y_label = "SOP 토픽" if is_topic else "클러스터"
    ax.set_title(
        f"상담주제 × 대화유형 교차분석\n(전체 {total:,}건 기준 비율% | {y_label} 평균 턴수)",
        fontsize=14, fontweight="bold", pad=15,
    )
    ax.set_ylabel(f"상담주제 ({y_label})", fontsize=10, labelpad=8)
    ax.text(
        0.5, -0.06,
        f"※ 10% 이상 Bold 표시  |  각 셀: 전체 대비 비율% (상단) · {y_label} 평균 턴수 (하단)",
        transform=ax.transAxes, ha="center", fontsize=9, color="#666",
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  ✅ 히트맵 저장: {output_path}")


# ─────────────────────────── Entry point ─────────────────────────────────── #

def main():
    parser = argparse.ArgumentParser(description="대화유형 분류 + 교차분석 히트맵 생성")
    parser.add_argument("--messages", required=True, help="*_messages.csv 경로")
    parser.add_argument("--tags",     required=True, help="*_tags.xlsx 경로")
    parser.add_argument("--output",   required=True, help="출력 디렉토리")
    parser.add_argument("--workers",    type=int,  default=2,     help="LLM 병렬 처리 수 (기본 2)")
    parser.add_argument("--chunk-size", type=int,  default=50,    help="한 번에 분류할 건수 (기본 50)")
    parser.add_argument("--user-only",  action="store_true",      help="유저 발화만 추출 (기본: 6턴 혼합)")
    parser.add_argument("--sample",     type=int,  default=None,  help="테스트용 샘플 수 (기본 전체)")
    parser.add_argument("--patterns",   default=None, help="Stage 2 patterns.json 경로 (sop_topic_map 기반 Y축 집계)")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # API 확인
    if not _use_claude() and not os.environ.get("UPSTAGE_API_KEY"):
        raise ValueError("PRISM_API_KEY (또는 ANTHROPIC_API_KEY) 또는 UPSTAGE_API_KEY 환경변수가 필요합니다.")

    # ── 데이터 로드 ────────────────────────────────────────────────────────── #
    print(f"\n📂 데이터 로드 중...")
    msgs_df = pd.read_csv(args.messages)
    tags_df = pd.read_excel(args.tags)

    print(f"  messages: {len(msgs_df):,}행 / {msgs_df['chatId'].nunique():,}건")
    print(f"  tags:     {len(tags_df)}개 클러스터")

    cluster_labels = dict(zip(
        tags_df["cluster_id"].astype(int),
        tags_df["label"].astype(str)
    ))

    # ── 첫 발화 추출 ──────────────────────────────────────────────────────── #
    mode_label = "유저 발화만" if args.user_only else "6턴 혼합"
    print(f"\n📝 첫 발화 추출 중... [{mode_label}]")
    chat_items = []
    for chat_id, group in msgs_df.groupby("chatId"):
        text = extract_first_turn_user_only(group) if args.user_only else extract_first_turn(group)
        if text:
            chat_items.append((chat_id, text))

    if args.sample:
        import random
        random.shuffle(chat_items)
        chat_items = chat_items[:args.sample]
        print(f"  샘플링: {len(chat_items)}건")
    else:
        print(f"  추출 완료: {len(chat_items)}건")

    # ── LLM 분류 ──────────────────────────────────────────────────────────── #
    chat_types = classify_batch(chat_items, workers=args.workers, chunk_size=args.chunk_size)

    # 분류 결과 요약
    from collections import Counter
    type_counts = Counter(chat_types.values())
    print(f"\n📊 대화유형 분류 결과:")
    for dtype in DialogType.ALL:
        cnt = type_counts.get(dtype, 0)
        pct = cnt / len(chat_types) * 100 if chat_types else 0
        print(f"  {dtype}: {cnt}건 ({pct:.1f}%)")

    # ── 통계 계산 ──────────────────────────────────────────────────────────── #
    print(f"\n📐 통계 계산 중...")
    chat_stats = compute_stats(msgs_df[msgs_df["chatId"].isin(dict(chat_items))])

    # ── 교차표 생성 ────────────────────────────────────────────────────────── #
    cross_data = build_cross_table(chat_types, chat_stats, cluster_labels)

    # ── 토픽 리매핑 (--patterns 지정 시) ────────────────────────────────────── #
    if args.patterns:
        patterns_path = Path(args.patterns)
        if patterns_path.exists():
            print(f"\n🔄 Stage 2 sop_topic_map 기반 리매핑 중...")
            cross_data = remap_to_topics(cross_data, str(patterns_path))
        else:
            print(f"  ⚠️  patterns.json 없음: {patterns_path} — 클러스터 기준 유지")

    # ── JSON 저장 ──────────────────────────────────────────────────────────── #
    json_path = output_dir / "cross_analysis.json"
    json_path.write_text(
        json.dumps(cross_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"  ✅ cross_analysis.json 저장: {json_path}")

    # ── 히트맵 생성 ────────────────────────────────────────────────────────── #
    print(f"\n🎨 히트맵 생성 중...")
    generate_heatmap(cross_data, output_dir / "heatmap.png")

    # ── 완료 ──────────────────────────────────────────────────────────────── #
    total = cross_data["total_chats"]
    print(f"\n{'─'*50}")
    print(f"✅ 분석 완료 — {total}건")
    print(f"   {json_path}")
    print(f"   {output_dir / 'heatmap.png'}")

    # 핵심 인사이트
    type_pct = cross_data["type_pct"]
    rag_pct  = type_pct.get(DialogType.KNOWLEDGE, 0) + type_pct.get(DialogType.POLICY_CHECK, 0)
    task_pct = type_pct.get(DialogType.INFO_QUERY, 0) + type_pct.get(DialogType.SIMPLE_ACTION, 0) + type_pct.get(DialogType.CONDITIONAL_ACTION, 0)
    esc_pct  = type_pct.get(DialogType.ESCALATE, 0)

    print(f"\n💡 자동화 가능성 요약:")
    print(f"   RAG 대상   (지식응답+정책확인): {rag_pct:.1f}%  → Phase 1 즉시 배포 가능")
    print(f"   Task 대상  (정보조회+실행류):   {task_pct:.1f}%  → Phase 2 API 연동 필요")
    print(f"   상담사 필수 (상담사전환):       {esc_pct:.1f}%  → 자동화 불가\n")


if __name__ == "__main__":
    main()
