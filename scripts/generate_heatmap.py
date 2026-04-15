#!/usr/bin/env python3
"""
generate_heatmap.py — cross_analysis.json → heatmap.png
=========================================================
Stage 5에서 생성한 cross_analysis.json을 읽어 히트맵 PNG를 생성합니다.
기존 analyze_dialogs.py의 generate_heatmap()과 달리, Stage 5 표준
cross_analysis.json 포맷에 맞게 동작하며 한글 폰트를 자동 탐지합니다.

Usage:
    python3 scripts/generate_heatmap.py \\
        --input  results/{company}/05_sales_report/analysis/cross_analysis.json \\
        --output results/{company}/05_sales_report/analysis/heatmap.png \\
        [--top_n 15]          # 상위 N개 클러스터만 표시 (기본값: 15)
        [--font "NanumGothic"] # 폰트 강제 지정 (선택)
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np


# ── 한글 폰트 우선순위 목록 ─────────────────────────────────────────────────
KOREAN_FONT_PRIORITY = [
    "NanumGothic",
    "Nanum Gothic",
    "AppleGothic",
    "Apple SD Gothic Neo",
    "Malgun Gothic",
    "Toppan Bunkyu Gothic",
    "Hiragino Sans",
    "DejaVu Sans",  # 폴백 (한글 깨짐 발생하지만 오류는 방지)
]

DIALOG_TYPE_LABELS = {
    "1": "지식응답",
    "2": "정보조회",
    "3": "단순실행",
    "4": "정책확인",
    "5": "조건부실행",
    "6": "의도불명확",
    "7": "상담사전환",
}


def find_korean_font():
    """시스템에서 한글 지원 폰트를 탐지해 이름을 반환합니다."""
    try:
        import matplotlib.font_manager as fm
        available = {f.name for f in fm.fontManager.ttflist}
        for candidate in KOREAN_FONT_PRIORITY:
            # 대소문자 무관 매칭
            for name in available:
                if candidate.lower() == name.lower():
                    return name
        return None
    except Exception:
        return None


def load_cross_analysis(path: Path) -> dict:
    """cross_analysis.json을 읽어 반환합니다."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_matrix(data: dict, top_n: int) -> tuple[np.ndarray, list[str], list[str], bool]:
    """
    cross_analysis.json → 히트맵용 행렬 + 레이블 반환.

    토픽 기반 (y_axis == "topic") 과 클러스터 기반 모두 지원.

    Returns:
        matrix    : (n_rows, n_cols) ndarray (클러스터/토픽 × 대화유형, 전체 대비 %)
        row_labels: 클러스터/토픽 레이블 목록
        col_labels: 대화유형 레이블 목록
        is_topic  : 토픽 기반 여부
    """
    is_topic = data.get("y_axis") == "topic"

    # 토픽 기반: cross_table이 {topic_id: {dtype: count}} 형태
    if is_topic:
        cross_table   = data.get("cross_table", {})
        cluster_stats = data.get("cluster_stats", {})
        total = data.get("total_chats", 1) or 1

        # 건수 내림차순 정렬
        sorted_items = sorted(
            cross_table.items(),
            key=lambda x: sum(x[1].values()),
            reverse=True,
        )[:top_n]

        type_keys  = [str(i) for i in range(1, 8)]
        col_labels = [f"{k}.{DIALOG_TYPE_LABELS[k]}" for k in type_keys]

        # 토픽 key → 대화유형 key 매핑 (dtype이 "1.지식응답" 또는 "1" 형태 모두 지원)
        row_labels = []
        matrix = []
        for tid, type_counts in sorted_items:
            label = cluster_stats.get(tid, {}).get("label", tid)[:18]
            row_labels.append(label)

            row = []
            for t in type_keys:
                # "1" 또는 "1.지식응답" 두 형태 모두 탐색
                cnt = type_counts.get(t, 0)
                if cnt == 0:
                    full_key = f"{t}.{DIALOG_TYPE_LABELS.get(t, '')}"
                    cnt = type_counts.get(full_key, 0)
                pct = round(cnt / total * 100, 1)
                row.append(pct)
            matrix.append(row)

        return np.array(matrix), row_labels, col_labels, True

    # 클러스터 기반 (기존 로직)
    cluster_data = data.get("cluster_cross_analysis", {})
    total = data.get("metadata", {}).get("total_classified", 1) or 1

    sorted_clusters = sorted(
        cluster_data.items(),
        key=lambda x: x[1].get("sample_count", 0),
        reverse=True,
    )[:top_n]

    type_keys = [str(i) for i in range(1, 8)]
    col_labels = [f"{k}.{DIALOG_TYPE_LABELS[k]}" for k in type_keys]

    row_labels = []
    matrix = []

    for cid, info in sorted_clusters:
        label = str(info.get("label", f"C{cid}"))[:12]
        row_labels.append(f"C{cid}: {label}")

        dialog_types = info.get("dialog_types", {})
        row = []
        for t in type_keys:
            cnt = dialog_types.get(t, 0)
            pct = round(cnt / total * 100, 1)
            row.append(pct)
        matrix.append(row)

    return np.array(matrix), row_labels, col_labels, False


def generate_heatmap(
    data: dict,
    output_path: Path,
    top_n: int = 15,
    font_name=None,
) -> None:
    """히트맵 PNG를 생성합니다."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
    except ImportError:
        print("  ⚠️  matplotlib 없음 — pip install matplotlib 실행 후 재시도")
        sys.exit(1)

    # 폰트 설정
    if font_name:
        plt.rcParams["font.family"] = font_name
    else:
        detected = find_korean_font()
        if detected:
            plt.rcParams["font.family"] = detected
            print(f"  🔤 한글 폰트: {detected}")
        else:
            print("  ⚠️  한글 폰트를 찾지 못했습니다. 한글이 깨질 수 있습니다.")
    plt.rcParams["axes.unicode_minus"] = False

    matrix, row_labels, col_labels, is_topic = build_matrix(data, top_n)
    n_rows, n_cols = matrix.shape

    # 행 합계·열 합계 추가
    row_sums = matrix.sum(axis=1, keepdims=True)
    col_sums = matrix.sum(axis=0, keepdims=True)
    corner = np.array([[matrix.sum()]])
    extended = np.hstack([matrix, row_sums])
    extended = np.vstack([extended, np.hstack([col_sums, corner])])

    ext_rows = row_labels + ["유형별 합계"]
    ext_cols = col_labels + ["주제별\n합계"]

    # 합계 행/열은 별도 색상 처리를 위해 마스크
    main_data = extended[:-1, :-1]

    # ── 그림 크기 자동 조정 ────────────────────────────────────────────────
    fig_w = max(14, n_cols * 1.6 + 3)
    fig_h = max(8, n_rows * 0.55 + 3)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # ── 컬러맵 ────────────────────────────────────────────────────────────
    # 합계 포함 전체를 하나의 imshow로 그리되, 합계 행/열은 별도 색조
    cmap_main = plt.cm.YlOrRd
    cmap_sum  = plt.cm.Blues

    # 메인 영역
    im = ax.imshow(
        extended,
        cmap=cmap_main,
        aspect="auto",
        vmin=0,
        vmax=max(main_data.max() * 1.2, 0.1),
    )

    # 합계 행·열을 Blues 계열로 덮어쓰기
    sum_row = extended[-1:, :]
    sum_col = extended[:, -1:]
    ax.imshow(
        np.vstack([np.full((n_rows, n_cols + 1), np.nan), sum_row]),
        cmap=cmap_sum,
        aspect="auto",
        vmin=0,
        vmax=100,
        alpha=0.6,
    )
    ax.imshow(
        np.hstack([np.full((n_rows + 1, n_cols), np.nan), sum_col]),
        cmap=cmap_sum,
        aspect="auto",
        vmin=0,
        vmax=100,
        alpha=0.6,
    )

    # ── 축 레이블 ─────────────────────────────────────────────────────────
    ax.set_xticks(range(len(ext_cols)))
    ax.set_xticklabels(ext_cols, fontsize=9, fontweight="bold", rotation=30, ha="right")
    ax.set_yticks(range(len(ext_rows)))
    ax.set_yticklabels(ext_rows, fontsize=9)

    # ── 셀 값 표시 ────────────────────────────────────────────────────────
    thresh = main_data.max() * 0.55 if main_data.max() > 0 else 1.0
    for i in range(len(ext_rows)):
        for j in range(len(ext_cols)):
            val = extended[i, j]
            if val == 0:
                ax.text(j, i, "–", ha="center", va="center", fontsize=8, color="#cccccc")
                continue
            is_sum = (i == len(ext_rows) - 1) or (j == len(ext_cols) - 1)
            bold = "bold" if (val >= thresh or is_sum) else "normal"
            color = "white" if (val >= thresh and not is_sum) else "black"
            ax.text(
                j, i,
                f"{val:.1f}%",
                ha="center", va="center",
                fontsize=8 if is_sum else 9,
                fontweight=bold,
                color=color,
            )

    # ── 컬러바 + 타이틀 ───────────────────────────────────────────────────
    cbar = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
    cbar.set_label("전체 대비 비율 (%)", fontsize=9)

    company = data.get("metadata", {}).get("company", "")
    total = data.get("metadata", {}).get("total_classified", 0) or data.get("total_chats", 0)
    y_unit = "SOP 토픽" if is_topic else "클러스터"
    ax.set_title(
        f"{company} 상담주제 × 대화유형 교차분석 히트맵\n"
        f"(상위 {min(top_n, len(row_labels))}개 {y_unit}, 샘플 {total:,}건)",
        fontsize=12,
        fontweight="bold",
        pad=12,
    )
    ax.set_xlabel("대화유형", fontsize=10, labelpad=8)
    ax.set_ylabel(f"상담주제 ({y_unit})", fontsize=10, labelpad=8)

    # 구분선 — 합계 행/열 경계
    ax.axhline(y=len(ext_rows) - 1.5, color="gray", linewidth=1.5, linestyle="--", alpha=0.6)
    ax.axvline(x=len(ext_cols) - 1.5, color="gray", linewidth=1.5, linestyle="--", alpha=0.6)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"  ✅ 히트맵 저장: {output_path}  ({output_path.stat().st_size // 1024} KB)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="cross_analysis.json → heatmap.png (한글 폰트 자동 탐지)"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="cross_analysis.json 경로",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="출력 PNG 경로 (기본값: 입력 파일과 같은 폴더의 heatmap.png)",
    )
    parser.add_argument(
        "--top_n",
        type=int,
        default=15,
        help="표시할 상위 클러스터 수 (기본값: 15)",
    )
    parser.add_argument(
        "--font",
        default=None,
        help="한글 폰트 이름 강제 지정 (예: 'NanumGothic'). 생략 시 자동 탐지.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 파일 없음: {input_path}")
        sys.exit(1)

    output_path = Path(args.output) if args.output else input_path.parent / "heatmap.png"

    print(f"📊 히트맵 생성 중...")
    print(f"   입력: {input_path}")
    print(f"   출력: {output_path}")
    print(f"   상위 클러스터: {args.top_n}개")

    data = load_cross_analysis(input_path)
    generate_heatmap(data, output_path, top_n=args.top_n, font_name=args.font)


if __name__ == "__main__":
    main()
