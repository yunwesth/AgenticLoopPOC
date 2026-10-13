output "open_webui" {
  value = "http://localhost:${var.webui_port}"
}

output "agent_api" {
  value = "http://localhost:${var.agent_port}/v1"
}
