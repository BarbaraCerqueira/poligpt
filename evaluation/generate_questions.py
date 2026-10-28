"""
Gera o conjunto de perguntas de teste a partir do índice de busca, para revisão manual.

Sorteia documentos do índice (metade páginas, metade PDFs) e, para um trecho de cada um, pede a um LLM uma pergunta
que um aluno faria e a resposta esperada. O documento sorteado é o gabarito da busca (recall@k).
O resultado vai para uma planilha (CSV) que é revisada à mão antes de ser usada na avaliação: a revisão está em
data/perguntas_revisadas.xlsx e o conjunto final, em data/perguntas_avaliacao.xlsx.

Uso: python generate_questions.py [quantidade de documentos]
Variáveis de ambiente: as mesmas do backend (OPENAI_API_KEY, AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_QUERY_KEY).
"""
import os
import sys
import csv
import random

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
from agent import search_client, OPENAI_API_KEY

# ====================== CONFIGURAÇÕES ======================

NUM_DOCUMENTS = int(sys.argv[1]) if len(sys.argv) > 1 else 80
GENERATOR_MODEL = "gpt-6-sol"  # modelo diferente do usado pelo chatbot, para não favorecê-lo
MIN_CHUNK_CHARS = 400  # trechos menores costumam ser só menus, listas de links ou nomes
RANDOM_SEED = 42
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "data", "perguntas_geradas.csv")

PROMPT = """Você está montando um conjunto de testes para o PoliGPT, chatbot que responde dúvidas de alunos, \
professores e candidatos da Escola Politécnica da UFRJ com base nos documentos do site da Poli.

A partir do trecho abaixo, escreva UMA pergunta que alguém da comunidade da Poli faria de verdade e que o trecho \
responde, junto com a resposta esperada.
- Escreva a pergunta como um aluno escreveria num chat: linguagem natural, sem copiar as expressões do trecho e sem \
citar o documento ("segundo o manual...").
- A pergunta deve fazer sentido sozinha, sem o trecho ao lado.
- A resposta esperada deve ser curta (1 a 3 frases) e conter só o que está no trecho.
- Se o trecho não tiver informação útil para essas pessoas (menus, listas de nomes, atas, notícias sem utilidade \
prática, texto ilegível), marque como não útil.

Documento: {title}
Data: {last_modified}
Trecho:
{chunk}"""


class GeneratedQuestion(BaseModel):
    useful: bool = Field(description="Se o trecho tem informação útil para gerar uma pergunta")
    question: str = Field(description="Pergunta, ou vazio se o trecho não for útil")
    expected_answer: str = Field(description="Resposta esperada, ou vazio se o trecho não for útil")


# ========================= GERAÇÃO =======================

def sample_chunks() -> list:
    """
    Sorteia um trecho de cada documento, com metade dos documentos sendo páginas e metade PDFs.
    """
    # A ordenação é necessária para paginar o índice inteiro: sem ela, a busca repete e pula trechos
    chunks = list(search_client.search(search_text="*", select=["parent_id", "url", "title", "last_modified", "chunk"], order_by=["chunk_id"], top=100000))
    chunks = [c for c in chunks if len(c["chunk"]) >= MIN_CHUNK_CHARS]

    documents = {}
    for chunk in chunks:
        documents.setdefault(chunk["parent_id"], []).append(chunk)

    rng = random.Random(RANDOM_SEED)
    pdfs = [d for d in documents.values() if d[0]["url"].lower().endswith(".pdf")]
    pages = [d for d in documents.values() if not d[0]["url"].lower().endswith(".pdf")]
    selected = rng.sample(pages, NUM_DOCUMENTS // 2) + rng.sample(pdfs, NUM_DOCUMENTS - NUM_DOCUMENTS // 2)
    return [rng.choice(document) for document in selected]


def main():
    llm = ChatOpenAI(model=GENERATOR_MODEL, api_key=OPENAI_API_KEY).with_structured_output(GeneratedQuestion)

    rows = []
    for i, chunk in enumerate(sample_chunks(), start=1):
        result = llm.invoke(PROMPT.format(title=chunk["title"] or chunk["url"], last_modified=chunk["last_modified"], chunk=chunk["chunk"]))
        print(f"[{i}/{NUM_DOCUMENTS}] {'ok' if result.useful else 'descartado'}: {result.question or chunk['url']}")
        if result.useful:
            rows.append({
                "id": len(rows) + 1,
                "tipo": "gerada",
                "pergunta": result.question,
                "resposta_esperada": result.expected_answer,
                "url_esperada": chunk["url"],
                "manter": "",
                "observacao": "",
                "trecho_origem": chunk["chunk"],
            })

    # Separador ";" e BOM para o Excel em português abrir a planilha direto, com acentos
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys(), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} perguntas salvas em {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
