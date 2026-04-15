#!/bin/bash
# Expert ALF Toolkit 설치 스크립트

set -e

echo "=========================================="
echo "  Expert ALF Toolkit 설치"
echo "=========================================="
echo ""

# ── 1. Python 확인 ──
echo "[1/5] Python 확인 중..."
if ! command -v python3 &>/dev/null; then
  echo "  Python 3이 설치되어 있지 않습니다."
  echo "  자동 설치를 시도합니다..."
  echo ""

  if command -v brew &>/dev/null; then
    echo "  Homebrew 감지 -> brew install python3 실행 중..."
    brew install python3
  else
    if ! command -v pyenv &>/dev/null; then
      echo "  pyenv 설치 중..."
      curl -fsSL https://pyenv.run | bash

      SHELL_RC="$HOME/.zshrc"
      [ -f "$HOME/.bashrc" ] && SHELL_RC="$HOME/.bashrc"

      echo '' >> "$SHELL_RC"
      echo '# pyenv' >> "$SHELL_RC"
      echo 'export PYENV_ROOT="$HOME/.pyenv"' >> "$SHELL_RC"
      echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> "$SHELL_RC"
      echo 'eval "$(pyenv init -)"' >> "$SHELL_RC"

      export PYENV_ROOT="$HOME/.pyenv"
      export PATH="$PYENV_ROOT/bin:$PATH"
      eval "$(pyenv init -)"
    fi

    echo "  Python 3.11 설치 중... (몇 분 소요될 수 있습니다)"
    pyenv install 3.11.9
    pyenv global 3.11.9
  fi

  if ! command -v python3 &>/dev/null; then
    echo ""
    echo "  자동 설치에 실패했습니다."
    echo "  https://www.python.org/downloads/ 에서 직접 설치 후 다시 실행해주세요."
    exit 1
  fi
  echo "  Python 설치 완료"
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
  echo "  Python 3.9 이상이 필요합니다. (현재: $PYTHON_VERSION)"
  exit 1
fi

echo "  OK Python $PYTHON_VERSION"

# ── 2. SOP Pipeline 의존성 (venv + pip) ──
echo ""
echo "[2/5] SOP Pipeline 패키지 설치..."
if [ ! -d "venv" ]; then
  python3 -m venv venv
  echo "  가상환경 생성: venv/"
else
  echo "  기존 가상환경 사용: venv/"
fi

source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  OK SOP Pipeline 패키지 설치 완료"

# ── 3. QA Agent 의존성 (uv) ──
echo ""
echo "[3/5] QA Agent 패키지 설치..."
if ! command -v uv &>/dev/null; then
  echo "  uv 설치 중..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

uv sync --all-groups 2>/dev/null || uv sync
uv run playwright install chromium
echo "  OK QA Agent 패키지 + Playwright 설치 완료"

# ── 4. 환경 변수 ──
echo ""
echo "[4/5] 환경 변수 설정..."
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "  .env 파일이 생성되었습니다."
  echo "  ANTHROPIC_API_KEY (필수) 와 UPSTAGE_API_KEY (선택) 를 설정해주세요."
else
  echo "  OK .env 파일 존재"
fi

# ── 5. 디렉토리 생성 + 검증 ──
echo ""
echo "[5/5] 설치 검증..."
mkdir -p data results cache storage/runs

# SOP 패키지 검증
python3 -c "import pandas; import numpy; import sklearn; import openpyxl; import tqdm; import dotenv" 2>/dev/null
if [ $? -eq 0 ]; then
  echo "  OK SOP 핵심 패키지 정상"
else
  echo "  WARN 일부 패키지 import 실패 -- pip install -r requirements.txt 재실행 필요"
fi

python3 -c "import sentence_transformers" 2>/dev/null
if [ $? -eq 0 ]; then
  echo "  OK 로컬 임베딩 모델 (sentence-transformers) 정상"
else
  echo "  INFO sentence-transformers 미설치 -- Solar API fallback 사용"
fi

# QA 패키지 검증
uv run python3 -c "import playwright; import anthropic; import yaml" 2>/dev/null
if [ $? -eq 0 ]; then
  echo "  OK QA Agent 핵심 패키지 정상"
else
  echo "  WARN QA Agent 패키지 확인 필요 -- uv sync 재실행"
fi

echo ""
echo "=========================================="
echo "  설치 완료!"
echo "=========================================="
echo ""
echo "  사용 가능한 스킬:"
echo ""
echo "  [SOP Pipeline]"
echo "  /userchat-to-alf-setup        전체 파이프라인 (Stage 1-7)"
echo "  /stage1-clustering           Stage 1: 클러스터링"
echo "  /stage2-extraction           Stage 2: 패턴 추출"
echo "  /stage3-sop-generation       Stage 3: SOP 생성"
echo "  /stage4-flowchart-generation Stage 4: 플로우차트 생성"
echo "  /stage5-sop-to-guide         Stage 5: ALF 패키지 생성"
echo "  /stage6-alf-document-export  Stage 6: 문서 분리"
echo "  /stage7-deployment-scenario  Stage 7: 배포 시나리오"
echo ""
echo "  [QA]"
echo "  /qa-agent                    QA 파이프라인 (시나리오 -> 테스트 -> 채점)"
echo "  /scoring-agent               채점만 재실행"
echo ""
echo "  [ALF 세팅]"
echo "  /settings-task               Task JSON 업로드"
echo "  /settings-rag                RAG 지식 문서 업로드"
echo ""
echo "  시작하기:"
echo "  1. .env 에 API 키 설정"
echo "  2. data/ 폴더에 고객 상담 Excel 파일 넣기"
echo "  3. Claude Code에서 이 폴더 열기"
echo "  4. /userchat-to-alf-setup 실행"
echo ""
