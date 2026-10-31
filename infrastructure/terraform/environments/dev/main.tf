locals {
  common_tags = {
    project     = "secure-enterprise-rag"
    environment = var.environment
    managed-by  = "terraform"
    purpose     = "ai-security-portfolio"
    owner       = var.owner
    data-class  = "synthetic"
  }
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${var.project_name}-${var.environment}-uks"
  location = var.location

  tags = local.common_tags
}

resource "random_string" "storage_suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "azurerm_storage_account" "documents" {
  name                     = "stairag${random_string.storage_suffix.result}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false

  tags = local.common_tags
}


resource "azurerm_storage_container" "documents" {
  name                  = "documents"
  storage_account_id    = azurerm_storage_account.documents.id
  container_access_type = "private"
}

resource "azurerm_search_service" "rag" {
  name                = "srch-${var.project_name}-${var.environment}-${random_string.storage_suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  sku             = "free"
  replica_count   = 1
  partition_count = 1

  local_authentication_enabled = false



  tags = local.common_tags
}


data "azurerm_client_config" "current" {}

resource "azurerm_role_assignment" "developer_blob_access" {
  scope                = azurerm_storage_account.documents.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "developer_search_index_access" {
  scope                = azurerm_search_service.rag.id
  role_definition_name = "Search Index Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "developer_search_service_access" {
  scope                = azurerm_search_service.rag.id
  role_definition_name = "Search Service Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}


resource "azurerm_cognitive_account" "embeddings" {
  name                = "oai-ai-rag-dev-nkihn6"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  kind     = "OpenAI"
  sku_name = "S0"

  local_auth_enabled    = false
  custom_subdomain_name = "oai-ai-rag-dev-nkihn6"

  tags = local.common_tags
}

resource "azurerm_cognitive_deployment" "embeddings" {
  name                 = "text-embedding-3-small"
  cognitive_account_id = azurerm_cognitive_account.embeddings.id

  model {
    format  = "OpenAI"
    name    = "text-embedding-3-small"
    version = var.embedding_model_version
  }

  sku {
    name     = "GlobalStandard"
    capacity = 1
  }
}

resource "azurerm_role_assignment" "developer_openai_user" {
  scope                = azurerm_cognitive_account.embeddings.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_cognitive_deployment" "rag_chat" {
  name                 = "rag-chat-mini"
  cognitive_account_id = azurerm_cognitive_account.embeddings.id

  model {
    format  = "OpenAI"
    name    = "gpt-4.1-mini"
    version = "2025-04-14"
  }

  sku {
    name     = "GlobalStandard"
    capacity = 1
  }
}