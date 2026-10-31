output "resource_group_name" {
  description = "Name of the development resource group"
  value       = azurerm_resource_group.main.name
}

output "resource_group_location" {
  description = "Azure region of the development resource group"
  value       = azurerm_resource_group.main.location
}

output "document_storage_account_name" {
  description = "Storage account containing synthetic RAG documents"
  value       = azurerm_storage_account.documents.name
}

output "document_container_name" {
  description = "Blob container containing synthetic RAG documents"
  value       = azurerm_storage_container.documents.name
}

output "search_service_name" {
  description = "Azure AI Search service used by the RAG application"
  value       = azurerm_search_service.rag.name
}