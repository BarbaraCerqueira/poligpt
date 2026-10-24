from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.search.documents.indexes import SearchIndexerClient
from azure.search.documents.indexes.models import (
    SplitSkill,
    InputFieldMappingEntry,
    OutputFieldMappingEntry,
    WebApiSkill,
    SearchIndexerIndexProjection,
    SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters,
    IndexProjectionMode,
    SearchIndexerSkillset
)

kv_uri = "https://kv-poligpt-dev-eastus2.vault.azure.net"
credential = DefaultAzureCredential()
client = SecretClient(vault_url=kv_uri, credential=credential)

azure_search_endpoint = client.get_secret("azure-search-endpoint").value
azure_search_admin_key = client.get_secret("azure-search-admin-key").value
azure_search_credential = AzureKeyCredential(azure_search_admin_key)
custom_embedding_api_key = client.get_secret("custom-embedding-function-key").value
custom_embedding_url = client.get_secret("custom-embedding-function-url").value
embedding_model = "text-embedding-3-large"
embedding_dimensions = 1024
project_name = "poligpt"


# Create a skillset  
skillset_name = f"{project_name}-skillset"

def create_skillset():
    split_skill = SplitSkill(  
        name=f"{project_name}-splitskill",
        description="Split skill to chunk documents", 
        default_language_code="pt-BR", 
        text_split_mode="pages",  
        context="/document",  
        maximum_page_length=4000,
        page_overlap_length=200,
        inputs=[  
            InputFieldMappingEntry(name="text", source="/document/ds_content_document"),
        ],  
        outputs=[  
            OutputFieldMappingEntry(name="textItems", target_name="pages")  
        ]
    )

    embedding_skill = WebApiSkill(  
        name=f"{project_name}-webapiskill",
        description="Skill to generate embeddings via Custom Web API",  
        context="/document/pages/*", 
        uri=custom_embedding_url,
        http_headers={
            "x-functions-key" : custom_embedding_api_key,
            "model" : embedding_model,
            "dimensions" : embedding_dimensions
        },
        http_method="POST",
        timeout="PT60S",
        batch_size=10,
        degree_of_parallelism=5,
        inputs=[  
            InputFieldMappingEntry(name="text", source="/document/pages/*"),  
        ],  
        outputs=[
            OutputFieldMappingEntry(name="embedding", target_name="vector")  
        ]
    )

    index_projection = SearchIndexerIndexProjection(  
        selectors=[
            SearchIndexerIndexProjectionSelector(  
                target_index_name=f"{project_name}-index",  
                parent_key_field_name="parent_id",  
                source_context="/document/pages/*",  
                mappings=[
                    InputFieldMappingEntry(name="url", source="/document/ds_url"),
                    InputFieldMappingEntry(name="title", source="/document/ds_title_document"),
                    InputFieldMappingEntry(name="keywords", source="/document/ds_keywords"),
                    InputFieldMappingEntry(name="last_modified", source="/document/dt_last_modified"),
                    InputFieldMappingEntry(name="chunk", source="/document/pages/*"),
                    InputFieldMappingEntry(name="vector", source="/document/pages/*/vector")
                ]
            )
        ],  
        parameters=SearchIndexerIndexProjectionsParameters(  
            projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS  
        )  
    )

    skills = [split_skill, embedding_skill]

    return SearchIndexerSkillset(
        name=skillset_name,  
        description="Skillset to chunk documents and generate embeddings",  
        skills=skills,  
        index_projection=index_projection
    )

skillset = create_skillset()
  
client = SearchIndexerClient(azure_search_endpoint, azure_search_credential)  
client.create_or_update_skillset(skillset)  
print(f"Skillset created or updated: {skillset.name}")  