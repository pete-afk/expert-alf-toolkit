# Expert ALF Toolkit

채널톡 ALF 세팅을 위한 엑스퍼트 전용 도구 모음입니다.

## 설치

```bash
git clone https://github.com/channel-io/expert-alf-toolkit.git
cd expert-alf-toolkit
sh setup.sh
```

`setup.sh`가 자동으로 처리하는 것:
- Python 확인 (없으면 자동 설치)
- SOP Pipeline 의존성 설치 (venv + pip)
- QA Agent 의존성 설치 (uv + Playwright)
- `.env` 파일 생성

## 사전 준비

1. **Claude Code 설치**: `curl -fsSL https://claude.ai/install.sh | sh`
2. **API 키 설정**: `.env` 파일에 `ANTHROPIC_API_KEY` 입력
3. **상담 데이터**: `data/` 폴더에 고객 상담 Excel 파일 넣기

## 사용법

Claude Code에서 이 폴더를 열고 스킬을 실행합니다.

```bash
cd expert-alf-toolkit
claude
```

### SOP 파이프라인 (상담 데이터 -> ALF 설정)

```
> /userchat-to-sop-pipeline
```

전체 파이프라인을 자동 실행합니다. 개별 단계도 실행 가능:

| 스킬 | 단계 |
|------|------|
| `/stage1-clustering` | 상담 데이터 클러스터링 |
| `/stage2-extraction` | 패턴 + FAQ 추출 |
| `/stage3-sop-generation` | SOP 문서 생성 |
| `/stage4-flowchart-generation` | 플로우차트 생성 |
| `/stage5-sop-to-guide` | ALF 구현 패키지 |
| `/stage6-alf-document-export` | 문서 개별 분리 |
| `/stage7-deployment-scenario` | 배포 시나리오 + QA 세트 |

### QA 테스트 (ALF 응답 품질 측정)

```
> /qa-agent
```

SOP 분석 결과 + 테스트 채널 URL로 자동 QA를 실행합니다.

### ALF 세팅 (채널톡에 적용)

```
> /settings-task task.json 채널ID x-account
> /settings-rag results/회사/06_rag_documents/ 채널ID 스페이스ID x-account
```

## 산출물

```
results/{회사명}/
├── 01_clustering/      # 클러스터링 결과
├── 02_extraction/      # 패턴 + FAQ
├── 03_sop/             # SOP 문서
├── 04_tasks/           # Task 정의
├── 05_sales_report/    # ALF 패키지 (규칙, RAG, 분석)
├── 06_rag_documents/   # 개별 RAG 지식 문서
└── 07_deployment/      # 배포 시나리오 + QA 세트

storage/runs/{run-id}/  # QA 테스트 결과
├── scenarios.json      # 테스트 시나리오
├── transcripts.jsonl   # ALF 대화 기록
├── scores.json         # 채점 결과
└── report_slides.html  # 발표 슬라이드
```
