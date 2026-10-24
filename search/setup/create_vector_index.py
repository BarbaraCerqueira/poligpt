from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    ScalarQuantizationCompression,
    ScalarQuantizationParameters,
    RescoringOptions,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField,
    SearchIndex
)

kv_uri = "https://kv-poligpt-dev-eastus2.vault.azure.net"
credential = DefaultAzureCredential()
client = SecretClient(vault_url=kv_uri, credential=credential)

azure_search_endpoint = client.get_secret("azure-search-endpoint").value
azure_search_admin_key = client.get_secret("azure-search-admin-key").value
azure_search_credential = AzureKeyCredential(azure_search_admin_key)
embedding_dimensions = 1024
project_name = "poligpt"


# Create a search index  
index_client = SearchIndexClient(endpoint=azure_search_endpoint, credential=azure_search_credential)  
fields = [  
    SearchField(name="chunk_id", type=SearchFieldDataType.String, key=True, sortable=True, filterable=True, analyzer_name="keyword"),
    SearchField(name="parent_id", type=SearchFieldDataType.String, sortable=True, filterable=True, facetable=True),  
    SearchField(name="url", type=SearchFieldDataType.String, searchable=False, filterable=True),
    SearchField(name="title", type=SearchFieldDataType.String, searchable=True, sortable=True, filterable=True),
    SearchField(name="keywords", type=SearchFieldDataType.String, searchable=True, sortable=True, filterable=True),
    SearchField(name="last_modified", type=SearchFieldDataType.String, searchable=False, sortable=True, filterable=True),
    SearchField(name="chunk", type=SearchFieldDataType.String, searchable=True, sortable=False, filterable=False),
    # stored=False: não guarda uma cópia dos vetores para devolver nas consultas (a aplicação nunca lê o vetor),
    # o que economiza espaço no índice.
    SearchField(name="vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), vector_search_dimensions=embedding_dimensions, vector_search_profile_name="poligpt-profile", stored=False)
]

# Configure the vector search configuration
vector_search = VectorSearch(
    algorithms=[
        HnswAlgorithmConfiguration(name="poligpt-hnsw"),
    ],
    # Quantização escalar: o índice vetorial (HNSW) guarda cada dimensão como int8 (1 byte) em vez de
    # float32 (4 bytes), ficando ~4x menor. Os vetores originais são preservados e usados para reordenar
    # os candidatos (rescoring), buscando 4x mais candidatos do que o pedido, para manter a qualidade da busca.
    compressions=[
        ScalarQuantizationCompression(
            compression_name="poligpt-scalar-quantization",
            parameters=ScalarQuantizationParameters(quantized_data_type="int8"),
            rescoring_options=RescoringOptions(
                enable_rescoring=True,
                default_oversampling=4,
                rescore_storage_method="preserveOriginals",
            ),
        )
    ],
    profiles=[
        VectorSearchProfile(
            name="poligpt-profile",
            algorithm_configuration_name="poligpt-hnsw",
            compression_name="poligpt-scalar-quantization",
        )
    ]
)
  
semantic_config = SemanticConfiguration(  
    name="poligpt-semantic-config",  
    prioritized_fields=SemanticPrioritizedFields(  
        content_fields=[
            SemanticField(field_name="title"),
            SemanticField(field_name="keywords"),
            SemanticField(field_name="chunk")
        ]  
    ),  
)
  
# Create the semantic search with the configuration
semantic_search = SemanticSearch(configurations=[semantic_config])  
  
# Create the search index
index = SearchIndex(name=f"{project_name}-index", fields=fields, vector_search=vector_search, semantic_search=semantic_search)  
result = index_client.create_or_update_index(index)  
print(f"Search index created or updated: {result.name}")