#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────
# upload-task.sh
# Task JSON 파일을 채널톡 ALF Task API에 업로드
# ──────────────────────────────────────────────
# 사용법:
#   ./upload-task.sh <file_or_dir> <channel_id> <x_account> [env] [task_id]
#
# 예시:
#   # 단일 파일 업로드 (prod)
#   ./upload-task.sh ./task.json 222425 eyJhbG...
#
#   # 디렉토리 내 모든 JSON 업로드 (exp)
#   ./upload-task.sh ./tasks/ 222425 eyJhbG... exp
#
#   # 기존 Task 수정
#   ./upload-task.sh ./task.json 222425 eyJhbG... prod 51057
# ──────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

usage() {
  echo "사용법: $0 <file_or_dir> <channel_id> <x_account> [env] [task_id]"
  echo ""
  echo "  file_or_dir  Task JSON 파일 경로 또는 디렉토리 (디렉토리면 *.json 전부 업로드)"
  echo "  channel_id   채널 ID"
  echo "  x_account    인증 토큰 (x-account)"
  echo "  env          prod (기본) 또는 exp"
  echo "  task_id      수정할 기존 Task ID (생략 시 신규 생성)"
  exit 1
}

# ── 인자 검증 ──
[[ $# -lt 3 ]] && usage

FILE_OR_DIR="$1"
CHANNEL_ID="$2"
X_ACCOUNT="$3"
ENV="${4:-prod}"
TASK_ID="${5:-}"

if [[ "$ENV" == "exp" ]]; then
  ALF_HOST="https://front-alf-desk-api.exp.channel.io"
else
  ALF_HOST="https://front-alf-desk-api.channel.io"
fi

BASE_PATH="/desk/channels/${CHANNEL_ID}/front-alf/v2"

# ── python3 확인 ──
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}[ERROR] python3이 필요합니다.${NC}"
  exit 1
fi

# ── JSON 파일 목록 수집 ──
FILES=()
if [[ -d "$FILE_OR_DIR" ]]; then
  while IFS= read -r f; do
    FILES+=("$f")
  done < <(find "$FILE_OR_DIR" -maxdepth 1 -name '*.json' -type f | sort)
  if [[ ${#FILES[@]} -eq 0 ]]; then
    echo -e "${RED}[ERROR] ${FILE_OR_DIR}에 JSON 파일이 없습니다.${NC}"
    exit 1
  fi
  echo -e "${CYAN}[INFO] ${#FILES[@]}개 JSON 파일 발견${NC}"
elif [[ -f "$FILE_OR_DIR" ]]; then
  FILES=("$FILE_OR_DIR")
else
  echo -e "${RED}[ERROR] 파일/디렉토리를 찾을 수 없습니다: ${FILE_OR_DIR}${NC}"
  exit 1
fi

# ── folderId 조회 (신규 생성 시) ──
FOLDER_ID=""
if [[ -z "$TASK_ID" ]]; then
  echo -e "${CYAN}[INFO] 폴더 목록 조회 중...${NC}"
  FOLDERS_RESP=$(curl -s -X GET \
    "${ALF_HOST}${BASE_PATH}/task/folders/root/contents" \
    -H "Content-Type: application/json" \
    -H "x-account: ${X_ACCOUNT}" \
    -H "Cookie: x-account=${X_ACCOUNT}")

  # 폴더 목록 파싱 및 선택
  FOLDER_ID=$(python3 -c "
import json, sys
resp = json.loads('''${FOLDERS_RESP}''')
folders = resp.get('childFolders', [])
if not folders:
    print('EMPTY')
    sys.exit(0)
for i, f in enumerate(folders):
    print(f'{i+1}) {f[\"name\"]} (id: {f[\"id\"]})', file=sys.stderr)
print('SELECT', file=sys.stdout)
" 2>&1)

  if [[ "$FOLDER_ID" == "EMPTY" ]]; then
    echo -e "${YELLOW}[WARN] 폴더가 없습니다. '기본' 폴더를 생성합니다.${NC}"
    CREATE_RESP=$(curl -s -X POST \
      "${ALF_HOST}${BASE_PATH}/task/folders" \
      -H "Content-Type: application/json" \
      -H "x-account: ${X_ACCOUNT}" \
      -H "Cookie: x-account=${X_ACCOUNT}" \
      -d '{"name": "기본"}')
    FOLDER_ID=$(python3 -c "import json; print(json.loads('${CREATE_RESP}').get('id',''))")
    echo -e "${GREEN}[OK] 폴더 생성 완료: ${FOLDER_ID}${NC}"
  else
    # 폴더 선택 UI
    FOLDER_LIST=$(python3 -c "
import json
resp = json.loads('''${FOLDERS_RESP}''')
folders = resp.get('childFolders', [])
for i, f in enumerate(folders):
    print(f'  {i+1}) {f[\"name\"]} (id: {f[\"id\"]})')
")
    echo -e "${CYAN}업로드할 폴더를 선택하세요:${NC}"
    echo "$FOLDER_LIST"
    echo ""
    read -rp "번호 입력: " FOLDER_NUM

    FOLDER_ID=$(python3 -c "
import json
resp = json.loads('''${FOLDERS_RESP}''')
folders = resp.get('childFolders', [])
idx = int('${FOLDER_NUM}') - 1
if 0 <= idx < len(folders):
    print(folders[idx]['id'])
else:
    print('INVALID')
")

    if [[ "$FOLDER_ID" == "INVALID" ]]; then
      echo -e "${RED}[ERROR] 잘못된 번호입니다.${NC}"
      exit 1
    fi
  fi
  echo -e "${GREEN}[OK] 선택된 폴더: ${FOLDER_ID}${NC}"
  echo ""
fi

# ── 업로드 함수 ──
upload_task() {
  local file="$1"
  local filename
  filename=$(basename "$file")

  # JSON 변환: wrapper → flat + folderId 추가
  local body
  body=$(python3 -c "
import json, sys
with open('${file}', 'r') as f:
    data = json.load(f)

# wrapper 형태면 풀어서 flat으로
if 'task' in data and isinstance(data['task'], dict):
    body = data['task']
    if 'taskEditorPosition' in data:
        body['taskEditorPosition'] = data['taskEditorPosition']
else:
    body = data

# folderId 추가 (신규 생성 시)
folder_id = '${FOLDER_ID}'
if folder_id:
    body['folderId'] = folder_id

json.dump(body, sys.stdout, ensure_ascii=False)
")

  local method url
  if [[ -n "$TASK_ID" ]]; then
    method="PUT"
    url="${ALF_HOST}${BASE_PATH}/tasks/${TASK_ID}"
  else
    method="POST"
    url="${ALF_HOST}${BASE_PATH}/tasks"
  fi

  echo -ne "${CYAN}[UPLOAD] ${filename} ... ${NC}"

  local resp
  resp=$(curl -s -X "$method" "$url" \
    -H "Content-Type: application/json" \
    -H "x-account: ${X_ACCOUNT}" \
    -H "Cookie: x-account=${X_ACCOUNT}" \
    -d "$body")

  # 결과 파싱
  python3 -c "
import json, sys
resp = json.loads('''$(echo "$resp" | python3 -c "import sys; print(sys.stdin.read().replace(\"'\", \"\\\\'\"))")''')
if 'frontAlfTask' in resp:
    t = resp['frontAlfTask']
    print(f'\033[0;32mOK\033[0m  id={t[\"id\"]}  name=\"{t[\"name\"]}\"  state={t[\"state\"]}')
elif 'errors' in resp:
    errs = ', '.join(e.get('message','') for e in resp['errors'])
    print(f'\033[0;31mFAIL\033[0m  {errs}')
else:
    print(f'\033[0;31mFAIL\033[0m  {json.dumps(resp, ensure_ascii=False)[:200]}')
"
}

# ── 실행 ──
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN} Task Upload  |  env=${ENV}  channel=${CHANNEL_ID}${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

SUCCESS=0
FAIL=0

for file in "${FILES[@]}"; do
  upload_task "$file" && ((SUCCESS++)) || ((FAIL++))
done

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN} 완료: ${SUCCESS}개 성공${NC}$([ "$FAIL" -gt 0 ] && echo -e ", ${RED}${FAIL}개 실패${NC}")"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
