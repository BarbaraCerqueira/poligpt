# Databricks notebook source
# MAGIC %md
# MAGIC # Ingestão de Dados - HTMLs e Arquivos Adjacentes

# COMMAND ----------

import os
import sys
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urlparse

etl_folder_path = './../../pipeline/'
sys.path.append(etl_folder_path)

from pyspark.sql.utils import AnalysisException
from pyspark.sql.window import Window
from pyspark.sql.functions import col, lit, when, row_number
from utils.ingestion_logs import log_ingestion_event

# COMMAND ----------

# MAGIC %md
# MAGIC ## Definição de Parâmetros

# COMMAND ----------

job_id = f"{int(datetime.now().timestamp())}"
headers = {'User-Agent': 'PoliGPT/1.0'}
output_path_html = "/mnt/adlsraw/html/"
output_path_pdf = "/mnt/adlsraw/pdf/"
sitemap_control_path = "/mnt/adlscontrol/sitemap_urls/"
ingestion_control_path = "/mnt/adlscontrol/ingestion_logs/"

# COMMAND ----------

# Widgets para receber os inputs do Workflow
# job_id = dbutils.notebook.entry_point.getDbutils().notebook().getContext().tags().get("runId").get()
# output_path_html = dbutils.widgets.get("output_path_html")
# output_path_pdf = dbutils.widgets.get("output_path_pdf")
# sitemap_control_path = dbutils.widgets.get("sitemap_control_path")
# ingestion_control_path = dbutils.widgets.get("ingestion_control_path")

# COMMAND ----------

# Sub-sitemaps que contém apenas páginas com informações redundantes, irrelevantes para o contexto ou inexistentes, e que não devem ser ingeridos
sub_sitemaps_to_ignore = [
    "http://poli.ufrj.br/category-sitemap.xml", 
    "http://poli.ufrj.br/courses-sitemap.xml",
    "http://poli.ufrj.br/curso-sitemap.xml",
    "http://poli.ufrj.br/docente-sitemap.xml",
    "http://poli.ufrj.br/tecnico-sitemap.xml",
    "http://poli.ufrj.br/imprensa-sitemap.xml",
    "http://poli.ufrj.br/publicacao-sitemap.xml",
    "http://poli.ufrj.br/video-podcast-sitemap.xml",
    "http://poli.ufrj.br/post_tag-sitemap.xml"
]

# COMMAND ----------

# MAGIC %md
# MAGIC ## Funções

# COMMAND ----------

# Verifica se o diretório existe no ADLS e, se não existir, cria o diretório
def ensure_directory_exists(directory_path):
    try:
        dbutils.fs.ls(directory_path)
    except Exception as e:
        if "java.io.FileNotFoundException" in str(e):
            dbutils.fs.mkdirs(directory_path)
            print(f"Diretório criado: {directory_path}")
        else:
            print(f"Erro inesperado ao verificar ou criar o diretório {directory_path}: {e}")
            raise e

# Função para extrair o domínio de uma URL e gerar um identificador único
def generate_url_id(url):
    parsed_url = urlparse(url)
    return parsed_url.netloc.replace(".", "_") + parsed_url.path.replace("/", "_")

# Função para fazer o download do HTML e salvar no ADLS
def download_html(url, url_id):
    try:
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        html_content = response.text
        
        # Caminho de destino no ADLS
        html_path = os.path.join(output_path_html, url_id, "index.html")
        
        # Escrevendo o HTML no ADLS
        dbutils.fs.put(html_path, html_content, overwrite=True)
        print(f"HTML salvo em: {html_path}")

        log_ingestion_event(job_id, url, "HTML", "Sucesso", "Arquivo extraído e salvo com sucesso", file_path=html_path)
        return html_content
    
    except requests.exceptions.Timeout:
        print("Timeout ao tentar acessar URL")
        log_ingestion_event(job_id, url, "HTML", "Falha", "Timeout ao tentar acessar URL")
        return None
    
    except requests.exceptions.ConnectionError:
        print("Erro de conexão ao acessar URL")
        log_ingestion_event(job_id, url, "HTML", "Falha", "Erro de conexão ao acessar URL")
        return None
    
    except requests.exceptions.HTTPError as e:
        print(f"Erro HTTP ao acessar URL: {e.response.status_code} - {e.response.reason}")
        log_ingestion_event(job_id, url, "HTML", "Falha", f"Erro HTTP ao acessar URL: {e.response.status_code} - {e.response.reason}")
        return None
    
    except Exception as e:
        print("Erro inesperado ao baixar HTML: {str(e)}")
        log_ingestion_event(job_id, url, "HTML", "Falha", f"Erro inesperado ao baixar HTML: {str(e)}")
        return None

# Função para localizar PDFs indicados em uma página HTML e salvá-los no ADLS
def download_pdfs(html_content, url_id, base_url):
    if html_content:
        # Parsear o conteúdo HTML para encontrar links de PDF
        soup = BeautifulSoup(html_content, "html.parser")
        pdf_links = [link.get('href') for link in soup.find_all('a') if link.get('href') and link.get('href').endswith('.pdf')]
        
        for link in pdf_links:
            # Resolver links relativos
            pdf_url = requests.compat.urljoin(base_url, link)

            try:
                # Fazer o download do PDF
                pdf_response = requests.get(pdf_url, timeout=10, headers=headers)
                pdf_response.raise_for_status()
                pdf_content = pdf_response.content
                
                # Caminho de destino no ADLS
                pdf_name = os.path.basename(pdf_url)
                pdf_path = os.path.join(output_path_pdf, url_id, pdf_name)
                
                # Verificar se o diretório de destino existe, senão criar
                directory_path = os.path.join(output_path_pdf, url_id)
                ensure_directory_exists(directory_path)

                # Salvar o PDF no mount do ADLS
                with open(f"/dbfs{pdf_path}", "wb") as pdf_file:
                    pdf_file.write(pdf_content)
                print(f"PDF salvo em: {pdf_path}")

                log_ingestion_event(job_id, pdf_url, "PDF", "Sucesso", "Arquivo extraído e salvo com sucesso", file_path=pdf_path)
            
            except requests.exceptions.Timeout:
                print("Timeout ao tentar baixar o PDF")
                log_ingestion_event(job_id, pdf_url, "PDF", "Falha", "Timeout ao tentar baixar o PDF")
            
            except requests.exceptions.ConnectionError:
                print("Erro de conexão ao acessar PDF")
                log_ingestion_event(job_id, pdf_url, "PDF", "Falha", "Erro de conexão ao acessar PDF")
            
            except requests.exceptions.HTTPError as e:
                print( f"Erro HTTP ao acessar PDF: {e.response.status_code} - {e.response.reason}")
                log_ingestion_event(job_id, pdf_url, "PDF", "Falha",  f"Erro HTTP ao acessar PDF: {e.response.status_code} - {e.response.reason}")

            except FileNotFoundError as e:
                print("Erro ao tentar acessar o diretório de destino para salvar o PDF")
                log_ingestion_event(job_id, pdf_url, "PDF", "Falha", "Erro ao tentar acessar o diretório de destino para salvar o PDF")

            except Exception as e:
                print(f"Erro inesperado ao baixar PDF: {str(e)}")
                log_ingestion_event(job_id, pdf_url, "PDF", "Falha", f"Erro inesperado ao baixar PDF: {str(e)}")

    else:
        print("HTML não encontrado")
        log_ingestion_event(job_id, pdf_url, "PDF", "Falha",  "HTML não encontrado")


# COMMAND ----------

# MAGIC %md
# MAGIC ## Determinar os Dados que precisam de Atualização
# MAGIC Acessar as tabelas de controle para verificar as páginas do site da Politécnica que foram atualizadas desde a última ingestão bem-sucedida.

# COMMAND ----------

# Ler tabela de controle de Sitemap com as URLs do site
df_control_sitemap = spark.read.format("parquet").load(sitemap_control_path)

# COMMAND ----------

try:
    # Tenta ler tabela de controle de Ingestão com as datas e status de ingestão de cada URL
    df_control_ingestion = spark.read.format("delta").load(ingestion_control_path)

    # Filtrar a tabela de controle de ingestão pelas datas de última ingestão de conteúdo HTML bem sucedida
    window_spec = Window.partitionBy("ds_affected_url").orderBy(col("dt_ocurrence").desc())
    df_control_ingestion_filtered = (
        df_control_ingestion
        .filter(col("ds_data_format") == "HTML")
        .filter(col("ds_status") == "Sucesso")
        .withColumn("row_number", row_number().over(window_spec))
        .filter(col("row_number") == 1)
        .drop("row_number")
        .withColumnRenamed("dt_ocurrence", "dt_last_sucessful_ingestion")
        .distinct()
    )

    # Obter as URLs elegíveis que foram modificadas depois da última ingestão bem sucedida
    urls_to_update = (
        df_control_sitemap
        .join(df_control_ingestion_filtered, col("ds_url") == col("ds_affected_url"), how="left")
        .withColumn("need_update", 
                    when(
                        (col("dt_last_sucessful_ingestion").isNull()) | 
                        (col("dt_last_modification") > col("dt_last_sucessful_ingestion")), 
                        True)
                    .otherwise(False))
        .filter(~col("ds_sub_sitemap").isin(sub_sitemaps_to_ignore))  # remover urls indesejadas
        .filter(col("need_update") == True)
        .select(col("ds_url"))
        .distinct()
        .rdd.flatMap(lambda row: row) # Mapear valores para uma lista
        .collect()  
    )

    print(f"Tabela de controle de ingestão lida com sucesso. Foram encontradas {len(urls_to_update)} URLs que foram modificadas depois da última ingestão bem sucedida.")

except AnalysisException as e:
    # Obter todas as urls elegíveis contidas na tabela de controle de sitemap
    urls_to_update = (
        df_control_sitemap
        .filter(~col("ds_sub_sitemap").isin(sub_sitemaps_to_ignore))  # remover urls indesejadas
        .select(col("ds_url"))
        .distinct()
        .rdd.flatMap(lambda row: row) # Mapear valores para uma lista
        .collect()  
    )

    print("Não foi possível ler a tabela de controle de ingestão. Todos os dados serão atualizados.")

# COMMAND ----------

print("Serão atualizados os dados referentes às seguintes URLs:")
for url in urls_to_update:
    print(url)

print(f"{'-'*100}")
print(f"Total de URLs a serem processadas: {len(urls_to_update)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Extrair Dados do Site da Politécnica e Escrever no Data Lake
# MAGIC ...
# MAGIC
# MAGIC Ao final é adicionado um log de ingestão bem sucedida. A ingestão só é considerada bem sucedida se todos os HTMLs foram baixados e salvos no ADLS com sucesso (a falha no download dos arquivos PDF associados é tratado como Warning para fins de auditoria e não termina a execução). Caso ocorra alguma falha, o notebook será interrompido e um log de Falha será adicionado. Isso é feito para evitar que na próxima ingestão os arquivos que falharam sejam ignorados e uma nova tentativa de extração seja executada.

# COMMAND ----------

# Loop pelas URLs fornecidas
for i, url in enumerate(urls_to_update):
    url_id = generate_url_id(url.strip())
    print(f"Process {i+1}/{len(urls_to_update)} - Processando URL: {url} (ID: {url_id})")
    
    # Download do HTML
    html_content = download_html(url, url_id)
    
    if html_content:
        # Download de PDFs dentro do HTML se existirem
        download_pdfs(html_content, url_id, url)

    print(f"{'-'*100}")

    # Intervalo entre requisições
    time.sleep(1)
