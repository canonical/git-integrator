# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Constants to be used in the Git Integrator charm."""

GIT_ENDPOINT = "git"

REPOSITORY_URL_CONFIG = "repository_url"
PATH_CONFIG = "path"
TRACKING_REF_CONFIG = "tracking_ref"
AUTHENTICATION_METHOD_CONFIG = "authentication_method"
CREDENTIALS_USERNAME_CONFIG = "credentials_username"
CREDENTIALS_PERSONAL_ACCESS_TOKEN_SECRET_CONFIG = "credentials_personal_access_token_secret"
SSH_PRIVATE_KEY_SECRET_CONFIG = "ssh_private_key_secret"
SSH_STRICT_HOST_KEY_CHECKING_CONFIG = "ssh_strict_host_key_checking"

PERSONAL_ACCESS_TOKEN = "credentials-personal-access-token"
SSH_PRIVATE_KEY = "ssh-private-key"

MISSING_REPOSITORY_URL_MESSAGE = "Missing required configuration 'repository_url'"
INVALID_AUTHENTICATION_MESSAGE = "Invalid authentication method"
MISSING_USERNAME_MESSAGE = "Missing username for authentication credentials"
MISSING_PERSONAL_ACCESS_TOKEN_SECRET_MESSAGE = (
    "Missing personal access token secret for authentication credentials"
)
INVALID_PERSONAL_ACCESS_TOKEN_SECRET_MESSAGE = "Personal access token secret not valid"
MISSING_PERSONAL_ACCESS_TOKEN_IN_SECRET_MESSAGE = "Missing personal access token in secret"
MISSING_SSH_PRIVATE_KEY_SECRET_MESSAGE = "Missing SSH private key secret"
INVALID_SSH_PRIVATE_KEY_MESSAGE = "SSH private key secret not valid"
MISSING_SSH_PRIVATE_KEY_IN_SECRET_MESSAGE = "Missing SSH private key in secret"
