#!/usr/bin/env python3
"""
Bot Analyzer — Non-ALF 봇 행동 분석
=====================================
messages.csv 또는 원본 Excel 파일에서 non-ALF 봇 메시지를 추출하고
봇 유형, 커버리지, 에스컬레이션 패턴, admin 연동을 분석합니다.

분석 항목:
  1. 봇 유형 분류 (AI Chatbot / Linker / Summarizer / Error)
  2. 커버리지 (봇 관여율, 첫 응답자 비율, 자체 해결률)
  3. 에스컬레이션 분석 (매니저 전환 비율, 턴 수, 실패 패턴)
  4. Bot-only 대화 해결 유형
  5. 에스컬레이션 토픽 분포
  6. Admin 연동 탐지

입력:
  --messages  {result_dir}/01_clustering/{prefix}_messages.csv
  --excel     원본 Excel (Message data 시트)
  --tags      (선택) {result_dir}/01_clustering/{prefix}_tags.xlsx

출력:
  {output_dir}/bot_analysis.json
  {output_dir}/bot_analysis_report.md

Usage:
    # CSV 입력
    python3 scripts/analyze_bots.py \\
        --messages results/pamesthetic/01_clustering/pamesthetic_messages.csv \\
        --output results/pamesthetic/bot_analysis

    # Excel 직접 입력
    python3 scripts/analyze_bots.py \\
        --excel "data/낫포유 90일 상담 데이터.xlsx" \\
        --output results/notforyou/bot_analysis
"""

import re
import json
import argparse
import statistics
from pathlib import Path
from datetime import date
from collections import Counter

import pandas as pd


# ─────────────── Constants ──────────────────────────────────────────────── #

ALF_PREFIX = "ALF"
JSON_INDENT = 2
OUTPUT_JSON = "bot_analysis.json"
OUTPUT_MD = "bot_analysis_report.md"


class BotType:
    LINKER = "conversation_linker"
    SUMMARIZER = "conversation_summary"
    AI_CHATBOT = "ai_chatbot"
    ERROR = "error_fallback"
    UNKNOWN = "unknown"

    LABELS = {
        "conversation_linker": "Conversation Linker (기존 상담 연결)",
        "conversation_summary": "Conversation Summary (상담 요약)",
        "ai_chatbot": "AI Chatbot (고객 대면 챗봇)",
        "error_fallback": "Error Fallback (장애 안내)",
        "unknown": "Unknown",
    }


# Bot classification patterns (message content based, company-agnostic)
LINKER_PATTERN = re.compile(r"📌\s*기존 상담|desk\.channel\.io/.*user-chats/")
ERROR_PATTERN = re.compile(r"일시적인 문제가 생겨|시스템.*오류.*답변.*어렵")
SUMMARIZER_INDICATORS = [
    re.compile(r"^(요약|주제|피드백|상담 내역)"),
    re.compile(r"^-\s+.{5,50}\n-\s+"),  # bullet-point style summaries
]

# Admin integration detection patterns
ADMIN_PATTERNS = {
    "member_lookup": re.compile(r"회원.*조회|회원.*확인|전화번호.*확인|정보.*확인이 어려운"),
    "order_data": re.compile(r"주문번호|주문.*확인|주문.*조회|품절|재고|입고"),
    "supporter_account": re.compile(r"서포터.*변경|서포터.*아이디|서포터.*조회|아이디.*조회"),
    "conversation_history": re.compile(r"desk\.channel\.io|기존 상담"),
    "delivery_tracking": re.compile(r"배송.*기사|송장.*번호|배송.*완료.*확인"),
    "coupon_system": re.compile(r"쿠폰.*발급|쿠폰.*확인|적립금.*확인"),
    "specific_data": re.compile(
        r"\d{3}-\d{3,4}-\d{4}"  # phone numbers
        r"|[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]+"  # emails
    ),
}

# Bot-only resolution type patterns
RESOLUTION_PATTERNS = {
    "영업시간외_안내": re.compile(r"영업시간.*종료|영업시간.*순차"),
    "지식응답_제품안내": re.compile(r"성분|사용법|보관|변색|살리실산|pH|사용.*방법|제품.*특성"),
    "단순인사_감사": re.compile(r"감사합니다|좋은 하루|편안한|반갑습니다|기분 좋은"),
    "매니저연결_안내후종료": re.compile(r"담당 매니저.*연결|매니저.*연결|상담원.*연결"),
    "정보수집후_미응답": re.compile(r"정보를 부탁|확인.*위해.*부탁|알려주시|부탁드"),
}

# Escalation topic patterns (based on user messages)
ESCALATION_TOPIC_PATTERNS = {
    "교환_환불": re.compile(r"교환|환불|반품|취소|반송"),
    "주문_배송": re.compile(r"배송|택배|송장|출고|수령|주문"),
    "쿠폰_적립금": re.compile(r"쿠폰|적립금|할인|포인트|코드"),
    "회원_계정": re.compile(r"아이디|회원|가입|탈퇴|비밀번호|로그인"),
    "제품문의": re.compile(r"성분|사용|제품|바디|미스트|로션|샤워|앰플"),
}

# Failure pattern detection
FAILURE_PATTERNS = {
    "정보확인_불가_반복": re.compile(r"정보.*확인이 어려운|확인이 되지 않|조회되지 않"),
    "매니저_위임": re.compile(r"담당 매니저가 도와드려야|매니저.*확인이 필요|시스템 확인이 필요"),
    "반복_안내": re.compile(r"다시 한 번.*확인|다시.*확인.*부탁"),
}


# ─────────────── Data Loading ───────────────────────────────────────────── #

def load_messages(args) -> pd.DataFrame:
    """Load messages from CSV or Excel."""
    if args.messages:
        df = pd.read_csv(args.messages)
    elif args.excel:
        df = pd.read_excel(args.excel, sheet_name="Message data")
    else:
        raise ValueError("--messages or --excel required")

    # Ensure consistent column names
    if "userChatId" in df.columns and "chatId" not in df.columns:
        df = df.rename(columns={"userChatId": "chatId"})

    return df


def load_tags(tags_path: str) -> dict:
    """Load cluster tags mapping. Returns {cluster_id: label}."""
    if not tags_path or not Path(tags_path).exists():
        return {}
    df = pd.read_excel(tags_path)
    return dict(zip(df["cluster_id"], df["label"]))


# ─────────────── Bot Classification ─────────────────────────────────────── #

def classify_bot_type(messages: list[str]) -> str:
    """Classify a bot by its message content patterns."""
    combined = "\n".join(messages)

    if LINKER_PATTERN.search(combined):
        return BotType.LINKER

    if ERROR_PATTERN.search(combined):
        return BotType.ERROR

    # Summarizer: structured, short, non-conversational
    summarizer_score = 0
    for pattern in SUMMARIZER_INDICATORS:
        if any(pattern.search(m) for m in messages):
            summarizer_score += 1
    avg_len = statistics.mean(len(m) for m in messages) if messages else 0
    if summarizer_score >= 1 and avg_len < 200 and not any("안녕하세요" in m for m in messages):
        return BotType.SUMMARIZER

    # Default: AI chatbot (conversational)
    if any("안녕하세요" in m or "고객님" in m for m in messages):
        return BotType.AI_CHATBOT

    return BotType.UNKNOWN


def classify_all_bots(df_bot: pd.DataFrame) -> dict:
    """Classify each unique bot personId. Returns {personId: bot_type}."""
    result = {}
    for pid, group in df_bot.groupby("personId"):
        messages = group["plainText"].fillna("").tolist()
        result[str(pid)] = classify_bot_type(messages)
    return result


# ─────────────── Coverage Analysis ──────────────────────────────────────── #

def analyze_coverage(df: pd.DataFrame, df_bot: pd.DataFrame) -> dict:
    """Analyze bot coverage across all conversations."""
    total_chats = df["chatId"].nunique()
    bot_chats = df_bot["chatId"].unique()
    bot_chat_count = len(bot_chats)

    # First responder analysis
    first_responder_count = 0
    for cid in bot_chats:
        conv = df[df["chatId"] == cid].sort_values("createdAt")
        non_user = conv[conv["personType"] != "user"]
        if len(non_user) > 0 and non_user.iloc[0]["personType"] == "bot":
            first_responder_count += 1

    # Bot-only (no manager) vs escalated
    bot_only = 0
    escalated = 0
    for cid in bot_chats:
        conv = df[df["chatId"] == cid]
        if "manager" not in conv["personType"].values:
            bot_only += 1
        else:
            escalated += 1

    return {
        "total_conversations": total_chats,
        "bot_involved_conversations": bot_chat_count,
        "bot_involvement_rate_pct": round(bot_chat_count / total_chats * 100, 1) if total_chats else 0,
        "bot_first_responder": first_responder_count,
        "bot_first_responder_rate_pct": round(first_responder_count / bot_chat_count * 100, 1) if bot_chat_count else 0,
        "bot_only_conversations": bot_only,
        "bot_only_rate_pct": round(bot_only / bot_chat_count * 100, 1) if bot_chat_count else 0,
        "escalated_to_manager": escalated,
        "escalation_rate_pct": round(escalated / bot_chat_count * 100, 1) if bot_chat_count else 0,
    }


# ─────────────── Escalation Analysis ───────────────────────────────────── #

def analyze_escalation(df: pd.DataFrame, df_bot: pd.DataFrame) -> dict:
    """Analyze escalation patterns for AI chatbot conversations."""
    bot_chats = df_bot["chatId"].unique()
    turns_before_manager = []
    failure_counts = Counter()

    for cid in bot_chats:
        conv = df[df["chatId"] == cid].sort_values("createdAt")
        types = conv["personType"].tolist()

        if "manager" in types:
            first_mgr_idx = types.index("manager")
            bot_before = sum(1 for t in types[:first_mgr_idx] if t == "bot")
            turns_before_manager.append(bot_before)

    # Failure pattern detection across all bot messages
    bot_texts = df_bot["plainText"].fillna("")
    for pattern_name, pattern in FAILURE_PATTERNS.items():
        count = bot_texts.str.contains(pattern).sum()
        if count > 0:
            failure_counts[pattern_name] = int(count)

    # Bot turn count stats
    all_bot_turns = []
    for cid in bot_chats:
        conv = df[df["chatId"] == cid]
        bot_turns = (conv["personType"] == "bot").sum()
        all_bot_turns.append(bot_turns)

    result = {
        "bot_turn_stats": {
            "avg": round(statistics.mean(all_bot_turns), 1) if all_bot_turns else 0,
            "median": round(statistics.median(all_bot_turns), 1) if all_bot_turns else 0,
            "max": max(all_bot_turns) if all_bot_turns else 0,
            "min": min(all_bot_turns) if all_bot_turns else 0,
        },
        "failure_patterns": dict(failure_counts.most_common()),
    }

    if turns_before_manager:
        turn_dist = Counter(turns_before_manager)
        result["turns_before_manager"] = {
            "avg": round(statistics.mean(turns_before_manager), 1),
            "median": round(statistics.median(turns_before_manager), 1),
            "distribution": dict(sorted(turn_dist.items())),
        }

    return result


# ─────────────── Bot-Only Resolution Types ──────────────────────────────── #

def classify_bot_only_resolutions(df: pd.DataFrame, df_bot: pd.DataFrame) -> dict:
    """Classify how bot-only conversations were resolved."""
    bot_chats = df_bot["chatId"].unique()
    bot_only_chats = [
        cid for cid in bot_chats
        if "manager" not in df[df["chatId"] == cid]["personType"].values
    ]

    resolution_counts = Counter()
    for cid in bot_only_chats:
        conv = df[df["chatId"] == cid].sort_values("createdAt")
        bot_texts = " ".join(conv[conv["personType"] == "bot"]["plainText"].fillna("").tolist())
        user_count = (conv["personType"] == "user").sum()

        classified = False
        for res_type, pattern in RESOLUTION_PATTERNS.items():
            if pattern.search(bot_texts):
                # Special handling: "매니저연결" only if short conversation
                if res_type == "매니저연결_안내후종료" and len(conv) > 4:
                    continue
                # "정보수집후_미응답" only if user sent few messages
                if res_type == "정보수집후_미응답" and user_count > 2:
                    continue
                # "단순인사_감사" only if short conversation
                if res_type == "단순인사_감사" and len(conv) > 3:
                    continue
                resolution_counts[res_type] += 1
                classified = True
                break

        if not classified:
            resolution_counts["기타"] += 1

    total = len(bot_only_chats)
    return {
        "total_bot_only": total,
        "types": {
            k: {"count": v, "pct": round(v / total * 100, 1) if total else 0}
            for k, v in resolution_counts.most_common()
        },
    }


# ─────────────── Escalation Topic Classification ───────────────────────── #

def classify_escalation_topics(df: pd.DataFrame, df_bot: pd.DataFrame) -> dict:
    """Classify topics of conversations escalated to managers."""
    bot_chats = df_bot["chatId"].unique()
    escalated_chats = [
        cid for cid in bot_chats
        if "manager" in df[df["chatId"] == cid]["personType"].values
    ]

    topic_counts = Counter()
    for cid in escalated_chats:
        conv = df[df["chatId"] == cid]
        user_texts = " ".join(conv[conv["personType"] == "user"]["plainText"].fillna("").tolist())

        classified = False
        for topic, pattern in ESCALATION_TOPIC_PATTERNS.items():
            if pattern.search(user_texts):
                topic_counts[topic] += 1
                classified = True
                break

        if not classified:
            topic_counts["기타"] += 1

    total = len(escalated_chats)
    return {
        "total_escalated": total,
        "topics": {
            k: {"count": v, "pct": round(v / total * 100, 1) if total else 0}
            for k, v in topic_counts.most_common()
        },
    }


# ─────────────── Admin Integration Detection ───────────────────────────── #

def detect_admin_integration(df_bot: pd.DataFrame) -> dict:
    """Detect admin/backend system integration signals in bot messages."""
    results = {}
    for name, pattern in ADMIN_PATTERNS.items():
        matches = df_bot[df_bot["plainText"].fillna("").str.contains(pattern)]
        if len(matches) > 0:
            # Collect evidence samples
            samples = []
            for _, row in matches.head(3).iterrows():
                text = str(row["plainText"])
                m = pattern.search(text)
                if m:
                    start = max(0, m.start() - 40)
                    end = min(len(text), m.end() + 40)
                    samples.append(f"...{text[start:end]}...")

            results[name] = {
                "count": int(len(matches)),
                "bot_ids": sorted(matches["personId"].astype(str).unique().tolist()),
                "evidence_samples": samples,
            }

    return results


# ─────────────── Topic Distribution (cluster-based) ─────────────────────── #

def analyze_topic_distribution(df: pd.DataFrame, df_bot: pd.DataFrame, tags: dict) -> dict:
    """Map bot conversations to clusters for topic distribution."""
    if "cluster_id" not in df.columns or not tags:
        return {}

    bot_chats = df_bot["chatId"].unique()
    cluster_counts = Counter()
    for cid in bot_chats:
        conv = df[df["chatId"] == cid]
        cid_clusters = conv["cluster_id"].dropna().unique()
        for c in cid_clusters:
            label = tags.get(int(c), f"cluster_{int(c)}")
            cluster_counts[label] += 1

    total = sum(cluster_counts.values())
    return {
        k: {"count": v, "pct": round(v / total * 100, 1) if total else 0}
        for k, v in cluster_counts.most_common()
    }


# ─────────────── Report Generation ──────────────────────────────────────── #

def generate_report(results: dict) -> str:
    """Generate human-readable Markdown report."""
    lines = []
    r = results

    lines.append(f"# Bot 분석 보고서")
    lines.append(f"")
    lines.append(f"- 분석일: {r['metadata']['analysis_date']}")
    lines.append(f"- 소스: `{r['metadata']['source']}`")
    lines.append(f"- 전체 메시지: {r['metadata']['total_messages']:,}건")
    lines.append(f"- Bot 메시지: {r['metadata']['bot_messages_total']}건 (ALF: {r['metadata']['alf_messages']}건, Non-ALF: {r['metadata']['non_alf_bot_messages']}건)")
    lines.append("")

    # Bot Types
    lines.append("## 1. 봇 유형 분류")
    lines.append("")
    lines.append("| personId | 유형 | 메시지 수 | 대화 수 |")
    lines.append("|----------|------|----------|---------|")
    for bot in r["bot_types"]:
        label = BotType.LABELS.get(bot["bot_type"], bot["bot_type"])
        lines.append(f"| {bot['person_id']} | {label} | {bot['message_count']} | {bot['conversation_count']} |")
    lines.append("")

    # Coverage
    cov = r["coverage"]
    lines.append("## 2. 커버리지")
    lines.append("")
    lines.append(f"| 지표 | 값 |")
    lines.append(f"|------|-----|")
    lines.append(f"| 전체 대화 | {cov['total_conversations']}건 |")
    lines.append(f"| Bot 관여 대화 | {cov['bot_involved_conversations']}건 ({cov['bot_involvement_rate_pct']}%) |")
    lines.append(f"| Bot 첫 응답자 | {cov['bot_first_responder']}건 ({cov['bot_first_responder_rate_pct']}%) |")
    lines.append(f"| Bot-only (매니저 없이 종료) | {cov['bot_only_conversations']}건 ({cov['bot_only_rate_pct']}%) |")
    lines.append(f"| 매니저 에스컬레이션 | {cov['escalated_to_manager']}건 ({cov['escalation_rate_pct']}%) |")
    lines.append("")

    # Escalation Analysis
    esc = r["escalation"]
    lines.append("## 3. 에스컬레이션 분석")
    lines.append("")
    ts = esc["bot_turn_stats"]
    lines.append(f"**Bot 턴 수**: 평균 {ts['avg']}회, 중앙값 {ts['median']}회, 최대 {ts['max']}회")
    lines.append("")

    if "turns_before_manager" in esc:
        tbm = esc["turns_before_manager"]
        lines.append(f"**매니저 전환 전 Bot 턴**: 평균 {tbm['avg']}회, 중앙값 {tbm['median']}회")
        lines.append("")
        lines.append("턴 수 분포:")
        lines.append("")
        lines.append("| 턴 수 | 대화 수 |")
        lines.append("|------|---------|")
        for turns, count in sorted(tbm["distribution"].items(), key=lambda x: int(x[0])):
            lines.append(f"| {turns} | {count} |")
        lines.append("")

    if esc["failure_patterns"]:
        lines.append("### 실패 패턴")
        lines.append("")
        lines.append("| 패턴 | 발생 횟수 |")
        lines.append("|------|----------|")
        for pattern, count in esc["failure_patterns"].items():
            lines.append(f"| {pattern} | {count} |")
        lines.append("")

    # Bot-only resolutions
    res = r["bot_only_resolutions"]
    lines.append("## 4. Bot-only 대화 해결 유형")
    lines.append("")
    lines.append(f"총 {res['total_bot_only']}건의 대화가 매니저 없이 종료됨:")
    lines.append("")
    lines.append("| 유형 | 건수 | 비율 |")
    lines.append("|------|------|------|")
    for name, data in res["types"].items():
        lines.append(f"| {name} | {data['count']} | {data['pct']}% |")
    lines.append("")

    # Escalation topics
    topics = r["escalation_topics"]
    lines.append("## 5. 에스컬레이션 토픽 분포")
    lines.append("")
    lines.append(f"총 {topics['total_escalated']}건이 매니저로 전환됨:")
    lines.append("")
    lines.append("| 토픽 | 건수 | 비율 |")
    lines.append("|------|------|------|")
    for name, data in topics["topics"].items():
        lines.append(f"| {name} | {data['count']} | {data['pct']}% |")
    lines.append("")

    # Admin integration
    admin = r["admin_integration"]
    lines.append("## 6. Admin 연동 탐지")
    lines.append("")
    if admin:
        lines.append("| 연동 유형 | 발생 횟수 | Bot ID |")
        lines.append("|----------|----------|--------|")
        for name, data in admin.items():
            bot_ids = ", ".join(data["bot_ids"])
            lines.append(f"| {name} | {data['count']} | {bot_ids} |")
        lines.append("")
        lines.append("### 증거 샘플")
        lines.append("")
        for name, data in admin.items():
            if data["evidence_samples"]:
                lines.append(f"**{name}**:")
                for sample in data["evidence_samples"]:
                    lines.append(f"  - `{sample}`")
                lines.append("")
    else:
        lines.append("Admin 연동 시그널이 탐지되지 않았습니다.")
        lines.append("")

    # Topic distribution (cluster-based)
    if r.get("topic_distribution"):
        lines.append("## 7. 토픽 분포 (클러스터 기반)")
        lines.append("")
        lines.append("| 클러스터 | 대화 수 | 비율 |")
        lines.append("|---------|---------|------|")
        for label, data in r["topic_distribution"].items():
            lines.append(f"| {label} | {data['count']} | {data['pct']}% |")
        lines.append("")

    # Summary / Implications
    lines.append("## 시사점")
    lines.append("")
    bot_rate = cov["bot_involvement_rate_pct"]
    bot_only_rate = cov["bot_only_rate_pct"]
    esc_rate = cov["escalation_rate_pct"]

    if bot_rate > 80:
        lines.append(f"- **봇이 주력 응대 채널** ({bot_rate}% 관여율): 거의 모든 상담에서 봇이 첫 응답")
    elif bot_rate > 30:
        lines.append(f"- **봇이 보조 역할** ({bot_rate}% 관여율): 일부 상담에서 봇 관여")
    else:
        lines.append(f"- **봇 관여 미미** ({bot_rate}% 관여율): 대부분 매니저 직접 응대")

    if bot_only_rate > 40:
        lines.append(f"- **자체 해결률 높음** ({bot_only_rate}%): 봇이 상당수 상담을 독립 처리")
    else:
        lines.append(f"- **자체 해결률 낮음** ({bot_only_rate}%): 대부분 매니저 에스컬레이션 필요")

    if admin:
        admin_types = ", ".join(admin.keys())
        lines.append(f"- **Admin 연동 확인**: {admin_types}")
    else:
        lines.append("- **Admin 연동 미확인**: 지식 기반 응답만 수행")

    lines.append("")

    return "\n".join(lines)


# ─────────────── Main ───────────────────────────────────────────────────── #

def main():
    parser = argparse.ArgumentParser(description="Non-ALF Bot Analyzer")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--messages", help="Path to messages CSV")
    input_group.add_argument("--excel", help="Path to source Excel file")
    parser.add_argument("--tags", help="Path to cluster tags Excel (optional)")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Load data ──
    print("Loading messages...")
    df = load_messages(args)
    tags = load_tags(args.tags) if args.tags else {}

    source_name = args.messages or args.excel
    total_msgs = len(df)
    total_chats = df["chatId"].nunique()

    print(f"  Total: {total_msgs:,} messages, {total_chats} conversations")
    print(f"  personType distribution: {df['personType'].value_counts().to_dict()}")

    # ── Filter bot messages ──
    all_bot = df[df["personType"] == "bot"]
    alf_bot = all_bot[all_bot["personId"].astype(str).str.startswith(ALF_PREFIX)]
    non_alf_bot = all_bot[~all_bot["personId"].astype(str).str.startswith(ALF_PREFIX)]

    print(f"\n  Bot messages: {len(all_bot)} (ALF: {len(alf_bot)}, Non-ALF: {len(non_alf_bot)})")
    print(f"  Non-ALF bot personIds: {sorted(non_alf_bot['personId'].astype(str).unique().tolist())}")

    if len(non_alf_bot) == 0:
        print("\n  No non-ALF bot messages found. Exiting.")
        return

    # ── Classify bots ──
    print("\nClassifying bot types...")
    bot_type_map = classify_all_bots(non_alf_bot)
    for pid, btype in bot_type_map.items():
        print(f"  {pid}: {BotType.LABELS.get(btype, btype)}")

    # Build bot type profiles
    bot_profiles = []
    for pid, btype in bot_type_map.items():
        pid_msgs = non_alf_bot[non_alf_bot["personId"].astype(str) == pid]
        bot_profiles.append({
            "person_id": pid,
            "bot_type": btype,
            "message_count": len(pid_msgs),
            "conversation_count": pid_msgs["chatId"].nunique(),
        })

    # ── Coverage analysis ──
    print("\nAnalyzing coverage...")
    coverage = analyze_coverage(df, non_alf_bot)
    print(f"  Bot involvement: {coverage['bot_involvement_rate_pct']}%")
    print(f"  Bot-only: {coverage['bot_only_rate_pct']}%")
    print(f"  Escalation: {coverage['escalation_rate_pct']}%")

    # ── Escalation analysis ──
    print("\nAnalyzing escalation patterns...")
    escalation = analyze_escalation(df, non_alf_bot)

    # ── Bot-only resolution types ──
    print("Classifying bot-only resolutions...")
    bot_only_res = classify_bot_only_resolutions(df, non_alf_bot)

    # ── Escalation topics ──
    print("Classifying escalation topics...")
    esc_topics = classify_escalation_topics(df, non_alf_bot)

    # ── Admin integration ──
    print("Detecting admin integration...")
    admin = detect_admin_integration(non_alf_bot)
    for name, data in admin.items():
        print(f"  {name}: {data['count']} occurrences")

    # ── Topic distribution ──
    topic_dist = analyze_topic_distribution(df, non_alf_bot, tags)

    # ── Build results ──
    results = {
        "metadata": {
            "analysis_date": str(date.today()),
            "source": str(source_name),
            "total_messages": total_msgs,
            "total_conversations": total_chats,
            "bot_messages_total": len(all_bot),
            "alf_messages": len(alf_bot),
            "non_alf_bot_messages": len(non_alf_bot),
        },
        "bot_types": bot_profiles,
        "coverage": coverage,
        "escalation": escalation,
        "bot_only_resolutions": bot_only_res,
        "escalation_topics": esc_topics,
        "admin_integration": admin,
    }
    if topic_dist:
        results["topic_distribution"] = topic_dist

    # ── Write outputs ──
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if hasattr(obj, "item"):  # numpy int/float
                return obj.item()
            return super().default(obj)

    json_path = output_dir / OUTPUT_JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=JSON_INDENT, cls=NumpyEncoder)
    print(f"\n  JSON: {json_path}")

    md_path = output_dir / OUTPUT_MD
    report = generate_report(results)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  Report: {md_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
