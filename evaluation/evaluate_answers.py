"""
Avalia as respostas do PoliGPT de ponta a ponta com o conjunto de perguntas revisado (data/perguntas_avaliacao.xlsx).

Cada pergunta é feita ao agente do chatbot (mesmo prompt, ferramenta e busca de produção), numa conversa nova, com cada
modelo de MODELS. Um modelo juiz, que não está entre os comparados, avalia cada resposta (LLM como juiz):
- correção: se a resposta bate com a resposta esperada (correta, parcial, incorreta ou não respondeu). Nas perguntas
  sem_resposta e fora_do_escopo, a resposta esperada descreve o comportamento correto (avisar que não encontrou, recusar);
- fidelidade: se tudo o que a resposta afirma está nos trechos que o agente recuperou (o contrário é alucinação).
Também são registrados as buscas feitas, se a fonte esperada foi recuperada, o tempo e o custo de cada resposta.

Uso: python evaluate_answers.py
Variáveis de ambiente: as mesmas do backend (OPENAI_API_KEY, AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_QUERY_KEY).
"""
import os
import sys
import csv
import time
import statistics
from typing import Literal
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
from agent import create_poligpt_agent, OPENAI_API_KEY, REASONING_EFFORT, OPENAI_TIMEOUT_SECONDS
from evaluate_retrieval import load_questions, normalize_url, RESULTS_DIR

# ====================== CONFIGURAÇÕES ======================

# Modelos comparados e preços em US$ por 1 milhão de tokens (entrada, entrada em cache, saída), conforme a página de
# preços da OpenAI em 28/10/2026. O custo considera só o modelo: os embeddings das buscas custam frações de centavo.
MODELS = {
    "gpt-6-luna": (0.10, 0.01, 0.50),
    "gpt-6.1-terra": (1.00, 0.05, 5.00),
}
JUDGE_MODEL = "gpt-6-sol"  # fora da comparação, para não avaliar as próprias respostas (é o mesmo que gerou as perguntas)
# O juiz usa o processamento Flex da OpenAI: metade do preço em troca de respostas mais lentas, o que não importa para
# ele (o tempo medido é só o do chatbot). Por ser mais lento, tem um tempo máximo maior.
JUDGE_SERVICE_TIER = "flex"
JUDGE_TIMEOUT_SECONDS = 600
MAX_WORKERS = 4  # perguntas respondidas em paralelo

ANSWERABLE_TYPES = ["gerada", "manual"]

JUDGE_PROMPT = """Você avalia as respostas do PoliGPT, chatbot que responde dúvidas sobre a Escola Politécnica da UFRJ \
(Poli) com base em trechos de documentos do site da Poli, recuperados por uma ferramenta de busca.

Avalie a resposta do chatbot em dois critérios:

1. Correção, comparando com a resposta esperada:
- correta: traz a informação principal da resposta esperada, sem erros. Detalhes a mais ou a menos não importam;
- parcial: acerta parte da informação principal, mas falta algo importante ou há um erro menor;
- incorreta: a informação principal está errada ou contradiz a resposta esperada;
- nao_respondeu: o chatbot disse que não encontrou a informação ou não respondeu ao que foi perguntado.
Nas perguntas do tipo sem_resposta e fora_do_escopo, a resposta esperada descreve o comportamento correto: classifique \
como correta se o chatbot agiu assim, e como incorreta se respondeu ao conteúdo ou inventou informação.

2. Fidelidade: se tudo o que a resposta afirma está apoiado nos trechos recuperados, independentemente de estar certo \
ou não. Orientações gerais, como procurar a secretaria do curso ou o SIGA, não contam. Uma resposta sem afirmações \
(por exemplo, uma recusa) é fiel.

Tipo da pergunta: {type}
Pergunta: {question}
Resposta esperada: {expected_answer}

Trechos recuperados pelo chatbot:
{passages}

Resposta do chatbot:
{answer}"""


class Judgement(BaseModel):
    justification: str = Field(description="Justificativa curta das duas avaliações: o que faltou, o que está errado ou o que não está nos trechos")
    correctness: Literal["correta", "parcial", "incorreta", "nao_respondeu"] = Field(description="Correção da resposta em relação à resposta esperada")
    faithful: bool = Field(description="Se tudo o que a resposta afirma está apoiado nos trechos recuperados")


# ========================= AVALIAÇÃO =======================

def cost(usage: list, prices: tuple) -> float:
    """
    Custo em US$ das chamadas ao modelo, a partir do uso de tokens de cada uma (os tokens de raciocínio são de saída).
    """
    input_price, cached_price, output_price = prices
    total = 0
    for u in usage:
        cached = u.get("input_token_details", {}).get("cache_read", 0)
        total += (u["input_tokens"] - cached) * input_price + cached * cached_price + u["output_tokens"] * output_price
    return total / 1_000_000


def evaluate(question: dict, model_name: str, model: ChatOpenAI, judge) -> dict:
    """
    Faz a pergunta ao agente com o modelo dado e avalia a resposta com o juiz.
    """
    row = {"modelo": model_name, "id": question["id"], "tipo": question["tipo"], "pergunta": question["pergunta"],
           "resposta_esperada": question["resposta_esperada"]}
    try:
        sources = {}
        start = time.time()
        result = create_poligpt_agent(sources, model).invoke({"messages": [("user", question["pergunta"])]})
        seconds = time.time() - start

        messages = result["messages"]
        ai_messages = [m for m in messages if m.type == "ai"]
        answer = messages[-1].text
        passages = "\n\n---\n\n".join(m.text for m in messages if m.type == "tool") or "Nenhuma busca feita."
        urls = {normalize_url(s["url"]) for s in sources.values() if s["url"]}

        judgement = judge.invoke(JUDGE_PROMPT.format(type=question["tipo"], question=question["pergunta"],
                                                     expected_answer=question["resposta_esperada"], passages=passages, answer=answer))
    except Exception as error:
        print(f"[{model_name}] {question['id']}: erro - {error}")
        return {**row, "erro": str(error)}

    print(f"[{model_name}] {question['id']}: {judgement.correctness}, {'fiel' if judgement.faithful else 'não fiel'}")
    return {
        **row,
        "resposta": answer,
        "correcao": judgement.correctness,
        "fiel": "sim" if judgement.faithful else "não",
        "justificativa": judgement.justification,
        "consultas": "\n".join(call["args"].get("consulta", "") for m in ai_messages for call in m.tool_calls),
        "buscas": sum(len(m.tool_calls) for m in ai_messages),
        "fonte_encontrada": ("sim" if question["urls"] & urls else "não") if question["urls"] else "",
        "fontes": "\n".join(sorted(urls)),
        "tempo_s": round(seconds, 1),
        "custo_usd": round(cost([m.usage_metadata for m in ai_messages if m.usage_metadata], MODELS[model_name]), 5),
        "erro": "",
    }


def share(rows: list, condition) -> float | str:
    return round(sum(1 for r in rows if condition(r)) / len(rows), 3) if rows else ""


def summarize(model_name: str, rows: list) -> dict:
    ok = [r for r in rows if not r["erro"]]
    answerable = [r for r in ok if r["tipo"] in ANSWERABLE_TYPES]
    no_answer = [r for r in ok if r["tipo"] == "sem_resposta"]
    out_of_scope = [r for r in ok if r["tipo"] == "fora_do_escopo"]
    times = [r["tempo_s"] for r in ok]
    return {
        "modelo": model_name,
        "perguntas": len(rows),
        "erros": len(rows) - len(ok),
        # Perguntas com resposta nos documentos
        "corretas": share(answerable, lambda r: r["correcao"] == "correta"),
        "parciais": share(answerable, lambda r: r["correcao"] == "parcial"),
        "incorretas": share(answerable, lambda r: r["correcao"] == "incorreta"),
        "nao_respondeu": share(answerable, lambda r: r["correcao"] == "nao_respondeu"),
        "fonte_encontrada": share([r for r in answerable if r["fonte_encontrada"]], lambda r: r["fonte_encontrada"] == "sim"),
        # Perguntas sem resposta nos documentos e fora do escopo: comportamento esperado
        "sem_resposta_corretas": share(no_answer, lambda r: r["correcao"] == "correta"),
        "fora_do_escopo_corretas": share(out_of_scope, lambda r: r["correcao"] == "correta"),
        "fora_do_escopo_sem_busca": share(out_of_scope, lambda r: r["buscas"] == 0),
        # Todas as perguntas
        "fieis": share(ok, lambda r: r["fiel"] == "sim"),
        "buscas_media": round(statistics.mean(r["buscas"] for r in ok), 2) if ok else "",
        "tempo_medio_s": round(statistics.mean(times), 1) if ok else "",
        "tempo_p95_s": round(statistics.quantiles(times, n=20)[-1], 1) if len(times) > 1 else "",
        "custo_medio_usd": round(statistics.mean(r["custo_usd"] for r in ok), 5) if ok else "",
        "custo_total_usd": round(sum(r["custo_usd"] for r in ok), 3),
    }


def main():
    questions = load_questions()
    judge = ChatOpenAI(model=JUDGE_MODEL, api_key=OPENAI_API_KEY, service_tier=JUDGE_SERVICE_TIER,
                       timeout=JUDGE_TIMEOUT_SECONDS).with_structured_output(Judgement)

    details, summaries = [], []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for model_name in MODELS:
            # Sem streaming, ao contrário do chatbot: o tempo medido é o da resposta completa nos dois casos, e assim o
            # uso de tokens vem em todas as mensagens
            model = ChatOpenAI(model=model_name, api_key=OPENAI_API_KEY, reasoning_effort=REASONING_EFFORT, timeout=OPENAI_TIMEOUT_SECONDS)
            rows = list(executor.map(lambda question: evaluate(question, model_name, model, judge), questions))
            details += rows
            summaries.append(summarize(model_name, rows))

    print(f"\n{'':<26}" + "".join(f"{s['modelo']:>16}" for s in summaries))
    for name in list(summaries[0])[1:]:
        print(f"{name:<26}" + "".join(f"{str(s[name]):>16}" for s in summaries))

    # Separador ";" e BOM para o Excel em português abrir direto, como na geração das perguntas
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    for name, rows in [("resumo", summaries), ("detalhes", details)]:
        path = os.path.join(RESULTS_DIR, f"respostas_{timestamp}_{name}.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            # A primeira linha sem erro tem todas as colunas; nas linhas com erro, as que faltam ficam vazias
            fieldnames = next((r for r in rows if not r.get("erro")), rows[0]).keys()
            writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print(f"Salvo em {path}")


if __name__ == "__main__":
    main()
