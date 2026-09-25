output "resource_group_name" {
  description = "Name of the development resource group"
  value       = azurerm_resource_group.main.name
}

output "resource_group_location" {
  description = "Azure region of the development resource group"
  value       = azurerm_resource_group.main.location
}