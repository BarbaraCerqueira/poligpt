import re
import json
import logging

import azure.functions as func
from azurefunctions.extensions.http.fastapi import Request, StreamingResponse, JSONResponse

from agent import create_poligpt_agent

# ====================== CONFIGURAÇÕES DO APP ======================

logging.captureWarnings(True)
logging.getLogger("azure").setLevel("WARNING")

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Limites das requisições, para conter o custo de cada chamada
MAX_QUERY_CHARS = 2000
MAX_HISTORY_MESSAGES = 20


# ========================= FUNÇÕES AUXILIARES =======================

def validate_request(req_body) -> str | None:
    """
    Valida o corpo da requisição e retorna a mensagem de erro, ou None se for válido.
    """
    if not isinstance(req_body, dict):
        return "O corpo da requisição deve ser um objeto JSON."

    query = req_body.get('query')
    if not isinstance(query, str) or not query.strip():
        return "O campo 'query' é obrigatório."
    if len(query) > MAX_QUERY_CHARS:
        return f"A pergunta deve ter no máximo {MAX_QUERY_CHARS} caracteres."

    chat_history = req_body.get('chat_history', [])
    if not isinstance(chat_history, list):
        return "O campo 'chat_history' deve ser uma lista."
    for msg in chat_history:
        if (not isinstance(msg, dict) or msg.get("role") not in ("user", "assistant")
                or not isinstance(msg.get("content"), str)):
            return "Cada mensagem do histórico deve ter 'role' (user ou assistant) e 'content'."

    if not isinstance(req_body.get('stream', True), bool):
        return "O campo 'stream' deve ser true ou false."

    return None

def error_response(message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)

def sse_event(data: dict) -> str:
    """
    Formata um evento no padrão Server-Sent Events.
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

def cited_sources(answer: str, sources: dict) -> list:
    """
    Retorna apenas as fontes citadas na resposta, como [1] ou [2][3], em ordem numérica.
    """
    cited = {int(number) for number in re.findall(r"\[(\d+)\]", answer)}
    return sorted((s for s in sources.values() if s["id"] in cited), key=lambda s: s["id"])

async def generate_answer(messages: list) -> dict:
    """
    Executa o agente e retorna a resposta completa, para chamadas sem stream.
    """
    sources = {}
    result = await create_poligpt_agent(sources).ainvoke({"messages": messages})
    answer = result["messages"][-1].text
    return {"answer": answer, "sources": cited_sources(answer, sources)}

async def stream_answer(messages: list):
    """
    Executa o agente e transmite a resposta em eventos SSE:
    - status: o agente vai buscar nos documentos (o texto recebido até aqui não era a resposta final e deve ser descartado);
    - token: trecho do texto da resposta, conforme é gerado;
    - sources: documentos citados na resposta (ao final);
    - done / error: fim da resposta.
    """
    sources = {}
    answer = ""
    try:
        agent = create_poligpt_agent(sources)
        async for chunk, metadata in agent.astream({"messages": messages}, stream_mode="messages"):
            if metadata.get("langgraph_node") != "model":
                continue
            if any(tool_call.get("name") for tool_call in getattr(chunk, "tool_call_chunks", [])):
                answer = ""
                yield sse_event({"type": "status", "status": "searching"})
            elif chunk.text:
                answer += chunk.text
                yield sse_event({"type": "token", "content": chunk.text})

        yield sse_event({"type": "sources", "sources": cited_sources(answer, sources)})
        yield sse_event({"type": "done"})
    except Exception:
        # O detalhe do erro vai só para o log (Application Insights), não para o cliente
        logging.exception("Erro ao gerar a resposta do chat")
        yield sse_event({"type": "error", "message": "Erro interno ao gerar a resposta."})


# ======================== DEFINIÇÃO DO FUNCTION APP =======================

@app.function_name(name="ChatCompletion")
@app.route(route="chatcompletion", methods=[func.HttpMethod.POST])
async def chat_completion(req: Request):
    try:
        req_body = await req.json()
    except ValueError:
        return error_response("O corpo da requisição deve ser um JSON válido.", 400)

    validation_error = validate_request(req_body)
    if validation_error:
        return error_response(validation_error, 400)

    # Histórico recente da conversa seguido da pergunta atual
    messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in req_body.get('chat_history', [])[-MAX_HISTORY_MESSAGES:]
    ]
    messages.append({"role": "user", "content": req_body['query']})

    # Por padrão a resposta vem em stream (SSE); com "stream": false, vem num único JSON
    if req_body.get('stream', True):
        return StreamingResponse(stream_answer(messages), media_type="text/event-stream")

    try:
        return JSONResponse(await generate_answer(messages))
    except Exception:
        logging.exception("Erro ao gerar a resposta do chat")
        return error_response("Erro interno ao gerar a resposta.", 500)
