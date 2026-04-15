#!/usr/bin/env python3
"""Channel.io Desk API - RAG 문서 일괄 업로드 (x-account 인증)"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import glob


def make_headers(x_account: str) -> dict:
    return {
        "x-account": x_account,
        "Cookie": f"x-account={x_account}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ── Markdown → Channel.io Document Body 변환 ──

def md_to_channel_body(md_text: str) -> list:
    """Markdown 텍스트를 Channel.io document body 포맷(JSON array)으로 변환"""
    lines = md_text.split("\n")
    body = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # 빈 줄 / HR 무시
        if not line.strip() or line.strip() in ("---", "***", "___"):
            i += 1
            continue

        # 헤딩
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            body.append({
                "type": "heading",
                "attrs": {"level": level},
                "content": [_inline(text)]
            })
            i += 1
            continue

        # 테이블
        if "|" in line and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1].strip()):
            table_node, i = _parse_table(lines, i)
            body.append(table_node)
            continue

        # 순서 없는 리스트
        if re.match(r"^[-*]\s+", line):
            items, i = _collect_list(lines, i, ordered=False)
            body.append({"type": "bullets", "content": items})
            continue

        # 순서 있는 리스트
        if re.match(r"^\d+\.\s+", line):
            items, i = _collect_list(lines, i, ordered=True)
            body.append({"type": "numberedList", "content": items})
            continue

        # 인용 블록
        if line.startswith(">"):
            quote_lines = []
            while i < len(lines) and lines[i].startswith(">"):
                quote_lines.append(re.sub(r"^>\s?", "", lines[i]))
                i += 1
            quote_text = " ".join(quote_lines).strip()
            body.append({
                "type": "blockquote",
                "content": [{"type": "text", "content": [_inline(quote_text)]}]
            })
            continue

        # 일반 텍스트 단락
        para_lines = []
        while i < len(lines) and lines[i].strip() and not _is_block_start(lines[i]):
            para_lines.append(lines[i])
            i += 1
        if para_lines:
            body.append({
                "type": "text",
                "content": [_inline(" ".join(para_lines))]
            })

    return body


def _is_block_start(line: str) -> bool:
    if re.match(r"^#{1,6}\s+", line):
        return True
    if re.match(r"^[-*]\s+", line):
        return True
    if re.match(r"^\d+\.\s+", line):
        return True
    if line.startswith(">"):
        return True
    if line.strip() in ("---", "***", "___"):
        return True
    if "|" in line:
        return True
    return False


def _inline(text: str) -> dict:
    """인라인 텍스트를 Channel.io text 노드로 변환 (bold 지원)"""
    # **bold** 파싱
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    if len(parts) == 1:
        return {"type": "plain", "attrs": {"text": text}}

    content = []
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            content.append({
                "type": "plain",
                "attrs": {"text": part[2:-2]},
                "marks": [{"type": "bold"}]
            })
        else:
            content.append({"type": "plain", "attrs": {"text": part}})

    return {"type": "text", "content": content} if len(content) > 1 else content[0]


def _collect_list(lines: list, i: int, ordered: bool) -> tuple:
    """리스트 아이템 수집"""
    items = []
    pattern = r"^\d+\.\s+" if ordered else r"^[-*]\s+"
    while i < len(lines) and re.match(pattern, lines[i]):
        text = re.sub(pattern, "", lines[i]).strip()
        items.append({
            "type": "listItem",
            "content": [{"type": "text", "content": [_inline(text)]}]
        })
        i += 1
    return items, i


def _parse_table(lines: list, i: int) -> tuple:
    """마크다운 테이블을 Channel.io table 노드로 변환"""
    header_cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
    i += 2  # skip header + separator

    rows = []
    # Header row
    rows.append({
        "type": "tableRow",
        "content": [
            {"type": "tableHeader", "content": [{"type": "text", "content": [_inline(c)]}]}
            for c in header_cells
        ]
    })

    # Data rows
    while i < len(lines) and "|" in lines[i] and lines[i].strip():
        cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
        rows.append({
            "type": "tableRow",
            "content": [
                {"type": "tableCell", "content": [{"type": "text", "content": [_inline(c)]}]}
                for c in cells
            ]
        })
        i += 1

    return {"type": "table", "content": rows}, i


# ── API 호출 ──

def api_request(url: str, headers: dict, method: str = "GET", data: dict = None) -> dict:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode("utf-8"))


def create_and_publish_article(base_url: str, headers: dict, name: str, channel_body: list) -> dict:
    """Article 생성 -> body/title 설정 -> publish"""
    result = api_request(
        f"{base_url}/articles", headers, "POST",
        {"name": name, "language": "ko"}
    )
    article_id = result["article"]["id"]
    revision_id = result["revision"]["id"]

    api_request(
        f"{base_url}/articles/{article_id}/revisions/{revision_id}",
        headers, "PATCH",
        {"title": name, "name": name, "body": channel_body}
    )

    api_request(
        f"{base_url}/articles/{article_id}/revisions/{revision_id}/publish",
        headers, "PUT", {}
    )

    return {"article_id": article_id, "revision_id": revision_id}


def main():
    if len(sys.argv) < 5:
        print("Usage: python3 upload_documents.py <docs_dir> <channelId> <spaceId> <xAccount> [env]")
        print()
        print("  docs_dir   : Markdown 문서 디렉토리 경로")
        print("  channelId  : 채널 ID")
        print("  spaceId    : Document Space ID")
        print("  xAccount   : x-account 인증 토큰")
        print("  env        : prod (기본) 또는 exp")
        sys.exit(1)

    docs_dir = sys.argv[1]
    channel_id = sys.argv[2]
    space_id = sys.argv[3]
    x_account = sys.argv[4]
    env = sys.argv[5] if len(sys.argv) > 5 else "prod"

    if env == "exp":
        host = "https://document-api.exp.channel.io"
    else:
        host = "https://document-api.channel.io"

    base_url = f"{host}/desk/v1/channels/{channel_id}/spaces/{space_id}"
    headers = make_headers(x_account)

    md_files = sorted(glob.glob(os.path.join(docs_dir, "*.md")))
    if not md_files:
        print(f"[ERROR] {docs_dir}에 .md 파일이 없습니다.")
        sys.exit(1)

    print(f"{'=' * 55}")
    print(f" Document Upload | channel={channel_id} space={space_id} | {len(md_files)}개 파일")
    print(f"{'=' * 55}")
    print()

    success = 0
    fail = 0

    for idx, filepath in enumerate(md_files, 1):
        filename = os.path.basename(filepath)
        name = os.path.splitext(filename)[0].replace("_", " ")

        with open(filepath, "r", encoding="utf-8") as f:
            md_content = f.read()

        first_line = md_content.split("\n")[0] if md_content else ""
        if first_line.startswith("# "):
            name = first_line.lstrip("# ").strip()

        channel_body = md_to_channel_body(md_content)

        try:
            result = create_and_publish_article(base_url, headers, name, channel_body)
            print(f"  [{idx:2d}/{len(md_files)}] OK {name}  (id={result['article_id']})")
            success += 1
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")[:150] if e.fp else str(e)
            print(f"  [{idx:2d}/{len(md_files)}] FAIL {name}  ({e.code}: {error_body})")
            fail += 1
        except Exception as e:
            print(f"  [{idx:2d}/{len(md_files)}] FAIL {name}  ({e})")
            fail += 1

        time.sleep(0.3)

    print()
    print(f"{'=' * 55}")
    print(f" 완료: {success}개 성공" + (f", {fail}개 실패" if fail else ""))
    print(f"{'=' * 55}")


if __name__ == "__main__":
    main()
