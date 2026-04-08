output "cluster_endpoint" {
  value     = google_container_cluster.primary.endpoint
  sensitive = true
}

output "registry_url" {
  value = "${local.region}-docker.pkg.dev/${local.project}/ml-platform"
}