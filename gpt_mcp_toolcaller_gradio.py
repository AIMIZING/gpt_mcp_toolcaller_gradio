# gpt_mcp_gradio_autoload.py
import os, json, uuid, requests
import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI

# ──────────────────── 1) 환경 변수 & 클라이언트 ────────────────────
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MCP_URL = "http://localhost:8000/mcp"
session_id: str | None = None

# ──────────────────── 2) 세션 초기화 ────────────────────
def init_session() -> str:
    payload = {
        "jsonrpc": "2.0",
        "id": f"init-{uuid.uuid4()}",
        "method": "initialize",
        "params": {
            "protocolVersion": 1,
            "capabilities": {"tools": True},
            "clientInfo": {"name": "gradio-client", "version": "0.1"}
        }
    }
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json"
    }
    r = requests.post(MCP_URL, json=payload, headers=headers, timeout=10)
    r.raise_for_status()
    sid = r.headers.get("Mcp-Session-Id")
    if not sid:
        raise RuntimeError("세션 ID를 받지 못했습니다.")
    print(f"🔑 세션 확보: {sid}")

    init_done = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {}
    }
    headers["Mcp-Session-Id"] = sid
    requests.post(MCP_URL, json=init_done, headers=headers, timeout=5).raise_for_status()

    return sid

# ──────────────────── 3) GPT + MCP 대화 ────────────────────
def chat_with_tool(user_input: str):
    global session_id
    if session_id is None:
        session_id = init_session()

    messages = [
        {
            "role": "system",
            "content": (
                "당신은 사용자의 일반 대화에 답변하다가, ‘프로젝트’·‘데이터베이스’ "
                "같은 키워드가 포함되면 MCP 도구(search_databases 등)를 호출해야 합니다."
            )
        },
        {"role": "user", "content": user_input}
    ]

    projects_cache = None
    chat_kwargs = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "tool_choice": "auto",
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "search_databases",
                    "description": "Notion에서 사용자 질의에 맞는 데이터베이스 객체(스키마) 목록을 검색합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"}
                        },
                        "required": ["query"]
                    },
                    "returns": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "id": {"type": "string"},
                          "title": {"type": "string"}
                        },
                        "required": ["id", "title"]
                      }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_projects",
                    "description": "특정 database_id에 속한 모든 프로젝트 항목을 반환합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "database_id": {"type": "string"}
                        },
                        "required": ["database_id"]
                    },
                    "returns": {
                        "type": "object",
                        "properties": {
                            "projects": {
                                "type": "array",
                                "items": {"type": "object"}
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_database_schema",
                    "description": "특정 database_id의 속성 옵션(스키마) 전체를 반환합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "get_schema": {"type": "string"}
                        },
                        "required": ["get_schema"]
                    },
                    "returns": {
                        "type": "object",
                        "properties": {
                            "schema": {
                                "type": "object",
                                "additionalProperties": {
                                    "type": "array",
                                    "items": {"type": "string"}
                                }
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_projects",
                    "description": (
                        "조회된 프로젝트 목록을 받아, 아래 **분석 방식**에 따라 결과를 생성합니다:\n\n"
                        "① 정량 분석 (데이터 기반 통계)\n"
                        "- 총 프로젝트 개수, 완료/진행/보류 비율\n"
                        "- 평균 완료율, 전체 완료된 태스크 비율\n"
                        "- 평균 소요 시간(종료일–시작일), 마감 초과율, 지연 프로젝트 비율\n"
                        "- 우선순위(High/Medium/Low) 분포\n"
                        "- 담당자별 프로젝트 수 및 업무 편중 여부\n"
                        "- 팀(태그)별 프로젝트 분포\n\n"
                        "② 정성 분석 (내용 기반)\n"
                        "- 프로젝트 설명 텍스트 요약\n"
                        "- ‘지연’, ‘문제’, ‘막힘’ 키워드 탐색으로 리스크 탐지\n"
                        "- 비효율적인 일정·구조 개선 제안\n"
                        "- 프로젝트 간 연관성 매핑 (Relation 기반)\n\n"
                        "결과는 **예시 형태**로 아래처럼 출력하세요:\n"
                        "```\n"
                        "총 프로젝트 수: 35개 (완료 20, 진행 10, 보류 5)\n"
                        "평균 소요 기간: 12.4일 (평균 마감 초과: +3.2일)\n"
                        "High 우선순위 중 40% 지연됨\n\n"
                        "💬 개선 제안:\n"
                        "- 마감일 초과 건 多 → 중간 점검 주기 도입\n"
                        "- ‘마케팅’ 팀 프로젝트 진행률 낮음 → 인력 재배치 검토\n"
                        "```"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "analyze": {
                                "type": "array",
                                "items": {"type": "object"}
                            }
                        },
                        "required": ["analyze"]
                    },
                    "returns": {
                        "type": "object",
                        "properties": {
                            "analysis": {"type": "string"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_page_summary",
                    "description": "페이지 텍스트를 요약합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "페이지 ID"}
                        },
                        "required": ["page_id"]
                    }
                }
            }
        ]
    }

    while True:
        res = client.chat.completions.create(**chat_kwargs)
        ai_msg = res.choices[0].message

        # 도구 호출이 없으면 바로 응답 종료
        if not ai_msg.tool_calls:
            return ai_msg.content

        # 도구 호출 처리
        for call in ai_msg.tool_calls:
            fn_name = call.function.name
            fn_args = json.loads(call.function.arguments or "{}")

            # analyze_projects 호출 시 cached projects 주입
            if fn_name == "analyze_projects" and "analyze" not in fn_args:
                # ① 캐시가 비어 있으면 데이터베이스 검색 → 프로젝트 로드
                if not projects_cache:
                    # 1) 데이터베이스 검색
                    search_payload = {
                        "jsonrpc":"2.0","id":str(uuid.uuid4()),
                        "method":"tools/call",
                        "params":{"name":"search_databases","arguments":{"query":"프로젝트"}}
                    }
                    resp_db = requests.post(MCP_URL, json=search_payload, headers=headers, timeout=10)
                    parsed_db = parse_mcp_response(resp_db)
                    if isinstance(parsed_db, list):
                        db_list = parsed_db
                    elif isinstance(parsed_db, dict):
                        db_list = parsed_db.get("result") or parsed_db.get("databases") or []
                    else:
                        db_list = []

                    if not db_list:
                        return "⚠️ ‘프로젝트’ 데이터베이스를 찾지 못했습니다."

                    db_id = db_list[0].get("id")
                    if not db_id:
                        return "⚠️ 데이터베이스 ID를 파싱하지 못했습니다."

                    # 2) 프로젝트 목록 조회
                    proj_payload = {
                        "jsonrpc":"2.0","id":str(uuid.uuid4()),
                        "method":"tools/call",
                        "params":{"name":"get_projects","arguments":{"database_id":db_id}}
                    }
                    resp_proj = requests.post(MCP_URL, json=proj_payload, headers=headers, timeout=10)
                    projects_cache = parse_mcp_response(resp_proj).get("projects", [])
                    if not projects_cache:
                        return "⚠️ 조회된 프로젝트가 없습니다."

                # 3) 분석 인자로 주입
                fn_args["analyze"] = projects_cache

            # MCP 호출 준비
            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {"name": fn_name, "arguments": fn_args}
            }
            headers = {
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json; charset=utf-8",
                "Mcp-Session-Id": session_id
            }

            print(f"\n[📡 MCP 호출] {fn_name} {fn_args}")
            resp = requests.post(MCP_URL, json=payload, headers=headers, timeout=30)
            print(f"[✅ status] {resp.status_code}")
            print(f"[📦 body ] {resp.text}")
            resp.raise_for_status()

            tool_output = parse_mcp_response(resp)

            if fn_name == "get_projects":
                projects_cache = tool_output.get("projects")

            # GPT에 결과 전달
            messages += [
                {"role": "assistant", "content": None, "tool_calls": [call.model_dump()]},
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": fn_name,
                    "content": json.dumps(tool_output, ensure_ascii=False, separators=(",", ":"))
                }
            ]
        chat_kwargs["messages"] = messages


def parse_mcp_response(resp):
    """
    FastMCP SSE 또는 JSON 응답을 dict   ← (또는 list) 로 변환
    내부 text 블록도 자동으로 json.loads()
    """
    # 1) 스트림 / JSON 본문 가져오기 ──────
    if resp.headers.get("Content-Type", "").startswith("text/event-stream"):
        resp.encoding = "utf-8"
        data_lines = []
        for line in resp.iter_lines(decode_unicode=True):
            if line == "":                     # 이벤트 종료
                break
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        raw = "\n".join(data_lines)
        outer = json.loads(raw, strict=False)
    else:
        resp.encoding = "utf-8"
        outer = resp.json()

    # 2) FastMCP result.content[0].text 추출 ──────
    if isinstance(outer, dict) and "result" in outer:
        content = outer["result"].get("content", [])
        if content and isinstance(content[0], dict):
            text_block = content[0].get("text")
            if text_block:
                try:
                    return json.loads(text_block, strict=False)  # 실제 툴 반환값
                except json.JSONDecodeError:
                    pass  # text 가 단순 문자열이라면 그대로 둠
        # Fallback: result 자체 반환
        return outer["result"]

    return outer   # 이미 dict/list 형태


# ──────────────────── 4) Gradio UI ────────────────────
with gr.Blocks() as demo:
    gr.Markdown("## 🧠 GPT + Notion MCP 인터페이스")
    txt = gr.Textbox(label="메시지", placeholder="예: 프로젝트 목록 보여줘")
    out = gr.Textbox(label="응답", lines=12)
    txt.submit(chat_with_tool, inputs=txt, outputs=out)

if __name__ == "__main__":
    demo.launch()
