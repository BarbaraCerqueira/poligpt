# Key Vault com os segredos do projeto. Segredos externos (chave da OpenAI, senhas) são gravados
# fora do Terraform (az keyvault secret set), para que nunca apareçam no código nem no state.
# Só os valores derivados de recursos do próprio Terraform são gerenciados aqui (fim do arquivo).
resource "azurerm_key_vault" "main" {
  name                = "kv-poligpt-dev-eastus2"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  tenant_id           = var.tenant_id
  sku_name            = "standard"

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_key_vault_access_policy" "admin" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = var.tenant_id
  object_id    = var.admin_object_id

  secret_permissions = ["Get", "List", "Set", "Delete", "Recover", "Backup", "Restore"]
}

# Necessário para o secret scope do Databricks baseado em Key Vault (poligpt-secret-scope).
resource "azurerm_key_vault_access_policy" "databricks" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = var.tenant_id
  object_id    = var.databricks_app_object_id

  secret_permissions = ["Get", "List"]
}

# Identidades das Functions: somente leitura.
resource "azurerm_key_vault_access_policy" "chat_function" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = var.tenant_id
  object_id    = azurerm_function_app_flex_consumption.chat.identity[0].principal_id

  secret_permissions = ["Get"]
}

resource "azurerm_key_vault_access_policy" "embedding_function" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = var.tenant_id
  object_id    = azurerm_function_app_flex_consumption.embedding.identity[0].principal_id

  secret_permissions = ["Get"]
}

# Endereço e chave da embedding-function, lidos pelo script search/setup/create_skillset.py.
# Ficam sincronizados automaticamente se a função for recriada.
resource "azurerm_key_vault_secret" "embedding_function_url" {
  name         = "custom-embedding-function-url"
  key_vault_id = azurerm_key_vault.main.id
  value        = "https://${azurerm_function_app_flex_consumption.embedding.default_hostname}/api/custom_web_api/openai_embeddings"

  depends_on = [azurerm_key_vault_access_policy.admin]
}

resource "azurerm_key_vault_secret" "embedding_function_key" {
  name         = "custom-embedding-function-key"
  key_vault_id = azurerm_key_vault.main.id
  value        = data.azurerm_function_app_host_keys.embedding.default_function_key

  depends_on = [azurerm_key_vault_access_policy.admin]
}

# Endereço e chave da API do chat, para quem precisar chamá-la (frontend, testes).
# Ficam sincronizados automaticamente se a função for recriada.
resource "azurerm_key_vault_secret" "chat_function_url" {
  name         = "chat-function-url"
  key_vault_id = azurerm_key_vault.main.id
  value        = "https://${azurerm_function_app_flex_consumption.chat.default_hostname}/api/chatcompletion"

  depends_on = [azurerm_key_vault_access_policy.admin]
}

resource "azurerm_key_vault_secret" "chat_function_key" {
  name         = "chat-function-key"
  key_vault_id = azurerm_key_vault.main.id
  value        = data.azurerm_function_app_host_keys.chat.default_function_key

  depends_on = [azurerm_key_vault_access_policy.admin]
}

# Chave somente leitura do AI Search, usada pela Function do chat (a chave admin fica só para os scripts de setup).
resource "azurerm_key_vault_secret" "search_query_key" {
  name         = "azure-search-query-key"
  key_vault_id = azurerm_key_vault.main.id
  value        = azurerm_search_service.main.query_keys[0].key

  depends_on = [azurerm_key_vault_access_policy.admin]
}
