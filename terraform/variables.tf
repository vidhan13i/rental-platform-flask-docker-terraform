variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Prefix for all AWS resources"
  type        = string
  default     = "rental-platform"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "public_key_path" {
  description = "Path to your local SSH public key"
  type        = string
  default     = "/Users/vidhanmanihar/.ssh/id_rsa.pub"
}

variable "allowed_ssh_cidr" {
  description = "Your IP in CIDR format e.g. 1.2.3.4/32"
  type        = string
  default     = "0.0.0.0/0"
}

variable "jwt_secret" {
  description = "JWT secret for all services"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "PostgreSQL password"
  type        = string
  sensitive   = true
  default     = "postgres123"
}