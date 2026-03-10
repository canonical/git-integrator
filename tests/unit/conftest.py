# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import charms.git_integrator.v0.git as git
import ops.testing
import pytest

from charm import GitIntegratorCharm

GIT_RELATION_ENDPOINT = "git"


@pytest.fixture
def context():
    return ops.testing.Context(charm_type=GitIntegratorCharm)


@pytest.fixture(scope="function")
def ssh_private_key_secret():
    return ops.testing.Secret(
        {
            "ssh-private-key": "custom-ssh-private-key",
        },
    )


@pytest.fixture(scope="function")
def personal_access_token_secret():
    return ops.testing.Secret(
        {
            "personal-access-token": "custom-personal-access-token",
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
def credentials_data(personal_access_token_secret):
    return {
        "repository-url": "https://github.com/org/repo",
        "path": "my/directory",
        "tracking-ref": "custom/branch",
        "authentication-method": git.AuthenticationMethodEnum.CREDENTIALS.value,
        "username": "custom-user",
        "secret-personal-access-token": personal_access_token_secret.id,
    }


SSH_GIT_CONNECTION_INFORMATION = sorted(
    {
        "repository_url": "https://github.com/org/repo",
        "path": "my/directory",
        "tracking_ref": "custom/branch",
        "authentication_method": git.AuthenticationMethodEnum.SSH.value,
        "ssh": {
            "private_key": "custom-ssh-private-key",
            "strict_host_key_checking": False,
        },
    }
)


CREDENTIALS_GIT_CONNECTION_INFORMATION = sorted(
    {
        "repository_url": "https://github.com/org/repo",
        "path": "my/directory",
        "tracking_ref": "custom/branch",
        "authentication_method": git.AuthenticationMethodEnum.CREDENTIALS.value,
        "credentials": {
            "username": "custom-user",
            "personal_access_token": "custom-persona-access-token",
        },
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
            "repository_url": "https://github.com/org/repo",
            "path": "my/directory",
            "tracking_ref": "custom/branch",
            "authentication_method": "credentials",
            "credentials_username": "custom-user",
            "credentials_personal_access_token_secret": personal_access_token_secret.id,
        },
    )


@pytest.fixture(scope="function")
def state_with_ssh(empty_git_relation, ssh_private_key_secret):
    return ops.testing.State(
        leader=True,
        relations=[empty_git_relation],
        secrets=[ssh_private_key_secret],
        config={
            "repository_url": "https://github.com/org/repo",
            "path": "my/directory",
            "tracking_ref": "custom/branch",
            "authentication_method": "ssh",
            "ssh_private_key_secret": ssh_private_key_secret.id,
            "ssh_strict_host_key_checking": True,
        },
    )
