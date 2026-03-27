resource "juju_application" "git_integrator" {
  name       = var.app_name
  model_uuid = var.model_uuid

  charm {
    name     = "git-integrator"
    revision = var.revision
    channel  = var.channel
  }

  constraints = var.constraints
  config      = var.config

  units = var.units
}
