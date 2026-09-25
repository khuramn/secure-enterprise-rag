locals {
  common_tags = {
    project      = "secure-enterprise-rag"
    environment  = var.environment
    managed-by   = "terraform"
    purpose      = "ai-security-portfolio"
    owner        = var.owner
    data-class   = "synthetic"
  }
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${var.project_name}-${var.environment}-uks"
  location = var.location

  tags = local.common_tags
}