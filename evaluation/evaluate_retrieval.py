"""
Avalia a busca do PoliGPT com o conjunto de perguntas revisado (data/perguntas_avaliacao.xlsx).

Para cada pergunta com fonte esperada, faz a busca com a consulta que o modelo do chatbot escreve na primeira busca, como
acontece em produção, variando o peso da busca vetorial na busca híbrida (as configurações de CONFIGS). Registra a
posição do primeiro trecho que vem de um dos documentos esperados (qualquer um deles conta como acerto). Métricas:
- recall@k: porcentagem de perguntas com acerto entre os k primeiros trechos (o chatbot recebe 8);
- MRR: média de 1/posição do primeiro acerto (0 quando não há acerto entre os MAX_RANK primeiros).

As consultas do modelo são geradas uma vez e salvas em results/consultas_modelo.json, para que as execuções usem as
mesmas e possam ser comparadas. Apague o arquivo para gerar de novo (por exemplo, depois de mudar o prompt ou o modelo).

Uso: python evaluate_retrieval.py
Variáveis de ambiente: as mesmas do backend (OPENAI_API_KEY, AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_QUERY_KEY).
"""
import os
import re
import sys
import csv
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import openpyxl
from azure.search.documents.models import VectorizedQuery

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
from agent import search_client, embeddings, llm, create_search_tool, SYSTEM_PROMPT, MAX_SEARCHES, VECTOR_CANDIDATES

# ====================== CONFIGURAÇÕES ======================

QUESTIONS_FILE = os.path.join(os.path.dirname(__file__), "data", "perguntas_avaliacao.xlsx")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
MODEL_QUERIES_FILE = os.path.join(RESULTS_DIR, "consultas_modelo.json")

MAX_RANK = 20  # trechos buscados por consulta; posições além disso contam como não encontrado
RECALL_AT = [1, 3, 5, 8, 10, 15, 20]

# Peso da busca vetorial na fusão com a busca por texto (BM25), cujo peso é sempre 1; None = sem busca vetorial e
# text False = sem busca por texto. Todas usam os mesmos candidatos vetoriais do chatbot (VECTOR_CANDIDATES); o peso
# do chatbot é VECTOR_WEIGHT.
CONFIGS = [
    {"name": "so_texto", "vector_weight": None},
    {"name": "peso_vetor_0.3", "vector_weight": 0.3},
    {"name": "peso_vetor_0.5", "vector_weight": 0.5},
    {"name": "peso_vetor_0.8", "vector_weight": 0.8},
    {"name": "peso_vetor_1.0", "vector_weight": 1.0},
    {"name": "peso_vetor_1.5", "vector_weight": 1.5},
    {"name": "so_vetor", "vector_weight": 1.0, "text": False},
]


# ========================= AVALIAÇÃO =======================

def normalize_url(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url.strip().lower()).rstrip("/")


def load_questions() -> list:
    """
    Lê as perguntas da planilha, com as fontes esperadas normalizadas em `urls` (vazio quando não há fonte).
    """
    sheet = openpyxl.load_workbook(QUESTIONS_FILE)["perguntas"]
    header = [cell.value for cell in sheet[1]]
    rows = [dict(zip(header, row)) for row in sheet.iter_rows(min_row=2, values_only=True)]
    for row in rows:
        row["urls"] = {normalize_url(url) for url in (row["urls_esperadas"] or "").split("\n") if url.strip()}
    return rows


def load_model_queries(questions: list) -> dict:
    """
    Retorna a consulta que o modelo do chatbot escreve na primeira busca de cada pergunta (texto da pergunta -> consulta),
    gerando as que ainda não estão salvas. Se o modelo decidir não buscar, a consulta fica vazia e conta como erro.
    """
    queries = {}
    if os.path.exists(MODEL_QUERIES_FILE):
        with open(MODEL_QUERIES_FILE, encoding="utf-8") as file:
            queries = json.load(file)

    model = llm.bind_tools([create_search_tool({})])
    system_prompt = SYSTEM_PROMPT.format(today=datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y"), max_searches=MAX_SEARCHES)
    for question in [q["pergunta"] for q in questions if q["pergunta"] not in queries]:
        message = model.invoke([("system", system_prompt), ("user", question)])
        queries[question] = message.tool_calls[0]["args"]["consulta"] if message.tool_calls else ""
        print(f"Consulta do modelo: {question} -> {queries[question]}")

    # Mantém só as perguntas atuais, descartando as que saíram da planilha
    queries = {q["pergunta"]: queries[q["pergunta"]] for q in questions}
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(MODEL_QUERIES_FILE, "w", encoding="utf-8") as file:
        json.dump(queries, file, ensure_ascii=False, indent=2)
    return queries


def search(query: str, vector: list, config: dict) -> list:
    """
    Busca com a configuração dada e retorna as URLs normalizadas dos trechos, na ordem dos resultados.
    """
    kwargs = {"select": ["url"], "top": MAX_RANK}
    if config["vector_weight"] is not None:
        kwargs["vector_queries"] = [VectorizedQuery(vector=vector, k_nearest_neighbors=VECTOR_CANDIDATES, fields="vector", weight=config["vector_weight"])]
    search_text = query if config.get("text", True) else None
    return [normalize_url(result["url"]) for result in search_client.search(search_text=search_text, **kwargs)]


def first_hit(urls: list, expected: set):
    return next((position for position, url in enumerate(urls, start=1) if url in expected), None)


def summarize(positions: list) -> dict:
    summary = {f"recall@{k}": sum(1 for p in positions if p and p <= k) / len(positions) for k in RECALL_AT}
    summary["mrr"] = sum(1 / p for p in positions if p) / len(positions)
    return summary


def main():
    questions = [q for q in load_questions() if q["urls"]]
    model_queries = load_model_queries(questions)

    # Um embedding por consulta, reaproveitado em todas as configurações
    vectors = {query: embeddings.embed_query(query) for query in set(model_queries.values()) - {""}}

    details, summaries = [], []
    for config in CONFIGS:
        positions = []
        for question in questions:
            query = model_queries[question["pergunta"]]
            position = first_hit(search(query, vectors[query], config), question["urls"]) if query else None
            positions.append(position)
            details.append({"config": config["name"], "id": question["id"], "tipo": question["tipo"],
                            "pergunta": question["pergunta"], "consulta": query, "posicao": position or ""})
        summaries.append({"config": config["name"], "perguntas": len(questions),
                          **{name: round(value, 3) for name, value in summarize(positions).items()}})

    print(f"\n{'config':<16}" + "".join(f"{name:>11}" for name in list(summaries[0])[2:]))
    for summary in summaries:
        print(f"{summary['config']:<16}" + "".join(f"{value:>11.3f}" for value in list(summary.values())[2:]))

    # Separador ";" e BOM para o Excel em português abrir direto, como na geração das perguntas
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    for name, rows in [("resumo", summaries), ("detalhes", details)]:
        path = os.path.join(RESULTS_DIR, f"busca_{timestamp}_{name}.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=rows[0].keys(), delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print(f"Salvo em {path}")


if __name__ == "__main__":
    main()
