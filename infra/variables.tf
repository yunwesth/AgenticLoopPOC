variable "docker_host" {
  type    = string
  default = "unix:///Users/yunwesth/.colima/default/docker.sock"
}

variable "model" {
  type    = string
  default = "qwen3:4b"
}

variable "ollama_url" {
  description = "Dedicated Ollama on the host (port 11435, so the existing :11434 is untouched)"
  type        = string
  default     = "http://host.docker.internal:11435"
}

variable "webui_port" {
  type    = number
  default = 3000
}

variable "agent_port" {
  type    = number
  default = 8000
}

variable "openwebui_tag" {
  type    = string
  default = "v0.12.0"
}
