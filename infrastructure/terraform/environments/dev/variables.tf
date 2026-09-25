variable "location" {
  description = "Primary Azure region for the development environment"
  type        = string
  default     = "uksouth"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project identifier"
  type        = string
  default     = "ai-rag"
}

variable "owner" {
  description = "Resource owner"
  type        = string
}