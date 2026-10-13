terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {
  host = var.docker_host
}

resource "docker_network" "agentnet" {
  name = "agentloop"
}

resource "docker_volume" "openwebui_data" {
  name = "agentloop_openwebui_data"
}

resource "docker_volume" "agent_audit" {
  name = "agentloop_audit"
}

resource "docker_image" "agent" {
  name = "agentloop-agent:local"
  build {
    context = "${path.module}/../agent"
  }
  triggers = {
    src = sha1(join("", [for f in ["Dockerfile", "app.py", "loop.py", "tools.py", "trace.py", "requirements.txt"] : filesha1("${path.module}/../agent/${f}")]))
  }
}

resource "docker_image" "openwebui" {
  name = "ghcr.io/open-webui/open-webui:${var.openwebui_tag}"
}

resource "docker_container" "agent" {
  name         = "agentloop-agent"
  image        = docker_image.agent.image_id
  restart      = "unless-stopped"
  memory       = 512
  network_mode = "bridge"
  networks_advanced {
    name    = docker_network.agentnet.name
    aliases = ["agent"]
  }
  host {
    host = "host.docker.internal"
    ip   = "host-gateway"
  }
  env = [
    "OLLAMA_URL=${var.ollama_url}",
    "MODEL=${var.model}",
  ]
  ports {
    internal = 8000
    external = var.agent_port
    ip       = "127.0.0.1"
  }
  volumes {
    volume_name    = docker_volume.agent_audit.name
    container_path = "/data"
  }
  healthcheck {
    test     = ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://localhost:8000/healthz')"]
    interval = "10s"
    timeout  = "3s"
    retries  = 3
  }
}

resource "docker_container" "openwebui" {
  name    = "agentloop-openwebui"
  image   = docker_image.openwebui.image_id
  restart = "unless-stopped"
  memory  = 1536
  networks_advanced {
    name = docker_network.agentnet.name
  }
  env = [
    "OPENAI_API_BASE_URL=http://agent:8000/v1",
    "OPENAI_API_KEY=local",
    "ENABLE_OLLAMA_API=false",
    "WEBUI_AUTH=false",
    "AUDIT_LOG_LEVEL=REQUEST_RESPONSE",
  ]
  ports {
    internal = 8080
    external = var.webui_port
    ip       = "127.0.0.1"
  }
  volumes {
    volume_name    = docker_volume.openwebui_data.name
    container_path = "/app/backend/data"
  }
  depends_on = [docker_container.agent]
}
