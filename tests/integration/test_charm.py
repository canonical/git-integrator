# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

import copy
import json
import logging
import pathlib

import charms.git_integrator.v0.git as git
import jubilant

import constants

logger = logging.getLogger(__name__)

GIT_ENDPOINT = "git"

MINIMAL_CONFIG = {
    constants.REPOSITORY_URL_CONFIG: "url0",
}

# Missing personal_access_token_secret config
CREDENTIALS_CONFIG = {
    constants.REPOSITORY_URL_CONFIG: "url1",
    constants.PATH_CONFIG: "path1",
    constants.TRACKING_REF_CONFIG: "ref1",
    constants.AUTHENTICATION_METHOD_CONFIG: "credentials",
    constants.CREDENTIALS_USERNAME_CONFIG: "user1",
}

# Missing ssh_private_key_secret config
SSH_CONFIG = {
    constants.REPOSITORY_URL_CONFIG: "url2",
    constants.PATH_CONFIG: "path2",
    constants.TRACKING_REF_CONFIG: "ref2",
    constants.AUTHENTICATION_METHOD_CONFIG: "ssh",
    constants.SSH_STRICT_HOST_KEY_CHECKING_CONFIG: True,
}

EXPECTED_GIT_CONNECTION_INFORMATION_MINIMAL = {
    "repository_url": "url0",
}

EXPECTED_GIT_CONNECTION_INFORMATION_CREDENTIALS = {
    "repository_url": "url1",
    "authentication_method": git.AuthenticationMethodEnum.CREDENTIALS.value,
    "path": "path1",
    "tracking_ref": "ref1",
    "credentials": {
        "username": "user1",
        "personal_access_token": "token1",
    },
}

EXPECTED_GIT_CONNECTION_INFORMATION_SSH = {
    "repository_url": "url2",
    "authentication_method": git.AuthenticationMethodEnum.SSH.value,
    "path": "path2",
    "tracking_ref": "ref2",
    "ssh": {
        "private_key": "key2",
        "strict_host_key_checking": True,
    },
}


def test_deploy(
    juju: jubilant.Juju,
    charm: pathlib.Path,
    mock_requirer_charm: pathlib.Path,
    personal_access_token_secret: str,
    ssh_private_key_secret: str,
):
    """Deploy multiple git integrator charms and multiple mock requirer charm."""
    logger.info("Deploying 3 git integrator charms with different configs")

    for index, config in enumerate([MINIMAL_CONFIG, CREDENTIALS_CONFIG, SSH_CONFIG]):
        juju.deploy(
            charm.resolve(),
            app=f"git-integrator{index}",
            config=config,
        )

        juju.grant_secret(personal_access_token_secret, f"git-integrator{index}")
        juju.grant_secret(ssh_private_key_secret, f"git-integrator{index}")

        juju.config(
            f"git-integrator{index}",
            {
                constants.CREDENTIALS_PERSONAL_ACCESS_TOKEN_SECRET_CONFIG: personal_access_token_secret,  # noqa: E501
                constants.SSH_PRIVATE_KEY_SECRET_CONFIG: ssh_private_key_secret,
            },
        )

    logger.info("Deploy 3 mock git requirer charms and integrating them with git integrators")

    for i in range(3):
        juju.deploy(mock_requirer_charm.resolve(), app=f"git-requirer{i}")

        for j in range(3):
            juju.integrate(f"git-integrator{j}:{GIT_ENDPOINT}", f"git-requirer{i}:{GIT_ENDPOINT}")

    logger.info("Waiting for all applications to go into active status")

    juju.wait(jubilant.all_active)


def test_git_connection_information(juju: jubilant.Juju):
    """Test proper propagation of git connection information to requirers."""
    logger.info("Ensuring proper propagation to all related requirers charms")

    for i in range(2):
        action = juju.run(f"git-requirer{i}/0", "get-git-connection-information")

        assert json.loads(action.results["git-connection-information"]) == {
            "git-integrator0": EXPECTED_GIT_CONNECTION_INFORMATION_MINIMAL,
            "git-integrator1": EXPECTED_GIT_CONNECTION_INFORMATION_CREDENTIALS,
            "git-integrator2": EXPECTED_GIT_CONNECTION_INFORMATION_SSH,
        }


def test_proper_propagation_upon_config_change(juju: jubilant.Juju):
    """Test proper propagation of git connection information to requirers when config changed."""
    logger.info("Updating config of one git integrator charm")

    juju.config("git-integrator0", {"path": "path0"})

    logger.info("Waiting for all charms to be active/idle (update propagation complete)")

    juju.wait(jubilant.all_active)
    juju.wait(jubilant.all_agents_idle)

    logger.info("Checking proper propagation of update")

    for i in range(2):
        action = juju.run(f"git-requirer{i}/0", "get-git-connection-information")

        assert json.loads(action.results["git-connection-information"]) == {
            "git-integrator0": {
                **EXPECTED_GIT_CONNECTION_INFORMATION_MINIMAL,
                "path": "path0",
            },
            "git-integrator1": EXPECTED_GIT_CONNECTION_INFORMATION_CREDENTIALS,
            "git-integrator2": EXPECTED_GIT_CONNECTION_INFORMATION_SSH,
        }

    logger.info("Revert config of the same git integrator charm")

    juju.config("git-integrator0", reset=["path"])

    logger.info("Waiting for all charms to be active/idle (update propagation complete)")

    juju.wait(jubilant.all_active)
    juju.wait(jubilant.all_agents_idle)

    logger.info("Checking proper revert of update")

    for i in range(2):
        action = juju.run(f"git-requirer{i}/0", "get-git-connection-information")

        assert json.loads(action.results["git-connection-information"]) == {
            "git-integrator0": EXPECTED_GIT_CONNECTION_INFORMATION_MINIMAL,
            "git-integrator1": EXPECTED_GIT_CONNECTION_INFORMATION_CREDENTIALS,
            "git-integrator2": EXPECTED_GIT_CONNECTION_INFORMATION_SSH,
        }


def test_consistency_with_one_relation_removed(juju: jubilant.Juju):
    """Test expected git connection information availability when only one relation removed."""
    logger.info("Removing relation git-integrator0 <-> git-requirer0")

    juju.remove_relation(f"git-integrator0:{GIT_ENDPOINT}", f"git-requirer0:{GIT_ENDPOINT}")

    logger.info("Waiting for all charms to be active/idle (removal effects complete)")

    juju.wait(jubilant.all_active)
    juju.wait(jubilant.all_agents_idle)

    logger.info("Checking proper access to git connection information")

    expected_git_connection_information = {
        "git-integrator0": EXPECTED_GIT_CONNECTION_INFORMATION_MINIMAL,
        "git-integrator1": EXPECTED_GIT_CONNECTION_INFORMATION_CREDENTIALS,
        "git-integrator2": EXPECTED_GIT_CONNECTION_INFORMATION_SSH,
    }

    for i in range(2):
        action = juju.run(f"git-requirer{i}/0", "get-git-connection-information")

        expected_action_results = copy.deepcopy(expected_git_connection_information)
        if i == 0:
            del expected_action_results["git-integrator0"]

        assert json.loads(action.results["git-connection-information"]) == expected_action_results

    logger.info("Adding relation git-integrator0 <-> git-requirer0")

    juju.integrate(f"git-integrator0:{GIT_ENDPOINT}", f"git-requirer0:{GIT_ENDPOINT}")

    logger.info("Waiting for all charms to be active/idle (removal effects complete)")

    juju.wait(jubilant.all_active)
    juju.wait(jubilant.all_agents_idle)

    logger.info("Checking proper access to git connection information")

    for i in range(2):
        action = juju.run(f"git-requirer{i}/0", "get-git-connection-information")

        assert json.loads(action.results["git-connection-information"]) == expected_action_results
