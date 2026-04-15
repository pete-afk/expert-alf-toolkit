#!/usr/bin/env python3
"""
ALF Setup Data Extractor
========================
Step 2 (Rules Draft + RAG Items) 전에 실행하여
LLM이 원시 파일을 직접 파싱하는 대신 구조화된 JSON을 받을 수 있게 합니다.

추출 항목:
  - patterns.json → 빈도 높은 패턴 (high/very high)
  - faq.json      → FAQ Q/A 쌍 전체
  - *.sop.md      → 톤앤매너 + 에스컬레이션 조건 + 피해야 할 표현

출력:
  {output_dir}/alf_setup/alf_setup_data.json

Usage:
    python3 scripts/extract_alf_setup_data.py \\
        --sop_dir   results/usimsa/03_sop \\
        --patterns  results/usimsa/02_extraction/patterns.json \\
        --faq       results/usimsa/02_extraction/faq.json \\
        --output    results/usimsa/06_sales_report/alf_setup
"""

import re
import json
import argparse
from enum import Enum
from pathlib import Path
from datetime import date


# ── 파일·출력 상수 ────────────────────────────────────────────────────────── #

SOP_FILE_EXT     = ".sop.md"
SOP_GLOB_PATTERN = f"*{SOP_FILE_EXT}"
OUTPUT_FILENAME  = "alf_setup_data.json"
DEFAULT_COMPANY  = "unknown"
SEPARATOR_WIDTH  = 45
JSON_INDENT      = 2
COMPANY_DIR_IDX  = -2   # results/{company}/03_sop → parts[-2] = company


class SopSection:
    """SOP 마크다운 섹션 헤더 이름."""
    TONE       = "톤앤매너"
    ESCALATION = "에스컬레이션 기준"


class PatternKey:
    """patterns.json 스키마 키."""
    CLUSTERS     = "clusters"
    CLUSTER_ID   = "cluster_id"
    LABEL        = "label"
    SOP_TYPE_REC = "sop_type_recommendation"
    TYPE         = "type"
    PATTERNS     = "patterns"
    FREQUENCY    = "frequency"
    PATTERN_NAME = "pattern_name"
    NAME         = "name"
    DESCRIPTION  = "description"


class FaqKey:
    """faq.json 스키마 키."""
    FAQ_PAIRS     = "faq_pairs"
    FAQ_ID        = "faq_id"
    CLUSTER_ID    = "cluster_id"
    CLUSTER_LABEL = "cluster_label"
    QUESTION      = "question"
    ANSWER        = "answer"


class FreqLevel(str, Enum):
    HIGH      = "high"
    VERY_HIGH = "very high"


HIGH_FREQ = {f.value for f in FreqLevel}


# ────────────────────────── SOP 파서 ─────────────────────────────────────── #

def parse_tone_and_escalation(sop_path: Path) -> dict:
    """
    .sop.md 에서 톤앤매너 + 에스컬레이션 조건 추출.

    반환:
    {
      "sop_id": "HT_001_...",
      "tone": {
        "examples": [...],      # 설명할 때/안내할 때 예시
        "forbidden": [...],     # 피해야 할 표현
      },
      "escalation": [
        {"situation": "...", "target": "...", "reason": "..."},
        ...
      ]
    }
    """
    text = sop_path.read_text(encoding="utf-8")
    sop_id = sop_path.name.replace(SOP_FILE_EXT, "")
    result = {
        "sop_id": sop_id,
        "tone": {"examples": [], "forbidden": []},
        "escalation": [],
    }

    # ── 톤앤매너 섹션 추출 ────────────────────────────────────────────────── #
    tone_m = re.search(
        rf'###\s+{SopSection.TONE}\n(.*?)(?=^---|\Z)',
        text, re.DOTALL | re.MULTILINE
    )
    if tone_m:
        tone_text = tone_m.group(1)

        # 예시 문구 (quoted strings)
        for line in tone_text.splitlines():
            line = line.strip()
            # - "문구" 형태
            q_m = re.match(r'-\s+"([^"]+)"', line)
            if q_m:
                result["tone"]["examples"].append(q_m.group(1))

        # 피해야 할 표현 (- ❌ "문구" 형태)
        for line in tone_text.splitlines():
            bad_m = re.search(r'❌\s+"([^"]+)"', line)
            if bad_m:
                result["tone"]["forbidden"].append(bad_m.group(1))

    # ── 에스컬레이션 테이블 추출 ──────────────────────────────────────────── #
    # "에스컬레이션 기준" 이후의 마크다운 테이블
    esc_sections = re.finditer(
        rf'\*\*{SopSection.ESCALATION}\*\*[^\n]*\n\n*((?:\|[^\n]+\n)+)',
        text
    )
    for esc_m in esc_sections:
        table_text = esc_m.group(1)
        rows = table_text.strip().splitlines()

        # 헤더 행 파악
        if len(rows) < 2:
            continue
        headers = [h.strip() for h in rows[0].split("|") if h.strip()]

        # 데이터 행 (구분선 제외)
        for row in rows[2:]:
            cells = [c.strip() for c in row.split("|") if c.strip()]
            if len(cells) < 2:
                continue
            entry = {
                "situation": cells[0] if len(cells) > 0 else "",
                "target":    cells[1] if len(cells) > 1 else "",
                "reason":    cells[2] if len(cells) > 2 else "",
                "source_sop": sop_id,
            }
            # 중복 제거
            if entry["situation"] and entry not in result["escalation"]:
                result["escalation"].append(entry)

    return result


# ─────────────────────── patterns.json 파서 ──────────────────────────────── #

def extract_high_freq_patterns(patterns_path: Path) -> list:
    """
    patterns.json에서 빈도 high/very high 패턴 추출.
    """
    data = json.loads(patterns_path.read_text(encoding="utf-8"))
    clusters = data.get(PatternKey.CLUSTERS, [])
    results = []

    for cluster in clusters:
        cid   = cluster.get(PatternKey.CLUSTER_ID)
        label = cluster.get(PatternKey.LABEL, "")
        stype = cluster.get(PatternKey.SOP_TYPE_REC, {}).get(PatternKey.TYPE, "")

        for pat in cluster.get(PatternKey.PATTERNS, []):
            freq = str(pat.get(PatternKey.FREQUENCY, "")).lower()
            if freq in HIGH_FREQ:
                results.append({
                    "cluster_id":    cid,
                    "cluster_label": label,
                    "sop_type":      stype,
                    "pattern":       pat.get(PatternKey.PATTERN_NAME, pat.get(PatternKey.NAME, "")),
                    "frequency":     freq,
                    "description":   pat.get(PatternKey.DESCRIPTION, ""),
                })

    return results


# ─────────────────────── faq.json 파서 ───────────────────────────────────── #

def extract_faq_pairs(faq_path: Path) -> list:
    """
    faq.json에서 모든 Q/A 쌍 추출.
    """
    data = json.loads(faq_path.read_text(encoding="utf-8"))
    pairs = data.get(FaqKey.FAQ_PAIRS, [])

    return [
        {
            "faq_id":        p.get(FaqKey.FAQ_ID, ""),
            "cluster_id":    p.get(FaqKey.CLUSTER_ID),
            "cluster_label": p.get(FaqKey.CLUSTER_LABEL, ""),
            "question":      p.get(FaqKey.QUESTION, ""),
            "answer":        p.get(FaqKey.ANSWER, ""),
        }
        for p in pairs
        if p.get(FaqKey.QUESTION) and p.get(FaqKey.ANSWER)
    ]


# ──────────────────────────── Main ───────────────────────────────────────── #

def main():
    parser = argparse.ArgumentParser(description="Extract structured data for ALF setup (Step 2 pre-processing)")
    parser.add_argument("--sop_dir",  required=True, help="Stage 3 SOP 디렉토리")
    parser.add_argument("--patterns", required=True, help="patterns.json 경로")
    parser.add_argument("--faq",      required=True, help="faq.json 경로")
    parser.add_argument("--output",   required=True, help="출력 디렉토리 (alf_setup/)")
    args = parser.parse_args()

    sop_dir    = Path(args.sop_dir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── SOP 파싱 ─────────────────────────────────────────────────────────── #
    sop_files = sorted(sop_dir.glob(SOP_GLOB_PATTERN))
    print(f"\n📖 SOP 파싱 — {len(sop_files)}개\n{'─'*SEPARATOR_WIDTH}")

    all_tones: list[str]       = []
    all_forbidden: list[str]   = []
    all_escalation: list[dict] = []
    per_sop_data: list[dict]   = []

    for sop_path in sop_files:
        parsed = parse_tone_and_escalation(sop_path)
        per_sop_data.append(parsed)

        all_tones.extend(parsed["tone"]["examples"])
        all_forbidden.extend(parsed["tone"]["forbidden"])
        all_escalation.extend(parsed["escalation"])

        n_esc = len(parsed["escalation"])
        n_tone = len(parsed["tone"]["examples"])
        print(f"  ✅ {parsed['sop_id']}: 톤 {n_tone}개, 에스컬레이션 {n_esc}개")

    # 중복 제거 (순서 유지)
    def dedup(lst):
        seen = set()
        return [x for x in lst if not (x in seen or seen.add(x))]

    all_tones     = dedup(all_tones)
    all_forbidden = dedup(all_forbidden)
    # 에스컬레이션은 (상황, 전달대상) 기준 중복 제거
    seen_esc = set()
    unique_esc = []
    for e in all_escalation:
        key = (e["situation"], e["target"])
        if key not in seen_esc:
            seen_esc.add(key)
            unique_esc.append(e)

    # ── patterns.json 파싱 ───────────────────────────────────────────────── #
    print(f"\n📊 patterns.json 파싱...")
    patterns_path = Path(args.patterns)
    high_freq_patterns = []
    if patterns_path.exists():
        high_freq_patterns = extract_high_freq_patterns(patterns_path)
        print(f"  ✅ 빈도 high/very high 패턴: {len(high_freq_patterns)}개")
    else:
        print(f"  ⚠️  patterns.json 없음: {patterns_path}")

    # ── faq.json 파싱 ────────────────────────────────────────────────────── #
    print(f"\n❓ faq.json 파싱...")
    faq_path = Path(args.faq)
    faq_pairs = []
    if faq_path.exists():
        faq_pairs = extract_faq_pairs(faq_path)
        print(f"  ✅ FAQ Q/A 쌍: {len(faq_pairs)}개")
    else:
        print(f"  ⚠️  faq.json 없음: {faq_path}")

    # ── 통합 JSON 저장 ───────────────────────────────────────────────────── #
    company = (
        sop_dir.parts[COMPANY_DIR_IDX]
        if len(sop_dir.parts) >= abs(COMPANY_DIR_IDX)
        else DEFAULT_COMPANY
    )
    output = {
        "company":       company,
        "extracted_at":  str(date.today()),
        "source": {
            "sop_dir":  str(sop_dir),
            "patterns": str(patterns_path),
            "faq":      str(faq_path),
        },
        "tone_rules": {
            "examples":  all_tones,
            "forbidden": all_forbidden,
        },
        "escalation_conditions": unique_esc,
        "faq_pairs":             faq_pairs,
        "high_freq_patterns":    high_freq_patterns,
        "summary": {
            "sop_count":               len(sop_files),
            "tone_examples":           len(all_tones),
            "forbidden_phrases":       len(all_forbidden),
            "escalation_conditions":   len(unique_esc),
            "faq_pairs":               len(faq_pairs),
            "high_freq_patterns":      len(high_freq_patterns),
        },
    }

    out_path = output_dir / OUTPUT_FILENAME
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=JSON_INDENT), encoding="utf-8")

    print(f"\n{'─'*SEPARATOR_WIDTH}")
    print(f"✅ 추출 완료 → {out_path}")
    print(f"\n📋 요약:")
    for k, v in output["summary"].items():
        print(f"  {k}: {v}")
    print(f"\n💡 이 JSON을 LLM Step 2에 전달하세요.")
    print(f"   LLM은 이 파일만 읽고 rules_draft.md + rag_items.md를 작성합니다.\n")


if __name__ == "__main__":
    main()
