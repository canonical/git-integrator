# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
#
# To learn more about testing, see https://documentation.ubuntu.com/ops/latest/explanation/testing/

import dataclasses
import unittest.mock

import ops
import pytest
from conftest import (
    GIT_RELATION_ENDPOINT,
)

import constants


def test_non_leader_unit(context, state_with_credentials):
    """Test no-op of non leader unit."""
    state = dataclasses.replace(state_with_credentials, leader=False)

    unit_status_before = state.unit_status

    state_out = context.run(context.on.start(), state)

    assert state_out.unit_status == unit_status_before


def test_missing_git_relation(context, state_with_credentials):
    """Test to ensure errorless execution when git relation is missing."""
    state = dataclasses.replace(state_with_credentials, relations=[])

    state_out = context.run(context.on.config_changed(), state)

    assert state_out.unit_status == ops.ActiveStatus()


def test_missing_config(context, state_with_credentials):
    """Test missing config."""
    state_with_empty_config = dataclasses.replace(state_with_credentials, config={})

    state_out = context.run(context.on.start(), state_with_empty_config)

    assert state_out.unit_status == ops.BlockedStatus(constants.WAITING_FOR_CONFIGURATION_MESSAGE)
    assert state_out.get_relations(GIT_RELATION_ENDPOINT)[0].local_app_data == {}


def test_missing_repository_url_config(context, state_with_credentials):
    """Test missing repository url config."""
    config = state_with_credentials.config.copy()
    config.pop(constants.REPOSITORY_URL_CONFIG)

    state = dataclasses.replace(state_with_credentials, config=config)

    state_out = context.run(context.on.config_changed(), state)

    assert state_out.unit_status == ops.BlockedStatus(constants.MISSING_REPOSITORY_URL_MESSAGE)
    assert state_out.get_relations(GIT_RELATION_ENDPOINT)[0].local_app_data == {}


def test_invalid_authentication_method(context, state_with_credentials):
    """Test invalid value for authentication_method config."""
    config = state_with_credentials.config.copy()
    config[constants.AUTHENTICATION_METHOD_CONFIG] = "invalid"

    state = dataclasses.replace(state_with_credentials, config=config)

    state_out = context.run(context.on.config_changed(), state)

    assert state_out.unit_status == ops.BlockedStatus(constants.INVALID_AUTHENTICAITON_MESSAGE)


def test_missing_username(context, state_with_credentials):
    """Test missing username config."""
    config = state_with_credentials.config.copy()
    config.pop(constants.CREDENTIALS_USERNAME_CONFIG)

    state = dataclasses.replace(state_with_credentials, config=config)

    state_out = context.run(context.on.config_changed(), state)

    assert state_out.unit_status == ops.BlockedStatus(constants.MISSING_USERNAME_MESSAGE)
    assert state_out.get_relations(GIT_RELATION_ENDPOINT)[0].local_app_data == {}


def test_missing_personal_access_token_secret_config(context, state_with_credentials):
    """Test missing personal access token secret config."""
    config = state_with_credentials.config.copy()
    config.pop(constants.CREDENTIALS_PERSONAL_ACCESS_TOKEN_SECRET_CONFIG)

    state = dataclasses.replace(state_with_credentials, config=config)

    state_out = context.run(context.on.config_changed(), state)

    assert state_out.unit_status == ops.BlockedStatus(
        constants.MISSING_PERSONAL_ACCESS_TOKEN_SECRET_MESSAGE
    )
    assert state_out.get_relations(GIT_RELATION_ENDPOINT)[0].local_app_data == {}


@pytest.mark.parametrize("exception", [ops.SecretNotFoundError, ops.ModelError])
def test_invalid_personal_access_token_secret(context, state_with_credentials, exception):
    """Test error while accessing the personal access token secret."""
    with unittest.mock.patch("ops.Model.get_secret", side_effect=exception):
        state_out = context.run(context.on.config_changed(), state_with_credentials)

        assert state_out.unit_status == ops.BlockedStatus(
            constants.INVALID_PERSONAL_ACCESS_TOKEN_SECRET_MESSAGE
        )
        assert state_out.get_relations(GIT_RELATION_ENDPOINT)[0].local_app_data == {}


def test_missing_personal_access_token_in_secret(context, state_with_credentials):
    """Test for missing personal access token in provided secret."""
    empty_secret = ops.testing.Secret({})
    config = state_with_credentials.config.copy()
    config[constants.CREDENTIALS_PERSONAL_ACCESS_TOKEN_SECRET_CONFIG] = empty_secret.id

    state = dataclasses.replace(state_with_credentials, secrets=[empty_secret], config=config)

    state_out = context.run(context.on.config_changed(), state)

    assert state_out.unit_status == ops.BlockedStatus(
        constants.MISSING_PERSONAL_ACCESS_TOKEN_IN_SECRET_MESSAGE
    )
    assert state_out.get_relations(GIT_RELATION_ENDPOINT)[0].local_app_data == {}


def test_missing_ssh_private_key_secret_config(context, state_with_ssh):
    """Test missing SSH private key secret config."""
    config = state_with_ssh.config.copy()
    config.pop(constants.SSH_PRIVATE_KEY_SECRET_CONFIG)

    state = dataclasses.replace(state_with_ssh, config=config)

    state_out = context.run(context.on.config_changed(), state)

    assert state_out.unit_status == ops.BlockedStatus(
        constants.MISSING_SSH_PRIVATE_KEY_SECRET_MESSAGE
    )
    assert state_out.get_relations(GIT_RELATION_ENDPOINT)[0].local_app_data == {}


@pytest.mark.parametrize("exception", [ops.SecretNotFoundError, ops.ModelError])
def test_invalid_ssh_private_key_secret(context, state_with_ssh, exception):
    """Test error while accessing the ssh private key secret."""
    with unittest.mock.patch("ops.Model.get_secret", side_effect=exception):
        state_out = context.run(context.on.config_changed(), state_with_ssh)

        assert state_out.unit_status == ops.BlockedStatus(
            constants.INVALID_SSH_PRIVATE_KEY_MESSAGE
        )
        assert state_out.get_relations(GIT_RELATION_ENDPOINT)[0].local_app_data == {}


def test_missing_ssh_private_key_in_secret(context, state_with_ssh):
    """Test for missing personal access token in provided secret."""
    empty_secret = ops.testing.Secret({})
    config = state_with_ssh.config.copy()
    config[constants.SSH_PRIVATE_KEY_SECRET_CONFIG] = empty_secret.id

    state = dataclasses.replace(state_with_ssh, secrets=[empty_secret], config=config)

    state_out = context.run(context.on.config_changed(), state)

    assert state_out.unit_status == ops.BlockedStatus(
        constants.MISSING_SSH_PRIVATE_KEY_IN_SECRET_MESSAGE
    )
    assert state_out.get_relations(GIT_RELATION_ENDPOINT)[0].local_app_data == {}


def test_credentials(context, state_with_credentials, credentials_data):
    """Test setting valid config for credentials."""
    state_out = context.run(context.on.config_changed(), state_with_credentials)

    credentials_data.pop("secret-personal-access-token")

    assert state_out.unit_status == ops.ActiveStatus()
    assert sorted(
        {
            key: value
            for key, value in state_out.get_relations(GIT_RELATION_ENDPOINT)[
                0
            ].local_app_data.items()
            if key != "secret-personal-access-token"
        }
    ) == sorted(credentials_data)

    updated_config = state_out.config.copy()
    updated_config[constants.REPOSITORY_URL_CONFIG] = "another-url"

    state_with_updated_config = dataclasses.replace(state_out, config=updated_config)

    state_out = context.run(context.on.config_changed(), state_with_updated_config)

    assert state_out.unit_status == ops.ActiveStatus()
    assert (
        state_out.get_relations(GIT_RELATION_ENDPOINT)[0].local_app_data["repository-url"]
        == "another-url"
    )


def test_ssh(context, state_with_ssh, ssh_data):
    """Test setting valid config for ssh."""
    state_out = context.run(context.on.config_changed(), state_with_ssh)

    assert state_out.unit_status == ops.ActiveStatus()
    assert sorted(state_out.get_relations(GIT_RELATION_ENDPOINT)[0].local_app_data) == sorted(
        ssh_data
    )

    updated_config = {
        **state_out.config,
        constants.PATH_CONFIG: "new/path",
        constants.TRACKING_REF_CONFIG: "new/branch",
        constants.SSH_STRICT_HOST_KEY_CHECKING_CONFIG: False,
    }

    state_with_updated_config = dataclasses.replace(state_out, config=updated_config)

    state_out = context.run(context.on.config_changed(), state_with_updated_config)

    assert state_out.unit_status == ops.ActiveStatus()

    relation_data = state_out.get_relations(GIT_RELATION_ENDPOINT)[0].local_app_data
    assert relation_data["path"] == "new/path"
    assert relation_data["tracking-ref"] == "new/branch"
    assert relation_data["ssh-strict-host-key-checking"] == "false"
