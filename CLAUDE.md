# Expert ALF Toolkit

> 채널톡 ALF 세팅을 위한 엑스퍼트 전용 도구 모음.
> 상담 데이터 분석 -> SOP 생성 -> ALF 세팅 -> QA 테스트까지 전 과정을 Claude Code 스킬로 수행합니다.

## 스킬 목록

### SOP 파이프라인 (상담 데이터 -> ALF 설정 산출물)

| 스킬 | 설명 |
|------|------|
| `/userchat-to-alf-setup` | 전체 파이프라인 자동 실행 (Stage 1-7) |
| `/stage1-clustering` | 상담 데이터 클러스터링 + 태깅 |
| `/stage2-extraction` | 패턴 추출 + FAQ 생성 |
| `/stage3-sop-generation` | SOP 문서 생성 |
| `/stage4-flowchart-generation` | Mermaid 플로우차트 생성 |
| `/stage5-sop-to-guide` | ALF 구현 패키지 (규칙 + RAG + 자동화 분석) |
| `/stage6-alf-document-export` | 규칙/RAG 문서 개별 파일 분리 |
| `/stage7-deployment-scenario` | 배포 시나리오 + QA 세트 생성 |

### QA 파이프라인 (ALF 응답 품질 자동 측정)

| 스킬 | 설명 |
|------|------|
| `/qa-agent` | 전체 QA 파이프라인 (시나리오 생성 -> ALF 테스트 -> 채점 -> 리포트) |
| `/scoring-agent` | 기존 run의 채점만 재실행 |

### ALF 세팅 (채널톡에 직접 적용)

| 스킬 | 설명 |
|------|------|
| `/settings-task` | Task JSON을 채널톡에 업로드 (생성/수정) |
| `/settings-rag` | RAG 지식 문서를 채널톡에 일괄 업로드 |

### 유틸리티

| 스킬 | 설명 |
|------|------|
| `/request-api-key` | Upstage API 키 요청 |

## 디렉토리 구조

```
data/           → 입력: 고객 상담 Excel 파일
results/        → SOP 파이프라인 산출물 (회사별)
storage/runs/   → QA Agent 실행 결과 (run별)
scripts/        → SOP 파이프라인 Python 스크립트
tools/          → QA Agent Python 도구
prompts/        → QA Agent 프롬프트
templates/      → SOP 생성 템플릿
```

## 인증

모든 채널톡 API 호출은 **x-account** 토큰으로 인증합니다.
- 채널톡 데스크에서 개발자 도구 > Network 탭에서 `x-account` 헤더 값을 복사
- 스킬 실행 시 인자로 전달

## 규칙

1. **보안**: `.env` 파일과 `x-account` 토큰은 절대 커밋하지 않음
2. **데이터**: `data/`, `results/`, `storage/` 는 gitignore 대상 (고객 데이터 보호)
3. **litellm 사용 금지**: 보안 위협으로 전 프로젝트 사용 금지. LLM 호출은 anthropic SDK 직접 사용

## 환경 설정

```bash
# 최초 1회
sh setup.sh

# 이후 사용 시
source venv/bin/activate   # SOP 파이프라인용
# uv는 자동으로 .venv 사용  # QA Agent용
```
