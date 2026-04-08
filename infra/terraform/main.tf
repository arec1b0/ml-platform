terraform {
  required_version = ">= 1.6"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.0" }
  }
  backend "gcs" {
    bucket = "ml-platform-tfstate"
    prefix = "terraform/state"
  }
}

locals {
  project    = var.project_id
  region     = "europe-west6"   # Zürich
  cluster    = "ml-platform"
}

resource "google_container_cluster" "primary" {
  name                     = local.cluster
  location                 = local.region
  remove_default_node_pool = true
  initial_node_count       = 1

  workload_identity_config {
    workload_pool = "${local.project}.svc.id.goog"
  }

  addons_config {
    http_load_balancing { disabled = false }
  }
}

resource "google_container_node_pool" "inference" {
  name       = "inference-pool"
  cluster    = google_container_cluster.primary.name
  location   = local.region
  node_count = 2

  autoscaling {
    min_node_count = 2
    max_node_count = 6
  }

  node_config {
    machine_type = "n2-standard-4"   # 4 vCPU, 16GB — хватит для toxic-bert
    disk_size_gb = 50

    labels = { workload = "inference" }

    workload_metadata_config { mode = "GKE_METADATA" }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }
}

# Artifact Registry для образов
resource "google_artifact_registry_repository" "models" {
  location      = local.region
  repository_id = "ml-platform"
  format        = "DOCKER"
}