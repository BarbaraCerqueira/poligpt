locals {
  key_vault_ref = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.main.name};SecretName=%s)"
}

# ---------------------------------------------------------------------------
# API do chat (backend/)
# ---------------------------------------------------------------------------
resource "azurerm_service_plan" "chat" {
  name                = "asp-poligpt-chat-dev"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  os_type             = "Linux"
  sku_name            = "FC1"
}

resource "azurerm_function_app_flex_consumption" "chat" {
  name                = "func-poligpt-chat-dev"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  service_plan_id     = azurerm_service_plan.chat.id

  storage_container_type      = "blobContainer"
  storage_container_endpoint  = "${azurerm_storage_account.functions.primary_blob_endpoint}${azurerm_storage_container.function_deployments["chat"].name}"
  storage_authentication_type = "StorageAccountConnectionString"
  storage_access_key          = azurerm_storage_account.functions.primary_access_key

  runtime_name           = "python"
  runtime_version        = "3.11"
  instance_memory_in_mb  = 2048
  maximum_instance_count = 10

  https_only                                     = true
  webdeploy_publish_basic_authentication_enabled = false

  # Identidade usada para ler os segredos do Key Vault (referências em app_settings).
  identity {
    type = "SystemAssigned"
  }

  app_settings = {
    OPENAI_API_KEY         = format(local.key_vault_ref, "openai-api-key")
    AZURE_SEARCH_QUERY_KEY = format(local.key_vault_ref, azurerm_key_vault_secret.search_query_key.name)
    AZURE_SEARCH_ENDPOINT  = "https://${azurerm_search_service.main.name}.search.windows.net"
    SEARCH_INDEX_NAME      = "poligpt-index"
    COMPLETION_MODEL       = "gpt-6-luna"
    REASONING_EFFORT       = "low"
    EMBEDDING_MODEL        = "text-embedding-3-large"
    EMBEDDING_DIMENSIONS   = "1024"
    NUM_DOCS_TO_RETRIEVE   = "8"
    # Habilita respostas HTTP em stream (extensão FastAPI do Azure Functions)
    PYTHON_ENABLE_INIT_INDEXING = "1"
  }

  site_config {
    application_insights_connection_string = azurerm_application_insights.main.connection_string

    cors {
      allowed_origins = concat(var.chat_cors_allowed_origins, ["https://${azurerm_static_web_app.frontend.default_host_name}"])
    }
  }
}

# Chave padrão da função do chat (guardada no Key Vault em key_vault.tf).
data "azurerm_function_app_host_keys" "chat" {
  name                = azurerm_function_app_flex_consumption.chat.name
  resource_group_name = azurerm_resource_group.main.name
}

# ---------------------------------------------------------------------------
# Função de embeddings chamada pelo skillset do AI Search (search/embedding-function/)
# ---------------------------------------------------------------------------
resource "azurerm_service_plan" "embedding" {
  name                = "asp-poligpt-embed-dev"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  os_type             = "Linux"
  sku_name            = "FC1"
}

resource "azurerm_function_app_flex_consumption" "embedding" {
  name                = "func-poligpt-embed-dev"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  service_plan_id     = azurerm_service_plan.embedding.id

  storage_container_type      = "blobContainer"
  storage_container_endpoint  = "${azurerm_storage_account.functions.primary_blob_endpoint}${azurerm_storage_container.function_deployments["embedding"].name}"
  storage_authentication_type = "StorageAccountConnectionString"
  storage_access_key          = azurerm_storage_account.functions.primary_access_key

  runtime_name           = "python"
  runtime_version        = "3.11"
  instance_memory_in_mb  = 2048
  maximum_instance_count = 10

  https_only                                     = true
  webdeploy_publish_basic_authentication_enabled = false

  # Identidade usada pelo código para ler a chave da OpenAI no Key Vault.
  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_insights_connection_string = azurerm_application_insights.main.connection_string
  }
}

# Chave padrão da função, usada pelo skillset do AI Search no cabeçalho x-functions-key.
data "azurerm_function_app_host_keys" "embedding" {
  name                = azurerm_function_app_flex_consumption.embedding.name
  resource_group_name = azurerm_resource_group.main.name
}
