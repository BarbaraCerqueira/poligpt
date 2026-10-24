from datetime import datetime
from pyspark.sql import SparkSession
from pyspark.sql.functions import lit

spark = SparkSession.builder.getOrCreate()

INGESTION_TABLE_PATH = "/mnt/adlscontrol/ingestion_logs/"

def log_ingestion_event(run_id, url, data_format, status, log_message, file_path=None):
    """
    Registra um evento durante a ingestão de dados na tabela de controle de ingestão. 
    A cada URL processada, um novo registro é criado na tabela de controle de ingestão, 
    indicando o status da operação, o horário da ocorrência e outras informações.

    Args:
        run_id (str): ID único de execução do notebook.
        url (str): URL da fonte de dados que gerou o evento.
        data_format (str): Formato do arquivo de dados ingerido ('PDF', 'HTML').
        status (str): Status da operação ('Sucesso', 'Falha', 'Aviso').
        log_message (str): Mensagem de log.
        file_path (str, opcional): Caminho onde o arquivo foi salvo no Data Lake (apenas em caso de sucesso).
    
    Returns:
        None
    """
    try:
        datetime_now = datetime.now()
        new_entry = [(run_id, datetime_now, url, data_format, status, log_message)]
        df = (
            spark.createDataFrame(new_entry, ["id_run", "dt_ocurrence", "ds_affected_url", "ds_data_format", "ds_status", "ds_log_message"])
            .withColumn("ds_file_path", lit(file_path).cast("string"))
        )
        df.write.format("delta").option("header", "true").option("mergeSchema", "true").mode("append").save(INGESTION_TABLE_PATH)
        print(f"Novo log de ingestão salvo com ID: {run_id}")        
    
    except Exception as e:
        print(f"Erro ao registrar evento de ingestão: {e}")
