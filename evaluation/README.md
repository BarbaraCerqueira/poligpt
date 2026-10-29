# Avaliação

Avaliação do PoliGPT em duas partes, que se complementam:

1. **Busca:** mede se a busca traz os documentos que respondem a cada pergunta (recall@k e MRR). É uma medida objetiva e reproduzível, usada para escolher a configuração da busca.
2. **Respostas:** mede a qualidade da resposta final que o usuário vê, com um LLM como juiz (correção e fidelidade às fontes), além de tempo e custo. Também compara modelos de linguagem para o chat.

As duas usam o mesmo conjunto de perguntas e o mesmo código do chat (`backend/agent.py`): o prompt, a ferramenta de busca e os parâmetros são os de produção.

## Estrutura

| Caminho                           | Conteúdo                                                                                       |
| --------------------------------- | ----------------------------------------------------------------------------------------------- |
| `generate_questions.py`         | Gera perguntas candidatas a partir de trechos sorteados do índice                              |
| `evaluate_retrieval.py`         | Avaliação da busca                                                                            |
| `evaluate_answers.py`           | Avaliação das respostas                                                                       |
| `data/perguntas_geradas.csv`    | Saída do gerador (antes da revisão)                                                           |
| `data/perguntas_revisadas.xlsx` | Revisão manual das perguntas geradas                                                           |
| `data/perguntas_avaliacao.xlsx` | Conjunto final de perguntas, usado nas duas avaliações                                        |
| `data/consultas_modelo.json`    | Consultas que o modelo do chat escreve para cada pergunta (fixadas para a avaliação da busca) |
| `results/busca_*`               | Resultados da avaliação da busca                                                              |
| `results/respostas_*`           | Resultados da avaliação das respostas                                                         |

Os resultados são salvos em CSV com separador `;`, para abrir direto no Excel em português. Cada execução gera dois arquivos, identificados pela data e hora: `_resumo` (métricas agregadas) e `_detalhes` (uma linha por pergunta).

## Conjunto de perguntas

### Geração e revisão

1. **Geração automática** (`generate_questions.py`): foram sorteados 80 documentos do índice, metade páginas e metade PDFs (semente fixa), e um trecho de cada um, com pelo menos 400 caracteres. Para cada trecho, um LLM (`gpt-6-sol`, diferente do modelo do chat para não favorecê-lo) escreveu uma pergunta como um aluno faria num chat e a resposta esperada, ou descartou o trecho por não ter informação útil (menus, atas, listas de nomes). O documento de origem é a fonte esperada. Saíram 70 perguntas.
2. **Revisão manual** (`perguntas_revisadas.xlsx`): cada pergunta foi marcada para manter ou descartar, com observações. Foram descartadas perguntas sobre conteúdo irrelevante ou desatualizado e perguntas que não fariam sentido para um aluno. Nas mantidas, a resposta esperada foi corrigida quando necessário. Quando outros documentos também respondiam à pergunta, eles foram acrescentados às fontes esperadas. Ficaram 44 perguntas geradas.
3. **Perguntas escritas à mão:** para cobrir casos que o sorteio não pegou, como dúvidas frequentes (inscrição em disciplinas, trancamento, estágio, TCC, jubilamento, atividades complementares) e siglas (coordenador de ENO, chefe do DCC).
4. **Perguntas sem resposta:** sobre a Poli e a UFRJ, mas sem resposta nos documentos do site, conferido no índice. Por exemplo, o cardápio do bandejão, a nota de corte do SISU, o CR do aluno e a grade horária do período (informação do SIGA). O esperado é que o chat diga que não encontrou, sem inventar, e indique onde procurar.
5. **Perguntas fora do escopo:** sem relação com a Poli, como um pedido de código, conhecimentos gerais, outra universidade e uma tentativa de mudar as instruções do chat. O esperado é que o chat recuse em uma frase, sem buscar nos documentos.

### Revisão das fontes esperadas

Na avaliação da busca, só os documentos listados como fonte contam como acerto. Por isso, depois de montado o conjunto, as fontes esperadas foram revistas: foram acrescentados documentos do índice que também respondiam à pergunta e retirados os que respondiam só em parte. Ficaram como fonte só os documentos que respondem integralmente à pergunta, sozinhos. Ao todo, 17 das 54 perguntas com fonte têm mais de uma fonte. A coluna `resolucao` registra o que mudou em cada pergunta.

### Conjunto final (`perguntas_avaliacao.xlsx`)

| Tipo               | Perguntas    | Avaliação da busca           | Avaliação das respostas |
| ------------------ | ------------ | ------------------------------ | ------------------------- |
| `gerada`         | 44           | Sim                            | Sim                       |
| `manual`         | 10           | Sim                            | Sim                       |
| `sem_resposta`   | 7            | Não (não há fonte esperada) | Sim                       |
| `fora_do_escopo` | 6            | Não                           | Sim                       |
| **Total**    | **67** | **54**                   | **67**              |

As colunas da planilha são `id`, `id_original` (id na revisão, para as geradas), `tipo`, `pergunta`, `resposta_esperada`, `urls_esperadas` (uma por linha), `observacao_revisao` e `resolucao` (como cada observação da revisão foi tratada). Nas perguntas `sem_resposta` e `fora_do_escopo`, a `resposta_esperada` descreve o comportamento esperado do chat.

## Avaliação da busca

### Como a busca funciona

O chat usa a busca híbrida do Azure AI Search. Cada consulta roda em paralelo de duas formas:

- **Busca por texto (BM25):** pontua os trechos pelas palavras da consulta, valorizando as mais raras. É boa para termos exatos, como siglas, nomes de sistemas e números de resolução.
- **Busca vetorial:** compara o embedding da consulta com o de cada trecho (`text-embedding-3-large`, 1024 dimensões) e traz os mais parecidos em significado. É boa para paráfrases.

As duas listas são combinadas por *Reciprocal Rank Fusion* (RRF). Cada trecho recebe `1/(60 + posição no texto) + peso × 1/(60 + posição no vetor)`, ou seja, conta só a posição em cada lista, e um trecho bem colocado nas duas sobe. A busca vetorial entra na fusão com seus 50 melhores candidatos (`VECTOR_CANDIDATES`), bem mais do que os trechos entregues ao modelo, para que a fusão tenha candidatos suficientes. Os k primeiros da lista final vão para o modelo.

### O que foi avaliado

Dois parâmetros da busca foram escolhidos por esta avaliação:

- **Peso da busca vetorial na fusão** (`VECTOR_WEIGHT`): quanto a posição na busca vetorial conta em relação à posição na busca por texto, cujo peso é sempre 1. Foram testados vários pesos, além da busca só por texto e só vetorial.
- **Quantidade de trechos entregues ao modelo** (k, `NUM_DOCS_TO_RETRIEVE`): mais trechos aumentam a chance de o documento certo chegar ao modelo, mas também o contexto de cada chamada, e com ele o custo, o tempo e o ruído na resposta. O corte não muda a ordem dos resultados, então uma única busca de 20 trechos permite medir todos os k até 20.

### Método

- **Consulta:** para cada pergunta, a busca usa a consulta que o modelo do chat escreve na sua primeira chamada à ferramenta, como acontece em produção. Em uma conversa, só o modelo consegue reescrever a pergunta com o contexto das mensagens anteriores, por isso a pergunta crua não foi usada. As consultas são geradas uma vez e guardadas em `data/consultas_modelo.json`, para que todas as configurações usem as mesmas.
- **Acerto:** a posição do primeiro trecho que vem de um dos documentos esperados; qualquer um deles conta. Se nenhum aparece entre os 20 primeiros, a pergunta conta como não encontrada.
- **Métricas:**
  - **recall@k:** porcentagem de perguntas com acerto entre os k primeiros trechos, medida para k = 1, 3, 5, 8, 10, 12 e 15.
  - **MRR (*Mean Reciprocal Rank*):** média de 1/posição do primeiro acerto, ou 0 sem acerto. Mede o quanto o documento certo aparece no topo.

### Resultados (`results/busca_20261028_2008_*`)

54 perguntas; cada uma vale 1,9 ponto percentual.

| Configuração              | R@1             | R@3             | R@5             | R@8             | R@10            | R@12            | R@15            | MRR             |
| --------------------------- | --------------- | --------------- | --------------- | --------------- | --------------- | --------------- | --------------- | --------------- |
| Só texto                   | **59,3%** | 75,9%           | **85,2%** | 85,2%           | 87,0%           | 88,9%           | 88,9%           | **0,701** |
| Peso do vetor 0,3           | 48,1%           | **77,8%** | **85,2%** | 87,0%           | 90,7%           | 90,7%           | **96,3%** | 0,651           |
| **Peso do vetor 0,5** | 50,0%           | **77,8%** | **85,2%** | **90,7%** | 90,7%           | **92,6%** | 94,4%           | 0,656           |
| Peso do vetor 0,8           | 48,1%           | 74,1%           | **85,2%** | 88,9%           | **92,6%** | **92,6%** | 94,4%           | 0,636           |
| Peso do vetor 1,0           | 51,9%           | 74,1%           | 83,3%           | 88,9%           | 90,7%           | **92,6%** | **96,3%** | 0,651           |
| Peso do vetor 1,5           | 51,9%           | 75,9%           | 81,5%           | 87,0%           | 88,9%           | **92,6%** | 94,4%           | 0,649           |
| Só vetor                   | 48,1%           | 64,8%           | 74,1%           | 77,8%           | 79,6%           | 83,3%           | 85,2%           | 0,584           |

- **A busca híbrida supera as isoladas a partir de 8 trechos.** Com k=8, ela acerta de 87,0% a 90,7%, contra 85,2% só com texto e 77,8% só com vetor.
- **O peso 0,5 ganha ou empata na maioria dos valores de k.** Em nenhum k ele fica mais de 1 pergunta atrás do melhor resultado, e tem o maior MRR entre os pesos.
- **A busca só por texto acerta mais no 1º lugar** (R@1 e MRR), mas perde em quase todos os outros casos. Isso importa pouco para o chat, porque o modelo lê todos os trechos que recebe.

### Configuração escolhida

- **Peso da busca vetorial: 0,5.** É o peso que ganha na maioria dos valores de k avaliados. Também tem o maior valor de MMR dentro da busca híbrida, o que demonstra a melhor capacidade de posicionar o trecho correto nos resultados. O peso não altera o custo da busca.
- **Trechos entregues ao modelo: 8.** Com o peso 0,5, a recall chega a 90,7% (49 das 54 perguntas) já com 7 trechos, e o ganho seguinte, de 1 pergunta, só vem com 12 trechos, quase 50% a mais de contexto. Cada trecho tem até 4.000 caracteres, cerca de 700 tokens a mais em cada chamada ao modelo, o que aumenta custo, tempo e texto irrelevante para o modelo ignorar.

## Avaliação das respostas

### Método

Cada pergunta é feita ao agente do chat numa conversa nova, com o mesmo prompt, a mesma ferramenta e a mesma busca de produção (peso 0,5 e 8 trechos, como escolhido na avaliação da busca; `reasoning_effort` baixo; até 3 buscas por pergunta), uma vez com cada modelo comparado. O agente roda localmente, no próprio script, a partir de `backend/agent.py`, e não pela Azure Function publicada. Um modelo juiz avalia cada resposta. A técnica, conhecida como LLM como juiz, é a mais usada para avaliar sistemas RAG, e os critérios seguem as métricas do [RAGAS](https://arxiv.org/abs/2309.15217):

- **Correção:** compara a resposta com a resposta esperada e a classifica como `correta` (traz a informação principal, sem erros), `parcial` (falta algo importante ou há um erro menor), `incorreta` ou `nao_respondeu` (disse que não encontrou). Nas perguntas `sem_resposta` e `fora_do_escopo`, "correta" significa que o chat se comportou como esperado.
- **Fidelidade:** verifica se tudo o que a resposta afirma está nos trechos que o agente recuperou, independentemente de estar certo. Uma resposta não fiel indica alucinação. Uma recusa, sem afirmações, é fiel.
- **Justificativa:** curta, para a análise dos erros.

Sem o juiz, o script também registra:

- as consultas feitas e o número de buscas;
- se a fonte esperada estava entre os documentos recuperados, considerando todas as buscas da resposta;
- o tempo até a resposta completa, com a média e o percentil 95 (o tempo que 95% das respostas não ultrapassam, que mostra os casos mais lentos sem depender de um único valor extremo);
- o custo do modelo do chat. A API da OpenAI informa, em cada chamada, os tokens de entrada (e quantos vieram do cache) e os de saída, incluindo os de raciocínio. O custo é a soma desses tokens multiplicados pelos preços de cada modelo, definidos no script. Os embeddings custam frações de centavo e ficam de fora.

**Modelos:**

- **Comparados:** `gpt-6-luna` e `gpt-6.1-terra`, as versões mais recentes das faixas econômica e intermediária da OpenAI.
- **Juiz:** `gpt-6-sol`, que não está entre os comparados, para não avaliar as próprias respostas. Ele roda no processamento Flex da OpenAI, que custa metade do preço em troca de respostas mais lentas. Isso não afeta as métricas, porque só o tempo do chat é medido.

### Resultados (`results/respostas_20261028_0152_*`)

| Métrica                                        | gpt-6-luna                                          | gpt-6.1-terra |
| ----------------------------------------------- | --------------------------------------------------- | ------------- |
| Respostas corretas (54 perguntas com resposta)  | 90,7% (49)                                          | 92,6% (50)    |
| Parciais / incorretas / não respondeu          | 4 / 1 / 0                                           | 4 / 0 / 0     |
| Fonte esperada recuperada                       | 94,4%                                               | 94,4%         |
| Comportamento correto em `sem_resposta` (7)   | 100%                                                | 100%          |
| Comportamento correto em `fora_do_escopo` (6) | 83,3% (5)                                           | 100%          |
| Respostas fiéis aos trechos (67)               | 91,0%                                               | 95,5%         |
| Buscas por pergunta (média)                    | 1,12                                                | 1,10          |
| Tempo médio / percentil 95                     | 4,9 s / 7,8 s                                       | 4,9 s / 7,5 s |
| Custo por pergunta                              | US$ 0,001                             | US$ 0,010 |               |

- **Os dois modelos acertam quase o mesmo:** 49 e 50 das 54 perguntas.
- **As respostas parciais** são, na maioria, respostas certas que omitem um detalhe da resposta esperada, como o formulário de um caso específico ou o sistema em que o pedido é feito.
- **Nos erros,** a busca não trouxe a fonte esperada em 2 dos 5 do `gpt-6-luna` e em 2 dos 4 do `gpt-6.1-terra`; nos outros, o modelo tinha a fonte e deixou algo de fora.
- **O `gpt-6.1-terra` vai um pouco melhor em fidelidade e na recusa de perguntas fora do escopo.** O `gpt-6-luna` buscou nos documentos antes de recusar uma pergunta sobre a USP e teve um erro de conteúdo: afirmou que ser refugiado não garante isenção da taxa de revalidação de diploma.
- **As diferenças são de 1 a 3 perguntas, dentro da variação esperada,** enquanto o custo do `gpt-6.1-terra` é 10 vezes maior, sem diferença de tempo. Por isso o chat **mantém o `gpt-6-luna`**.
- **O juiz é rigoroso demais na fidelidade:** parte das respostas marcadas como não fiéis só cita o endereço do SIGA (`siga.ufrj.br`), que vem das instruções do chat e não dos trechos, ou faz observações genéricas, como dizer que a nota de corte varia por ano.

## Como executar

Pré-requisitos:

- **Ambiente:** Python 3.11 com as dependências do backend e o `openpyxl` (`pip install -r requirements.txt`).
- **Variáveis de ambiente** do backend: `OPENAI_API_KEY`, `AZURE_SEARCH_ENDPOINT` e `AZURE_SEARCH_QUERY_KEY`. Elas podem ser lidas do Key Vault:

```bash
export AZURE_SEARCH_ENDPOINT=https://srch-poligpt-dev.search.windows.net
export AZURE_SEARCH_QUERY_KEY=$(az search query-key list --service-name srch-poligpt-dev -g rg-poligpt-dev-eastus2 --query "[0].key" -o tsv)
export OPENAI_API_KEY=$(az keyvault secret show --vault-name kv-poligpt-dev-eastus2 -n openai-api-key --query value -o tsv)

cd evaluation
python generate_questions.py [quantidade de documentos]   # só para gerar um novo conjunto (padrão: 80)
python evaluate_retrieval.py
python evaluate_answers.py
```

| Script                    | Tempo   | Custo aproximado                                               |
| ------------------------- | ------- | -------------------------------------------------------------- |
| `generate_questions.py` | ~5 min  | centavos                                                       |
| `evaluate_retrieval.py` | ~1 min  | centavos (embeddings e, se faltarem, as consultas do modelo)   |
| `evaluate_answers.py`   | ~15 min | ~US$ 2 (US$ 0,75 nos modelos comparados e ~US$ 1,40 no juiz) |

As configurações ficam no topo de cada script: `CONFIGS` na busca, e `MODELS` (com os preços), `JUDGE_MODEL` e `JUDGE_PROMPT` nas respostas. Depois de mudar o prompt ou o modelo do chat, apague `data/consultas_modelo.json` para que a avaliação da busca use as novas consultas.

## Limitações

- **Tamanho do conjunto:** com 54 perguntas, cada uma vale 1,9 ponto percentual. Diferenças de 1 ou 2 perguntas não são significativas.
- **Variação entre execuções:** os modelos de linguagem não são determinísticos, e a busca vetorial pode variar levemente. Na busca, duas execuções seguidas diferiram em 1 pergunta. A avaliação das respostas foi executada uma vez.
- **Fontes esperadas:** a busca conta como acerto só os documentos listados em `urls_esperadas`, que respondem integralmente à pergunta. Documentos que respondem em parte não contam, mesmo quando o modelo consegue montar a resposta juntando vários deles, por isso a recall é uma medida conservadora. Na avaliação das respostas isso não acontece, porque o juiz olha o conteúdo.
- **Juiz automático:** as notas dependem do modelo e do prompt do juiz. Os vereditos podem ser conferidos pelas justificativas no arquivo de detalhes, mas não houve uma medida formal de concordância com avaliação humana.
- **Perguntas isoladas:** cada pergunta é feita numa conversa nova. Perguntas que dependem de mensagens anteriores não foram avaliadas.
- **Tempo medido fora da Function:** o tempo de resposta é o do agente rodando localmente. Ele não inclui a inicialização da Azure Function (*cold start*, quando ela fica um tempo sem uso) nem a latência de rede entre o site e a Function.
