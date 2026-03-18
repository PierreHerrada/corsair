variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "project_name" {
  type    = string
  default = "corsair"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "control_plane_cpu" {
  type    = number
  default = 512
}

variable "control_plane_memory" {
  type    = number
  default = 1024
}

variable "agent_default_cpu" {
  type    = number
  default = 1024
}

variable "agent_default_memory" {
  type    = number
  default = 2048
}

variable "agent_db_dind_cpu" {
  type    = number
  default = 2048
}

variable "agent_db_dind_memory" {
  type    = number
  default = 4096
}
