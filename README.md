# GPT MCP Toolcaller Gradio

이 프로젝트는 OpenAI GPT 모델과 FastMCP를 활용하여 Notion 데이터를 조회하고 분석하는 예제입니다. Gradio UI를 통해 사용자의 질문을 입력하면 GPT가 자동으로 MCP 도구를 호출하여 결과를 반환합니다.

## 구성
- **`notion_mcp_server.py`**: Notion API를 사용하여 여러 MCP 도구(데이터베이스 검색, 프로젝트 조회, 스키마 조회 등)를 제공하는 FastMCP 서버입니다.
- **`gpt_mcp_toolcaller_gradio.py`**: Gradio 인터페이스와 GPT 호출 로직을 포함합니다. 사용자의 입력에 따라 필요한 MCP 도구를 호출해 응답을 생성합니다.

## 요구 사항
- Python 3.10 이상
- OpenAI API 키(`OPENAI_API_KEY`)
- Notion 통합 토큰(`NOTION_TOKEN`)

## 설치
```bash
# 의존성 설치
pip install -e .
```

## 사용 방법
1. 먼저 Notion MCP 서버를 실행합니다.
   ```bash
   python notion_mcp_server.py
   ```
2. 다른 터미널에서 Gradio 인터페이스를 실행합니다.
   ```bash
   python gpt_mcp_toolcaller_gradio.py
   ```
3. 브라우저에서 표시되는 URL을 열어 대화를 시작합니다.

프로젝트 설정 및 세부 사항은 `pyproject.toml`을 참고하세요.
