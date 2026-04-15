#!/usr/bin/env python3
"""
Sales Report Generator — ALF Implementation Analysis
====================================================
Config JSON 파일을 읽어 수치를 일관성 있게 계산하고
마크다운 세일즈 리포트를 생성합니다.

Usage:
    python3 scripts/generate_sales_report.py \\
        --config results/assacom/06_sales_report/sales_report_config.json

    # 출력 경로 지정
    python3 scripts/generate_sales_report.py \\
        --config results/assacom/06_sales_report/sales_report_config.json \\
        --output results/assacom/06_sales_report/assacom_sales_report_v8.md
"""

import json
import argparse
import math
from pathlib import Path
from datetime import date


# ─────────────────────────── Formatting helpers ──────────────────────────── #

def fc(n: int) -> str:
    """Format count with comma: 3958 → '3,958'"""
    return f"{n:,}"


def fw(amount: int) -> str:
    """Format Won in 만원 units: 9,547,000 → '약 955만원'"""
    man = round(amount / 10_000)
    return f"약 {man:,}만원"


def fp(rate: float) -> str:
    """Format rate as integer percent: 0.682 → '68%'"""
    return f"{round(rate * 100)}%"


# ──────────────────────────── Core calculation ───────────────────────────── #

def calculate(cfg: dict) -> dict:
    bp      = cfg["base_params"]
    vol     = bp["monthly_volume"]      # 월 상담 건수
    sample  = bp["sample_size"]         # 분석 샘플 수

    # 기본값 검증: 0 또는 음수일 경우 계산 전 에러
    if sample <= 0:
        raise ValueError(f"base_params.sample_size must be positive, got {sample!r}")
    if vol <= 0:
        raise ValueError(f"base_params.monthly_volume must be positive, got {vol!r}")

    wage    = bp["agent_hourly_wage"]   # 상담사 시급 (원)
    t_min   = bp["avg_handling_time_min"]           # 건당 평균 처리 시간 (분)
    c_chat  = bp["alf_chat_cost_per_conversation"]  # ALF 채팅 비용
    c_task  = bp["alf_task_cost_per_execution"]     # ALF 태스크 비용
    dev     = cfg["development_cost"]

    # ── 그룹별 계산 ──────────────────────────────────────────────────────── #
    groups = []
    for grp in cfg["sop_groups"]:
        sops = grp["sops"]

        # 샘플 합산 및 가중 해결율
        sample_count = sum(s["sample_count"] for s in sops)
        resolved_sample = sum(s["sample_count"] * s["resolution_rate"] for s in sops)
        resolution_rate = resolved_sample / sample_count if sample_count else 0

        # 실제 월 건수로 스케일
        # sample은 위에서 양수로 검증했지만 추가로 안전장치 적용
        monthly_count   = round(sample_count   / sample * vol) if sample else 0
        monthly_resolved = round(resolved_sample / sample * vol) if sample else 0

        groups.append({
            **grp,
            "sample_count":      sample_count,
            "monthly_count":     monthly_count,
            "monthly_resolved":  monthly_resolved,
            "resolution_rate":   resolution_rate,
        })

    # ── Phase 분리 ───────────────────────────────────────────────────────── #
    p1_groups = [g for g in groups if g["phase"] == 1]
    p2_groups = [g for g in groups if g["phase"] == 2]

    p1_monthly   = sum(g["monthly_count"]    for g in p1_groups)
    p1_resolved  = sum(g["monthly_resolved"] for g in p1_groups)
    p2_monthly   = sum(g["monthly_count"]    for g in p2_groups)
    p2_resolved  = sum(g["monthly_resolved"] for g in p2_groups)
    total_resolved = p1_resolved + p2_resolved

    # ── ALF 비용 ─────────────────────────────────────────────────────────── #
    # Phase 1: 참여 건수만큼 채팅 비용, 태스크 없음
    p1_alf_chat  = p1_monthly * c_chat
    p1_alf_total = p1_alf_chat

    # 전체: 전체 참여 채팅 + Phase 2 태스크
    full_alf_chat  = vol * c_chat
    full_alf_task  = p2_monthly * c_task
    full_alf_total = full_alf_chat + full_alf_task

    # ── 인건비 절감 계산 ─────────────────────────────────────────────────── #
    coeff = t_min / 60  # 시간 단위 변환 계수

    p1_labor      = round(p1_resolved  * coeff * wage)
    p1_net_mon    = p1_labor - p1_alf_total
    p1_net_ann    = p1_net_mon * 12

    full_labor    = round(total_resolved * coeff * wage)
    full_net_mon  = full_labor - full_alf_total
    full_net_ann  = full_net_mon * 12

    # ── 손익분기 ─────────────────────────────────────────────────────────── #
    if full_net_mon > 0 and dev["phase2_min_krw"] > 0:
        bre_min = math.ceil(dev["phase2_min_krw"] / full_net_mon)
        bre_max = math.ceil(dev["phase2_max_krw"] / full_net_mon)
        breakeven = f"약 {bre_min}~{bre_max}개월"
    else:
        breakeven = "—"

    return {
        "vol": vol, "wage": wage, "t_min": t_min,
        "c_chat": c_chat, "c_task": c_task,
        "dev": dev, "breakeven": breakeven,
        "groups": groups,
        "p1": {
            "groups": p1_groups,
            "monthly":   p1_monthly,
            "resolved":  p1_resolved,
            # vol은 양수로 검증되어 있으므로 여기서는 그대로 사용하지만
            # 추가적으로 방어적으로 0 분모 체크를 붙여 둠
            "pct":       p1_monthly / vol if vol else 0,
            "alf_chat":  p1_alf_chat,
            "alf_total": p1_alf_total,
            "labor":     p1_labor,
            "net_mon":   p1_net_mon,
            "net_ann":   p1_net_ann,
        },
        "p2": {
            "groups": p2_groups,
            "monthly":  p2_monthly,
            "resolved": p2_resolved,
        },
        "full": {
            "monthly":    vol,
            "resolved":   total_resolved,
            "res_rate":   total_resolved / vol if vol else 0,
            "alf_chat":   full_alf_chat,
            "alf_task":   full_alf_task,
            "alf_total":  full_alf_total,
            "labor":      full_labor,
            "net_mon":    full_net_mon,
            "net_ann":    full_net_ann,
        },
    }


# ──────────────────────────── Markdown builder ───────────────────────────── #

def build_report(cfg: dict, m: dict) -> str:
    name     = cfg["company_name"]
    rep_date = cfg.get("report_date", str(date.today()))
    ref_mon  = cfg.get("data_reference_month", "")
    dev      = m["dev"]
    p1       = m["p1"]
    p2       = m["p2"]
    full     = m["full"]

    min_man = round(dev["phase2_min_krw"] / 10_000)
    max_man = round(dev["phase2_max_krw"] / 10_000)
    dev_range = f"{min_man:,}~{max_man:,}만원"

    lines = []

    # ── 헤더 ─────────────────────────────────────────────────────────────── #
    lines += [
        f"# {name} AI 상담 자동화 도입 효과 분석",
        "",
        f"> **작성일**: {rep_date} | **분석 기준**: 실제 상담 데이터 ({ref_mon} 기준 월 {fc(m['vol'])}건)",
        "",
        "| 업무 | 월 건수 | 해결율 | 처리 방식 |",
        "|------|--------|--------|---------|",
    ]
    for g in m["groups"]:
        res_pct = g["monthly_resolved"] / g["monthly_count"] if g["monthly_count"] else 0
        lines.append(
            f"| {g['group_name']} | 약 {fc(g['monthly_count'])}건 | {fp(res_pct)} | {g['implementation']} |"
        )
    lines += [
        f"| **합계** | **{fc(m['vol'])}건** | **{fp(full['res_rate'])}** | |",
        "",
    ]

    # ── 1. ROI 요약 ──────────────────────────────────────────────────────── #
    lines += [
        "## 1. ROI 요약",
        "",
        "| 구분 | 월 순절감 | 연간 순절감 | 투자 | 손익분기 |",
        "|------|---------|----------|------|--------|",
        f"| **1단계** (즉시 배포) | **{fw(p1['net_mon'])}** | **{fw(p1['net_ann'])}** | 없음 | **즉시** |",
        f"| **전체 완성** (API 연동) | **{fw(full['net_mon'])}** | **{fw(full['net_ann'])}** | 외주비 {dev_range} | {m['breakeven']} |",
        "",
        f"> **핵심 메시지**: 1단계는 추가 비용 없이 첫 달부터 수익 발생."
        f" API 연동 투자 후 연간 {fw(full['net_ann'])} 절감.",
        "",
        "| 지표 | 수치 | 의미 |",
        "|------|------|------|",
        "| 관여율 | **100%** | 모든 고객 문의에 ALF 우선 응대 |",
        f"| 해결율 | **{fp(full['res_rate'])}** | 상담원 없이 완전 처리 가능한 비율 |",
        f"| 월 자동 처리 건수 | **약 {fc(full['resolved'])}건** |"
        f" {fc(m['vol'])}건 중 ALF가 처음부터 끝까지 처리 |",
        "",
        "---",
        "",
    ]

    # ── 2. 도입 시나리오 ─────────────────────────────────────────────────── #
    lines += [
        "## 2. 도입 시나리오",
        "",
        "### 1단계 — 즉시 배포 (추가 개발 없음, 2~3주)",
        "",
        "> 고객사 담당자(비개발자)가 규칙 설정 + FAQ DB 구축만으로 배포",
        "",
        "| 적용 업무 | 월 건수 | 해결 건수 |",
        "|---------|--------|---------|",
    ]
    for g in p1["groups"]:
        lines.append(
            f"| {g['group_name']} | 약 {fc(g['monthly_count'])}건 | 약 {fc(g['monthly_resolved'])}건 |"
        )
    lines += [
        f"| **소계** | **{fc(p1['monthly'])}건 ({p1['pct']:.1%})** | **약 {fc(p1['resolved'])}건** |",
        "",
        "**필요 작업:**",
    ]
    for note in cfg.get("phase1_notes", []):
        lines.append(f"- {note}")
    lines += [
        "",
        "---",
        "",
        f"### 2단계 — API 연동 (전체 완성, {dev.get('phase2_duration', '미정')})",
        "",
        f"> {cfg.get('phase2_description', 'API 연동으로 나머지 업무 자동화 추가')}",
        "",
        "| 적용 업무 | 월 건수 | 해결율 | 필요 API |",
        "|---------|--------|--------|---------|",
    ]
    for g in p2["groups"]:
        res_pct = g["monthly_resolved"] / g["monthly_count"] if g["monthly_count"] else 0
        api_str = g.get("required_api") or "—"
        # 배송처럼 두 SOP 합산인 경우 범위 표시
        if len(g["sops"]) > 1:
            rates = [s["resolution_rate"] for s in g["sops"]]
            lo, hi = min(rates), max(rates)
            rate_str = f"{round(lo*100)}~{round(hi*100)}%"
        else:
            rate_str = fp(res_pct)
        lines.append(
            f"| {g['group_name']} | 약 {fc(g['monthly_count'])}건 | {rate_str} | {api_str} |"
        )
    p2_pct = p2["monthly"] / m["vol"] if m["vol"] else 0
    lines += [
        f"| **추가 소계** | **{fc(p2['monthly'])}건 ({p2_pct:.1%})** | — | — |",
        f"| **전체** | **{fc(m['vol'])}건 (100%)** | **{fp(full['res_rate'])}** | — |",
        "",
        "**필요 작업:**",
    ]
    for note in cfg.get("phase2_notes", []):
        lines.append(f"- {note}")
    lines += [
        "",
        "---",
        "",
    ]

    # ── 3. 도입 시 예상 리소스 ───────────────────────────────────────────── #
    lines += [
        "## 3. 도입 시 예상 리소스",
        "",
        "| 단계 | 작업 내용 | 담당 | 소요 기간 | 비용 |",
        "|------|---------|------|---------|------|",
    ]
    for row in cfg.get("resource_table", []):
        ph   = row["phase"]
        task = row["task"]
        own  = row["owner"]
        dur  = row["duration"]
        cost = row["cost_display"]
        # 합계 행 굵게
        if "합계" in ph or ph == "전체 완성":
            lines.append(f"| **{ph}** | | | **{dur}** | **{cost}** |")
        else:
            lines.append(f"| **{ph}** | {task} | {own} | {dur} | {cost} |")
    lines += ["", "---", ""]

    # ── 4. ROI 상세 계산 ─────────────────────────────────────────────────── #
    lines += [
        "## 4. ROI 상세 계산",
        "",
        "**계산 공식 (ALF 실제 과금 구조 기반)**",
        "",
        "```",
        "월 순절감액 = (해결 건수 × 평균 처리 시간(분) ÷ 60 × 상담사 시급)",
        "            - ALF 운영 비용",
        "",
        "ALF 운영 비용 = (ALF 참여 대화 수 × 500원)",
        "             + (태스크 실행 수 × 200원)",
        "```",
        "",
        "| 측정 항목 | 방법 |",
        "|---------|------|",
        "| ALF 참여 대화 수 | alf_triggered 건수 자동 집계 |",
        "| 평균 처리 시간 | alf_handling_time 합계 ÷ 참여 건수 |",
        f"| 상담사 시급 | 수동 설정 (임금직업포털 중위값: {fc(m['wage'])}원/시간) |",
        "",
        "---",
        "",
        f"**1단계 계산 (월 {fc(m['vol'])}건 기준, {ref_mon} 실측)**",
        "",
        "| 항목 | 계산 | 금액 |",
        "|------|------|------|",
        f"| ALF 참여 건수 | {fc(m['vol'])}건 × {p1['pct']:.1%} | {fc(p1['monthly'])}건 |",
        f"| 채팅 ALF 비용 | {fc(p1['monthly'])}건 × {fc(m['c_chat'])}원 | {fc(p1['alf_chat'])}원 |",
        f"| 태스크 비용 | 없음 (규칙+지식 기반) | 0원 |",
        f"| **총 ALF 비용** | | **{fc(p1['alf_total'])}원** |",
        f"| 해결 건수 | (SOP별 해결율 가중 합산) | 약 {fc(p1['resolved'])}건 |",
        f"| 인건비 절감 | {fc(p1['resolved'])} × {m['t_min']}분 ÷ 60 × {fc(m['wage'])}원 | {fc(p1['labor'])}원 |",
        f"| **월 순절감** | {fc(p1['labor'])} - {fc(p1['alf_total'])} | **{fw(p1['net_mon'])}** |",
        f"| **연간 순절감** | {fc(p1['net_mon'])}원 × 12 | **{fw(p1['net_ann'])}** |",
        "",
        "---",
        "",
        "**전체 완성 계산 (1단계+2단계, 10개 SOP)**",
        "",
        "| 항목 | 계산 | 금액 |",
        "|------|------|------|",
        f"| ALF 참여 건수 | {fc(m['vol'])}건 (100%) | {fc(m['vol'])}건 |",
        f"| 채팅 ALF 비용 | {fc(m['vol'])}건 × {fc(m['c_chat'])}원 | {fc(full['alf_chat'])}원 |",
        f"| 태스크 비용 | {fc(p2['monthly'])}건 × {fc(m['c_task'])}원 | {fc(full['alf_task'])}원 |",
        f"| **총 ALF 비용** | | **{fc(full['alf_total'])}원** |",
        f"| 해결 건수 | (SOP별 해결율 가중 합산) | 약 {fc(full['resolved'])}건 |",
        f"| 인건비 절감 | {fc(full['resolved'])} × {m['t_min']}분 ÷ 60 × {fc(m['wage'])}원 | {fc(full['labor'])}원 |",
        f"| **월 순절감** | {fc(full['labor'])} - {fc(full['alf_total'])} | **{fw(full['net_mon'])}** |",
        f"| **연간 순절감** | {fc(full['net_mon'])}원 × 12 | **{fw(full['net_ann'])}** |",
        "",
        "---",
        "",
    ]

    # ── 5. ALF 적용 현황 ─────────────────────────────────────────────────── #
    lines += [
        "## 5. ALF 적용 현황",
        "",
        "**자동화 가능 업무**",
        "",
        "| 업무 | 월 건수 | 해결율 | 처리 방식 |",
        "|------|--------|--------|---------|",
    ]
    for g in m["groups"]:
        res_pct = g["monthly_resolved"] / g["monthly_count"] if g["monthly_count"] else 0
        impl = g["implementation"]
        lines.append(
            f"| {g['group_name']} | 약 {fc(g['monthly_count'])}건 | **{fp(res_pct)}** | {impl} |"
        )
    lines += [
        f"| **합계** | **{fc(m['vol'])}건** | **{fp(full['res_rate'])}** | |",
        "",
        "**자동화 한계 (상담원 전담 유지)**",
        "",
        "| 상황 | 이유 |",
        "|------|------|",
    ]
    for item in cfg.get("non_automatable", []):
        lines.append(f"| {item['situation']} | {item['reason']} |")
    lines += [
        "",
        "> **관여율 100%**: 위 케이스도 ALF가 기본 정보를 수집해 상담원에게 전달 — 상담원 처리 효율 향상",
        "",
        "---",
        "",
        "> ⚠️ **검수 필요**: ROI 수치는 alf_triggered, alf_handling_time 실측값과 실제 상담사 시급으로 최종 검증 필요",
        "",
    ]

    return "\n".join(lines)


# ──────────────────────────────── Entry point ────────────────────────────── #

def main():
    parser = argparse.ArgumentParser(description="Generate ALF Sales Report from config JSON")
    parser.add_argument("--config", required=True, help="Path to sales_report_config.json")
    parser.add_argument("--output", default=None, help="Output markdown file path")
    args = parser.parse_args()

    config_path = Path(args.config)
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)

    m = calculate(cfg)
    report = build_report(cfg, m)

    # 출력 경로 결정
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = config_path.parent / f"{cfg['company_name']}_sales_report.md"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"✅ Report generated: {out_path}")

    # 주요 수치 요약 출력
    p1 = m["p1"]
    full = m["full"]
    print(f"\n📊 주요 수치 요약")
    print(f"  1단계: 월 {p1['monthly']:,}건 참여, {p1['resolved']:,}건 해결")
    print(f"        ALF 비용 {p1['alf_total']:,}원 | 인건비 절감 {p1['labor']:,}원")
    print(f"        월 순절감 {fw(p1['net_mon'])} | 연간 {fw(p1['net_ann'])}")
    print(f"  전체: 월 {full['monthly']:,}건 참여, {full['resolved']:,}건 해결 ({fp(full['res_rate'])})")
    print(f"        ALF 비용 {full['alf_total']:,}원 | 인건비 절감 {full['labor']:,}원")
    print(f"        월 순절감 {fw(full['net_mon'])} | 연간 {fw(full['net_ann'])}")
    print(f"  손익분기: {m['breakeven']}")


if __name__ == "__main__":
    main()
