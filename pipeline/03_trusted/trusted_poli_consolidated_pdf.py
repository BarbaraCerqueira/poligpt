# Databricks notebook source
# MAGIC %md
# MAGIC # Transformação e Agregação de Dados
# MAGIC Neste Notebook é feita a extração dos dados brutos da camada Raw, seguida da agregação, limpeza e estruturação dos mesmos em uma tabela única. Essa tabela terá como granularidade uma URL (seja de páginas qualquer do site da Politécnica ou de um arquivo PDF), ou seja, cada linha contém o conteúdo de um único arquivo coletado da camada anterior, juntamente com os metadados relevantes para o projeto.  

# COMMAND ----------

import os
import re
import sys
import time
import fitz  # PyMuPDF
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

from multiprocessing import Pool

etl_folder_path = './../../pipeline/'
sys.path.append(etl_folder_path)

from delta.tables import DeltaTable
from pyspark.sql import Row
from pyspark.sql.window import Window
from pyspark.sql.types import StringType, DoubleType
from pyspark.sql.functions import col, lit, when, length, udf, to_timestamp, regexp_replace, trim, unix_timestamp, current_timestamp, row_number
from utils import list_all_files, upsert_to_delta_lake, save_checkpoint, get_checkpoint_by_source

# COMMAND ----------

# MAGIC %md
# MAGIC ## Definição de Parâmetros

# COMMAND ----------

input_base_path = "/mnt/adlsraw/pdf/"
output_path = "/mnt/adlstrusted/poli_consolidated_pdf/"
checkpoint_path = "/mnt/adlstrusted/checkpoints/poli_consolidated_pdf/"
ingestion_control_path = "/mnt/adlscontrol/ingestion_logs/"
num_processes = 4
max_tasks_per_process = 20           # recria cada processo após N PDFs, devolvendo a memória acumulada pelo MuPDF/Tesseract

# OCR (Tesseract, via PyMuPDF) para páginas sem texto extraível. Uma página passa por OCR quando:
#   1. o texto existente é ilegível (fontes sem mapeamento Unicode viram o caractere U+FFFD); ou
#   2. não tem camada de texto (menos de `ocr_min_chars_per_page` caracteres) e contém imagens ou muitos desenhos
#      vetoriais (texto convertido em curvas, comum em páginas impressas pelo navegador); ou
#   3. é dominada por imagem (digitalização), mesmo com algum texto digital por cima (carimbo, cabeçalho).
# Imagens dentro de páginas digitais comuns (logos, fotos, gráficos) não passam por OCR.
ocr_language = "por"
ocr_dpi = 300                        # resolução recomendada para o Tesseract
ocr_max_megapixels = 25              # limite de tamanho da imagem renderizada para o OCR (A4 a 300 dpi ≈ 8,7 MP)
ocr_min_chars_per_page = 50          # abaixo disso, a página é considerada sem camada de texto
ocr_min_image_coverage = 0.1         # ignora páginas sem texto que só têm imagens pequenas (ex.: logo)
ocr_min_vector_drawings = 200        # desenhos vetoriais que indicam texto em curvas (bordas e enfeites ficam bem abaixo disso)
ocr_scanned_image_coverage = 0.8     # fração da página coberta por imagem para considerá-la digitalizada
ocr_scanned_max_chars = 300          # máximo de texto digital presente em página com imagem para permitir OCR
ocr_max_illegible_ratio = 0.1        # fração de caracteres ilegíveis (U+FFFD) que indica texto corrompido

# COMMAND ----------

# Widgets para receber os inputs do Workflow
# input_base_path = dbutils.widgets.get("input_base_path")
# output_path = dbutils.widgets.get("output_path")
# checkpoint_path = dbutils.widgets.get("checkpoint_path")
# num_processes = dbutils.widgets.get("num_processes")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Funções

# COMMAND ----------

# Função para medir a fração da página coberta por imagens
def image_coverage(page):
    page_area = abs(page.rect)
    if page_area == 0:
        return 0.0
    covered = sum(abs(fitz.Rect(img["bbox"]) & page.rect) for img in page.get_image_info())
    return min(covered / page_area, 1.0)

# Função para decidir se uma página precisa de OCR (critérios descritos nos parâmetros)
def page_needs_ocr(page, text):
    chars = len(text.strip())
    if chars and text.count("�") / chars > ocr_max_illegible_ratio:
        return True
    coverage = image_coverage(page)
    if chars < ocr_min_chars_per_page:
        return coverage >= ocr_min_image_coverage or len(page.get_drawings()) >= ocr_min_vector_drawings
    return coverage >= ocr_scanned_image_coverage and chars <= ocr_scanned_max_chars

# Função executada ao iniciar cada processo de OCR, que descarta o stderr nativo do processo. O Tesseract e o Leptonica
# escrevem nele avisos ("Image too small to scale", "Line cannot be recognized") sobre fragmentos estreitos demais
# para reconhecer, como bordas de tabela e traços, que são ignorados sem afetar o texto extraído. Em PDFs com
# tabelas, são milhares de linhas, e a saída de uma célula de job tem limite de tamanho (8 MB).
def silence_native_stderr():
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 2)
    os.close(devnull)

# Função para calcular a resolução do OCR de uma página. Páginas cuja imagem a `ocr_dpi` passaria de
# `ocr_max_megapixels` têm a resolução reduzida até esse limite, já que a memória usada pelo Tesseract cresce com
# o número de pixels. Isso acontece em digitalizações cujo PDF declara um tamanho de página muito maior que o real.
def ocr_dpi_for_page(page):
    megapixels = abs(page.rect) / 72**2 * ocr_dpi**2 / 1e6  # área em pontos (1/72 pol.) -> pixels na resolução desejada
    if megapixels <= ocr_max_megapixels:
        return ocr_dpi
    return int(ocr_dpi * (ocr_max_megapixels / megapixels) ** 0.5)  # os pixels crescem com o quadrado da resolução

# Função para extrair o texto de uma página, aplicando OCR quando necessário
def extract_page_text(page):
    text = page.get_text("text")
    if not page_needs_ocr(page, text):
        return text, False
    try:
        textpage = page.get_textpage_ocr(language=ocr_language, dpi=ocr_dpi_for_page(page), full=True)
        return page.get_text("text", textpage=textpage), True
    except Exception as e:
        print(f"Erro no OCR da página {page.number}: {e}")
        return text, False

# Função para extrair o conteúdo textual e metadados de um PDF localizado no ADLS
def extract_data_from_pdf(pdf_path):
    try:
        with fitz.open(f"/dbfs{pdf_path}") as pdf:
            metadata = pdf.metadata if pdf is not None else {}
            text = ""
            ocr_pages = 0
            for page in pdf:
                page_text, used_ocr = extract_page_text(page)
                text += page_text
                ocr_pages += used_ocr
        return text, metadata, ocr_pages
    except Exception as e:
        print(f"Erro ao processar {pdf_path}: {e}")
        return '', {}, 0

# Função para gerar o Row com o conteúdo do PDF
def process_pdf(pdf_path):
    pdf_text, pdf_metadata, ocr_pages = extract_data_from_pdf(pdf_path)

    if not isinstance(pdf_metadata, dict):
        pdf_metadata = {}

    # Garantir o retorno como string para evitar incompatibilidade de schema
    def get_metadata_value(key):
        value = pdf_metadata.get(key, 'N/A')
        return str(value) if value is not None else 'N/A'

    return Row(
        file_path=str(pdf_path),
        title=get_metadata_value('title'),
        author=get_metadata_value('author'),
        creator=get_metadata_value('creator'),
        subject=get_metadata_value('subject'),
        creation_date=get_metadata_value('creationDate'),
        modification_date=get_metadata_value('modDate'),
        content=str(pdf_text) if pdf_text is not None else '',
        ocr_pages=int(ocr_pages)
    )

# COMMAND ----------

# Função para analisar e formatar a data extraída do PDF
def parse_pdf_date(pdf_date_str):
    try:
        if pdf_date_str in (None, 'N/A'):
            return None
        
        date_str = pdf_date_str.strip()
        if date_str.startswith('D:'):
            date_str = date_str[2:]
        
        # Regex para extrair os componentes da data
        pattern = r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(Z|[+\-]\d{2}'?(\d{2})'?)?$"
        match = re.match(pattern, date_str)
        
        if not match:
            # Tentar correspondência com apenas data (YYYYMMDD)
            pattern = r"^(\d{4})(\d{2})(\d{2})$"
            match = re.match(pattern, date_str)
            if not match:
                return None
            else:
                year, month, day = match.groups()
                dt_str = f"{year}-{month}-{day} 00:00:00+00:00"
                return dt_str
        else:
            year, month, day, hour, minute, second, tz, tz_minute = match.groups()
            dt_str = f"{year}-{month}-{day} {hour}:{minute}:{second}"
            if tz:
                if tz == 'Z':
                    tz_str = '+00:00'
                else:
                    # Remove apóstrofos e adiciona dois pontos entre horas e minutos
                    tz = tz.replace("'", "")
                    if tz_minute:
                        tz_str = f"{tz[:3]}:{tz_minute}"
                    else:
                        tz_str = f"{tz[:3]}:00"
                dt_str += tz_str
            else:
                # Se não tiver fuso horário, assumir UTC
                dt_str += '+00:00'
            return dt_str
    except Exception as e:
        return None

# COMMAND ----------

# Função para verificar a proporção de caracteres válidos num texto
def valid_char_ratio(text):
    if text is None:
        return 0
    total_chars = len(text)
    if total_chars == 0:
        return 0
    valid_chars = len(re.findall(r'[A-Za-z0-9.,!?;: ]', text))
    return valid_chars / total_chars

# COMMAND ----------

# Função para obter a URL de origem de cada PDF a partir da tabela de logs de ingestão, que registra onde cada arquivo
# foi salvo. Se o mesmo arquivo foi baixado mais de uma vez (e sobrescrito na camada Raw), vale o download mais recente.
def get_pdf_source_urls():
    window_file = Window.partitionBy("ds_file_path").orderBy(col("dt_ocurrence").desc())

    return (
        spark.read.format("delta").load(ingestion_control_path)
        .filter((col("ds_status") == "Sucesso") & (col("ds_data_format") == "PDF"))
        .withColumn("row_number", row_number().over(window_file))
        .filter(col("row_number") == 1)
        .select(col("ds_file_path").alias("file_path"), col("ds_affected_url").alias("url"))
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Extração e Transformação dos Dados 
# MAGIC

# COMMAND ----------

# Encontrar timestamp da última extração para evitar reprocessamento
last_extraction = get_checkpoint_by_source(checkpoint_path=checkpoint_path, source_path=input_base_path)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Extração e Agregação do Conteúdo dos PDFs

# COMMAND ----------

# Listar todos os PDFs na estrutura de subdiretórios desde a última extração
pdf_files = list_all_files(base_dir=input_base_path, file_format="pdf", min_modified_timestamp=last_extraction)

# COMMAND ----------

if pdf_files:
    # Processos (e não threads) para paralelizar a leitura e o OCR dos PDFs: o PyMuPDF não é thread-safe,
    # e com threads o processamento ficaria, na prática, sequencial.
    # Os resultados chegam conforme cada PDF termina, para acompanhar o progresso; a ordem não importa.
    pdf_text_data = []
    ocr_pages_so_far = 0
    start = time.time()
    with Pool(processes=num_processes, initializer=silence_native_stderr, maxtasksperchild=max_tasks_per_process) as pool:
        for row in pool.imap_unordered(process_pdf, pdf_files):
            pdf_text_data.append(row)
            ocr_pages_so_far += row.ocr_pages
            done = len(pdf_text_data)
            print(f"{done}/{len(pdf_files)} PDFs ({done / len(pdf_files):.0%}) | páginas com OCR: {ocr_pages_so_far} | {(time.time() - start) / 60:.1f} min", flush=True)

    # Resumo do OCR
    ocr_docs = [row for row in pdf_text_data if row.ocr_pages > 0]
    print(f"PDFs processados: {len(pdf_text_data)} | PDFs com OCR: {len(ocr_docs)} | Páginas com OCR: {sum(row.ocr_pages for row in ocr_docs)}")

    # Criar o DataFrame a partir da lista de Rows
    df_pdf = spark.createDataFrame(pdf_text_data)

else:
    dbutils.notebook.exit("Não foram encontrados arquivos PDF novos ou atualizados para processar. O processamento será interrompido.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Limpeza e Estruturação dos Dados

# COMMAND ----------

# Registrar função de formatação de data como UDF no Spark
parse_pdf_date_udf = udf(parse_pdf_date, StringType())

# Registrar função para verificar a proporção de caracteres válidos como UDF no Spark
valid_char_ratio_udf = udf(valid_char_ratio, DoubleType())

# COMMAND ----------

# Transformar as datas para o formato Timestamp padrão
df_pdf_processed = (
    df_pdf
    .withColumnRenamed('creation_date', 'creation_date_pdf')
    .withColumnRenamed('modification_date', 'modification_date_pdf')
    .withColumn('parsed_creation_date_str', parse_pdf_date_udf(col('creation_date_pdf')))
    .withColumn('parsed_modification_date_str', parse_pdf_date_udf(col('modification_date_pdf')))
    .withColumn('creation_date', to_timestamp(col('parsed_creation_date_str'), "yyyy-MM-dd HH:mm:ssXXX"))
    .withColumn('modification_date', to_timestamp(col('parsed_modification_date_str'), "yyyy-MM-dd HH:mm:ssXXX"))
)

# COMMAND ----------

df_poli_consolidated_pdf = (
    df_pdf_processed
    .withColumn("content", regexp_replace(col("content"), "(?i)(figura|fig|figure|imagem)\s*\d+[:\-].*", ""))  # remover legendas de figuras
    .withColumn("content", trim(regexp_replace(col("content"), "[ ]+", " ")))  # normalizar espaços no texto
    .withColumn("content", regexp_replace(col("content"), "(\n| \n){2,}", "\n\n"))  # normalizar quebras de linha no texto
    .filter(valid_char_ratio_udf(col("content")) > 0.8)  # desconsiderar arquivos com muitos caracteres especiais
    .filter(length(col("content")) > 200)  # desconsiderar arquivos muito curtos
    .filter(col("content").isNotNull())
    .dropDuplicates(["content"])
    .join(get_pdf_source_urls(), on="file_path", how="left")  # URL de origem de cada PDF
    .replace('N/A', None)
    .replace('', None)
    .select(
        col("file_path").cast("string"),
        col("url").cast("string"),
        col("title").cast("string"),
        col("author").cast("string"),
        col("creator").cast("string"),
        col("creation_date").cast("timestamp"),
        col("modification_date").cast("timestamp"),
        col("content").cast("string"),
        # Adicionando data de atualização do registro em milissegundos para usar nas leituras incrementais
        (unix_timestamp(current_timestamp()) * 1000).cast("long").alias("_update_timestamp")
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Escrita no Data Lake

# COMMAND ----------

upsert_to_delta_lake(df=df_poli_consolidated_pdf, delta_table_path=output_path, key_column="file_path")
save_checkpoint(checkpoint_path=checkpoint_path, source_path=input_base_path, target_path=output_path)
