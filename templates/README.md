# Templates

파이프라인 각 단계에서 사용하는 출력 템플릿 모음입니다.

## SOP 템플릿 (Stage 3)

| 파일 | 용도 |
|------|------|
| `HT_template.md` | **How-To SOP** — 정보 제공·안내 목적의 SOP. 제품 이용 방법, 정책 안내, 프로세스 가이드 등 "어떻게 하나요?" 유형의 반복 문의 대응에 사용 |
| `TS_template.md` | **Troubleshooting SOP** — 문제 해결 목적의 SOP. 오류 진단, 클레임 처리, 환불/교환, 불만 응대 등 "안 돼요/문제가 생겼어요" 유형의 이슈 대응에 사용 |
| `기존 템플릿.md` | **원본 레거시 템플릿** — HT/TS 분리 이전에 사용하던 단일 SOP 양식. 현재 파이프라인에서는 미사용이나 참고용으로 보존 |

## 플로우차트 템플릿 (Stage 4)

| 파일 | 용도 |
|------|------|
| `FLOWCHART_template.md` | **Mermaid 플로우차트** — Stage 3 SOP를 시각화할 때 사용. 고객 문의 → 분기 조건 → 상담사 연결 흐름을 색상 코딩된 다이어그램으로 표현 |

## ALF 구축 패키지 템플릿 (Stage 5)

| 파일 | 용도 |
|------|------|
| `ALF_PACKAGE_template.md` | **ALF 구축 패키지** — Stage 5 최종 통합 보고서 템플릿. ROI 요약, 교차분석 결과, 자동화 전략, Rules Draft 요약, RAG 항목 요약, 구축 로드맵을 포함하는 의사결정용 패키지 |
| `AUTOMATION_ANALYSIS_template.md` | **자동화 가능성 분석** — 대화유형 분류 결과를 해석하는 분석 보고서 템플릿. 히트맵 해석, 유형별 ALF 처리 전략, Phase 우선순위, 클러스터별 인사이트 포함 |
| `RAG_ITEMS_template.md` | **RAG 지식 DB 등록 항목** — ALF 구축 시 벡터 DB에 등록해야 할 지식 항목 목록 템플릿. Priority 1(즉시 등록) / Priority 2(Phase 2 이후) / 고객사 추가 권장 3단계로 구성 |
| `SALES_REPORT_template.md` | **ROI 영업 보고서** — `generate_sales_report.py` 스크립트가 자동 생성하는 보고서의 구조 참고용 템플릿. 도입 시나리오, ROI 상세 계산, 리소스 테이블 포함 |
| `최종 분석 리포트 템플릿.md` | **최종 분석 리포트 (Rosagi 프레임워크)** — 상담주제 × 대화유형 2차원 교차분석 결과를 고객사 내부 팀에게 전달하는 데이터 분석 보고서 템플릿. 데이터 개요, 분포 분석, 교차분석, 자동화 전략, 우선순위 권고 포함 |

## 디렉토리

```
templates/
├── HT_template.md                  # Stage 3 — How-To SOP
├── TS_template.md                  # Stage 3 — Troubleshooting SOP
├── 기존 템플릿.md                  # 레거시 (참고용)
├── FLOWCHART_template.md           # Stage 4 — Mermaid 플로우차트
├── ALF_PACKAGE_template.md         # Stage 5 — ALF 구축 패키지 (통합 보고서)
├── AUTOMATION_ANALYSIS_template.md # Stage 5 — 자동화 가능성 분석
├── RAG_ITEMS_template.md           # Stage 5 — RAG 지식 DB 등록 항목
├── SALES_REPORT_template.md        # Stage 5 — ROI 영업 보고서
├── 최종 분석 리포트 템플릿.md      # Stage 5 — 최종 분석 리포트 (Rosa)
└── examples/                       # 작성 예시 파일
```
