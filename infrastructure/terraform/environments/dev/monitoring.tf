resource "azurerm_log_analytics_workspace" "rag" {
  name                = "log-${var.project_name}-${var.environment}-uks"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  sku               = "PerGB2018"
  retention_in_days = 30
  daily_quota_gb    = 0.5

  tags = local.common_tags
}

resource "azurerm_application_insights" "rag" {
  name                = "appi-${var.project_name}-${var.environment}-uks"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  application_type  = "web"
  workspace_id      = azurerm_log_analytics_workspace.rag.id
  retention_in_days = 30

  tags = local.common_tags
}
