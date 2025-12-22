variable "aws_region" {
  description = "AWS region to deploy to"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
  default     = "n8n"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.small"
}

variable "root_volume_size" {
  description = "Size of root EBS volume in GB"
  type        = number
  default     = 30
}

variable "domain_name" {
  description = "Domain name for n8n (e.g., n8n.example.com)"
  type        = string
}

variable "key_name" {
  description = "Name of existing EC2 key pair for SSH access"
  type        = string
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed to SSH (e.g., your IP: x.x.x.x/32)"
  type        = string
  default     = "0.0.0.0/0"
}

variable "n8n_version" {
  description = "n8n Docker image version (use 'latest' or specific version like '1.20.0')"
  type        = string
  default     = "latest"
}

variable "timezone" {
  description = "Timezone for n8n (e.g., America/New_York, UTC)"
  type        = string
  default     = "UTC"
}
