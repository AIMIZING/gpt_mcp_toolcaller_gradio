# notion_mcp_server.py
import os
from typing import List, Dict, Any

from dotenv import load_dotenv
from notion_client import Client
from fastmcp import FastMCP

# ──────────────────── 1) Notion 클라이언트 ────────────────────
load_dotenv()
notion = Client(auth=os.getenv("NOTION_TOKEN"))

# ──────────────────── 2) FastMCP 서버 ────────────────────
mcp = FastMCP(
    name="notion-mcp-server",
    instructions="Notion 데이터를 조회하고 분석하는 도구들입니다."
)

# ──────────────────── 3) 공통 유틸 ────────────────────
def safe_get(d: Dict[str, Any] | None, *keys: str, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
    return d if d is not None else default


def summarize_text(text: str, head: int = 200) -> str:
    return f"전체 길이 {len(text)}자, 앞부분:\n{text[:head]}"

# ──────────────────── 4) MCP 도구 ────────────────────
@mcp.tool()
def search_databases(query: str) -> List[dict]:
    """Notion에서 데이터베이스를 검색"""
    resp = notion.search(query=query,
                         filter={"property": "object", "value": "database"})
    results = [
        {
            "id": db["id"],
            "title": "".join(t.get("plain_text", "") for t in db.get("title", []))
        }
        for db in resp.get("results", [])
    ]
    return results

@mcp.tool()
def get_projects(database_id: str) -> Dict[str, List[dict]]:
    """특정 데이터베이스의 프로젝트 목록 반환"""
    resp = notion.databases.query(database_id=database_id)
    projects: List[dict] = []

    for page in resp.get("results", []):
        props = page.get("properties", {})

        title_parts = safe_get(props, "프로젝트 이름", "title", default=[])
        name = "".join(t.get("plain_text", "") for t in title_parts) if title_parts else ""

        projects.append({
            "id": page["id"],
            "프로젝트 이름": name,
            "담당자": [p.get("name") for p in safe_get(props, "담당자", "people", default=[])],
            "상태": safe_get(props, "상태", "status", "name"),
            "시작일": safe_get(props, "시작일", "date", "start"),
            "종료일": safe_get(props, "종료일", "date", "start"),
            "우선순위": safe_get(props, "우선순위", "select", "name"),
            "팀": [t.get("name") for t in safe_get(props, "팀", "multi_select", default=[])],
            "파일 첨부": [
                f.get("name") or safe_get(f, "external", "url")
                for f in safe_get(props, "파일 첨부", "files", default=[])
            ],
        })

    return {"projects": projects}

@mcp.tool()
def get_database_schema(database_id: str) -> Dict[str, Dict[str, List[str]]]:
    """select·multi_select·status 옵션 목록 반환"""
    db = notion.databases.retrieve(database_id=database_id)
    schema: Dict[str, List[str]] = {}
    for name, prop in db.get("properties", {}).items():
        p_type = prop["type"]
        if p_type in ("select", "multi_select", "status"):
            schema[name] = [o["name"] for o in prop[p_type].get("options", [])]
    return {"schema": schema}

@mcp.tool()
def analyze_projects(analyze: List[dict]) -> Dict[str, List[dict]]:
    """(예시) 분석 대상 그대로 반환"""
    return {"projects": analyze}

@mcp.tool()
def get_page_summary(page_id: str) -> str:
    """페이지 전체 문단 텍스트를 요약"""
    children = notion.blocks.children.list(page_id)
    texts = []
    for block in children.get("results", []):
        para = block.get("paragraph")
        if para:
            texts.extend(t.get("plain_text", "") for t in para.get("text", []))
    return summarize_text("\n".join(texts))

# ──────────────────── 5) 서버 실행 ────────────────────
if __name__ == "__main__":
    import sys
    print("🚀 FastMCP Notion 서버를 실행합니다...", file=sys.stderr)
    print("✅ http://localhost:8000/mcp 에서 요청 대기 중", file=sys.stderr)
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
        path="/mcp",
    )
