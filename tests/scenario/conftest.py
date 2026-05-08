# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.


import charms.git_integrator.v0.git as git
import ops.testing
import pytest

import constants
from charm import GitIntegratorCharm

GIT_RELATION_ENDPOINT = "git"


@pytest.fixture
def context():
    return ops.testing.Context(charm_type=GitIntegratorCharm)


@pytest.fixture(scope="function")
def ssh_private_key_secret():
    return ops.testing.Secret(
        {
            constants.SSH_PRIVATE_KEY: "custom-ssh-private-key",
        },
    )


@pytest.fixture(scope="function")
def ssh_passphrase_secret():
    return ops.testing.Secret(
        {
            constants.SSH_PASSPHRASE: "custom-ssh-passphrase",
        },
    )


@pytest.fixture(scope="function")
def personal_access_token_secret():
    return ops.testing.Secret(
        {
            constants.PERSONAL_ACCESS_TOKEN: "custom-personal-access-token",
        },
    )


@pytest.fixture(scope="function")
def ssh_data(ssh_private_key_secret):
    return {
        "repository-url": "https://github.com/org/repo",
        "path": "my/directory",
        "tracking-ref": "custom/branch",
        "authentication-method": git.AuthenticationMethodEnum.SSH.value,
        "secret-ssh-private-key": ssh_private_key_secret.id,
        "ssh-strict-host-key-checking": "false",
    }


@pytest.fixture(scope="function")
def ssh_data_with_passphrase_and_port(ssh_private_key_secret, ssh_passphrase_secret):
    return {
        "repository-url": "https://github.com/org/repo",
        "path": "my/directory",
        "tracking-ref": "custom/branch",
        "authentication-method": git.AuthenticationMethodEnum.SSH.value,
        "secret-ssh-private-key": ssh_private_key_secret.id,
        "secret-ssh-passphrase": ssh_passphrase_secret.id,
        "ssh-strict-host-key-checking": "false",
        "ssh-port": "2222",
    }


@pytest.fixture(scope="function")
def credentials_data(personal_access_token_secret):
    return {
        "repository-url": "https://github.com/org/repo",
        "path": "my/directory",
        "tracking-ref": "custom/branch",
        "authentication-method": git.AuthenticationMethodEnum.CREDENTIALS.value,
        "credentials-username": "custom-user",
        "secret-credentials-personal-access-token": personal_access_token_secret.id,
    }


@pytest.fixture
def ssh_provider_model(ssh_private_key_secret):
    return git.GitProviderModel.model_validate(
        {
            "repository_url": "https://github.com/org/repo",
            "path": "my/directory",
            "tracking_ref": "custom/branch",
            "authentication_method": git.AuthenticationMethodEnum.SSH.value,
            "ssh_private_key": ssh_private_key_secret.latest_content[constants.SSH_PRIVATE_KEY],
            "secret_ssh_private_key": ssh_private_key_secret.id,
            "ssh_strict_host_key_checking": False,
            "request_id": "fixed_request_id",
        }
    )


@pytest.fixture
def ssh_provider_model_with_passphrase_and_port(ssh_private_key_secret, ssh_passphrase_secret):
    return git.GitProviderModel.model_validate(
        {
            "repository_url": "https://github.com/org/repo",
            "path": "my/directory",
            "tracking_ref": "custom/branch",
            "authentication_method": git.AuthenticationMethodEnum.SSH.value,
            "ssh_private_key": ssh_private_key_secret.latest_content[constants.SSH_PRIVATE_KEY],
            "secret_ssh_private_key": ssh_private_key_secret.id,
            "ssh_passphrase": ssh_passphrase_secret.latest_content[constants.SSH_PASSPHRASE],
            "secret_ssh_passphrase": ssh_passphrase_secret.id,
            "ssh_strict_host_key_checking": False,
            "ssh_port": 2222,
            "request_id": "fixed_request_id",
        }
    )


@pytest.fixture(scope="function")
def credentials_provider_model(personal_access_token_secret):
    return git.GitProviderModel.model_validate(
        {
            "repository_url": "https://github.com/org/repo",
            "path": "my/directory",
            "tracking_ref": "custom/branch",
            "authentication_method": git.AuthenticationMethodEnum.CREDENTIALS.value,
            "credentials_username": "custom-user",
            "credentials_personal_access_token": personal_access_token_secret.tracked_content[
                constants.PERSONAL_ACCESS_TOKEN
            ],
            "secret_credentials_personal_access_token": personal_access_token_secret.id,
            "request_id": "fixed_request_id",
        }
    )


@pytest.fixture(scope="function")
def empty_git_relation():
    return ops.testing.Relation(GIT_RELATION_ENDPOINT)


@pytest.fixture(scope="function")
def state_with_credentials(empty_git_relation, personal_access_token_secret):
    return ops.testing.State(
        leader=True,
        relations=[empty_git_relation],
        secrets=[personal_access_token_secret],
        config={
            constants.REPOSITORY_URL_CONFIG: "https://github.com/org/repo",
            constants.PATH_CONFIG: "my/directory",
            constants.TRACKING_REF_CONFIG: "custom/branch",
            constants.AUTHENTICATION_METHOD_CONFIG: "credentials",
            constants.CREDENTIALS_USERNAME_CONFIG: "custom-user",
            constants.CREDENTIALS_PERSONAL_ACCESS_TOKEN_SECRET_CONFIG: personal_access_token_secret.id,  # noqa: E501
        },
    )


@pytest.fixture(scope="function")
def state_with_ssh(empty_git_relation, ssh_private_key_secret):
    return ops.testing.State(
        leader=True,
        relations=[empty_git_relation],
        secrets=[ssh_private_key_secret],
        config={
            constants.REPOSITORY_URL_CONFIG: "https://github.com/org/repo",
            constants.PATH_CONFIG: "my/directory",
            constants.TRACKING_REF_CONFIG: "custom/branch",
            constants.AUTHENTICATION_METHOD_CONFIG: "ssh",
            constants.SSH_PRIVATE_KEY_SECRET_CONFIG: ssh_private_key_secret.id,
            constants.SSH_STRICT_HOST_KEY_CHECKING_CONFIG: False,
        },
    )


@pytest.fixture(scope="function")
def state_with_ssh_passphrase_and_port(
    empty_git_relation, ssh_private_key_secret, ssh_passphrase_secret
):
    return ops.testing.State(
        leader=True,
        relations=[empty_git_relation],
        secrets=[ssh_private_key_secret, ssh_passphrase_secret],
        config={
            constants.REPOSITORY_URL_CONFIG: "https://github.com/org/repo",
            constants.PATH_CONFIG: "my/directory",
            constants.TRACKING_REF_CONFIG: "custom/branch",
            constants.AUTHENTICATION_METHOD_CONFIG: "ssh",
            constants.SSH_PRIVATE_KEY_SECRET_CONFIG: ssh_private_key_secret.id,
            constants.SSH_PASSPHRASE_SECRET_CONFIG: ssh_passphrase_secret.id,
            constants.SSH_STRICT_HOST_KEY_CHECKING_CONFIG: False,
            constants.SSH_PORT_CONFIG: 2222,
        },
    )
