---
name: request-api-key
description: Requests Upstage API key via Channel.io when the key is not configured. Sends a message to Pete, waits for his reply, then writes the key to .env automatically.
---

# Request API Key via Channel.io

## Overview

When `UPSTAGE_API_KEY` is missing from `.env`, this skill:
1. Sends a request message to Pete's Channel.io group
2. Waits for the user to confirm Pete replied
3. Reads the key from the thread and writes it to `.env`

**Language:** Detect the language from the user's first message and respond in that language throughout. Support Korean (한국어) and Japanese (日本語). Default to Korean if language is unclear.

## Steps

### 1. Check Current API Key Status

**Constraints:**
- You MUST run: `grep -s "UPSTAGE_API_KEY" .env`
- If the key exists, starts with `up_`, and is NOT the placeholder `up_YOUR_API_KEY_HERE` → STOP and tell the user the key is already configured
- You MUST get requester info: `hostname` and `whoami`

### 2. Send Request to Pete via Channel.io

**Constraints:**
- You MUST call `mcp__team-chat-mcp__send_team_chat_message` with `groupId: "531940"`
- You MUST set `userName` to `{username} ({hostname})`
- You MUST save the returned `messageId` for thread lookup in Step 3

**Message template:**
```
🔑 Upstage API 키 요청

안녕하세요, 피트님!
{username} ({hostname})에서 SOP 파이프라인을 실행하려고 합니다.
Upstage API 키가 필요합니다. 키를 이 스레드에 답장해 주세요 🙏
```

**Expected Output:**
```
✅ 피트님께 요청을 보냈습니다!
   Channel.io에서 답장이 오면 아래 버튼을 눌러주세요.
```

### 3. Wait for Pete's Reply

**Constraints:**
- You MUST use AskUserQuestion with two options:
  - "답장 왔어요" — Pete replied, check the thread now
  - "잠깐 기다릴게요" — not yet, will notify later
- If user selects "잠깐 기다릴게요", tell them to re-run `/request-api-key` when Pete replies and STOP
- If user selects "답장 왔어요", proceed to get the thread

### 4. Find Pete's Key and Save to .env

Pete may reply in the thread or directly in the group — check both.

**Constraints:**
- First, call `mcp__team-chat-mcp__get_team_chat_thread` with the `messageId` from Step 2, and scan replies for a message from personId `592317` containing `up_[a-zA-Z0-9_]+`
- If not found in thread, call `mcp__team-chat-mcp__get_team_chat_messages` with `groupId: "531940"`, `limit: 10`, `sortOrder: "desc"` and scan for a message from personId `592317` containing `up_[a-zA-Z0-9_]+`
- You MUST extract the key value from whichever location it's found
- You MUST verify the key starts with `up_` and is at least 20 characters
- If still not found, ask user to copy-paste Pete's message directly via AskUserQuestion
- If `.env` does not exist, create it: `cp .env.example .env`
- You MUST replace the UPSTAGE_API_KEY line using the Edit tool
- You MUST verify: `grep UPSTAGE_API_KEY .env`
- You MUST NOT display the full key — show only first 8 chars + `...`

### 5. Verify and Continue

**Constraints:**
- You MUST run: `python3 -c "import sys; sys.path.insert(0, '.'); from scripts.config import UPSTAGE_API_KEY; print('OK')"`
- If OK → inform the user setup is complete, suggest `/stage1-clustering` or `/userchat-to-sop-pipeline`
- If fails → tell user to restart Claude Code

**Expected Output:**
```
🎉 API 키 설정 완료! (up_xxxxx...)
   이제 파이프라인을 실행할 수 있습니다.
   👉 /stage1-clustering  또는  /userchat-to-sop-pipeline
```

## Troubleshooting

### Key not found in thread
- Ask user to copy-paste Pete's message directly via AskUserQuestion
- Validate it starts with `up_`

### Python verification fails
- Check `.env` is in project root: `cat .env`
- Ask user to restart Claude Code and retry
