# CC008: charm modules must output the deployed application object.
output "application" {
  value = juju_application.git_integrator
}

output "provides" {
  value = {
    git = "git"
  }
}

output "requires" {
  value = {}
}
