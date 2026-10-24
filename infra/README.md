# Infraestrutura (Terraform)

Infraestrutura do PoliGPT na Azure como código. Os recursos do resource group `rg-poligpt-dev-eastus2` foram importados a partir do ambiente existente, com alguns pequenos ajustes posteriores.

## Pré-requisitos

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.6
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) autenticada: `az login --tenant <tenant_id>`
- Permissão **Storage Blob Data Contributor** no storage account do state (`stpoligpttfstate`)

## Uso

```bash
cd infra
terraform init      # conecta ao state remoto e baixa os providers
terraform plan      # mostra o que mudaria — sempre revisar antes de aplicar
terraform apply
```

## Organização

| Arquivo | Recursos |
|---|---|
| `versions.tf` | Versões, backend do state e configuração do provider |
| `main.tf` | Resource group |
| `storage.tf` | Data Lake (ADLS Gen2) com os containers das camadas, e storage interno das Function Apps |
| `key_vault.tf` | Key Vault, políticas de acesso e os secrets derivados de outros recursos (URL e chave das Functions do chat e de embeddings) |
| `sql.tf` | Servidor e banco Azure SQL |
| `search.tf` | Serviço do Azure AI Search (os objetos internos são criados por `search/setup/`) |
| `functions.tf` | Function Apps do chat e da embedding-function, no plano Flex Consumption |
| `web.tf` | Static Web App do frontend |
| `monitoring.tf` | Log Analytics e Application Insights |
| `databricks.tf` | Workspace do Databricks, secret scope (Key Vault), Git folder, cluster interativo, job do pipeline e init script que instala o Tesseract OCR nos clusters |
| `iam.tf` | Permissões (role assignments) |

## State remoto

O state fica em `rg-poligpt-tfstate/stpoligpttfstate/tfstate/poligpt-dev.tfstate`, fora do resource group gerenciado. O storage account tem acesso por chave desativado (só Entra ID), versionamento, soft delete de 30 dias e um lock contra exclusão. Foi criado manualmente, fora do Terraform.

## Segredos

Nenhum segredo fica no código ou nos `.tfvars`. Os valores são guardados no Key Vault (`kv-poligpt-dev-eastus2`) e lidos em tempo de execução:

- A Function do chat lê a chave da OpenAI e a chave **somente leitura** (query key) do AI Search por **referências ao Key Vault** nas app settings (`@Microsoft.KeyVault(...)`), usando sua identidade gerenciada. A chave admin do AI Search fica só para os scripts de `search/setup/`.
- A embedding-function lê a chave da OpenAI diretamente do Key Vault no código, também com identidade gerenciada.
- A senha do administrador do SQL (usada pelo Databricks e pela fonte de dados do AI Search) fica só no Key Vault. O Terraform a lê durante a execução como recurso **efêmero** (o valor é descartado ao final, sem ir para o plano nem para o state) e a envia num atributo **write-only** (`administrator_login_password_wo`), que a Azure recebe mas o Terraform não grava. Detalhes e passo a passo para trocar a senha estão em [`sql.tf`](sql.tf).

## Deploy do código das Functions

O Terraform cria as Function Apps, mas não publica o código. O deploy é feito com o Azure Functions Core Tools:

```bash
cd backend && func azure functionapp publish func-poligpt-chat-dev --python
cd search/embedding-function && func azure functionapp publish func-poligpt-embed-dev --python
```

Se a embedding-function for recriada, rode `search/setup/create_skillset.py` para o skillset do AI Search apontar para a nova URL e chave.

## Proteções

Recursos que guardam dados (Data Lake, Key Vault, SQL, AI Search, Databricks) têm `prevent_destroy = true`: o Terraform se recusa a destruí-los.
