# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
#
# To learn more about testing, see https://documentation.ubuntu.com/ops/latest/explanation/testing/

"""Tests for the Git Integrator charm lib."""

import dataclasses
import logging
import unittest.mock

import charms.git_integrator.v0.git as git
import ops
import ops.testing
import pytest

logger = logging.getLogger(__name__)

GIT_RELATION_INTERFACE = "git"


class GitRequirerCharm(ops.CharmBase):
    """Mock requirer charm to enable testing git integrator charm lib."""

    def __init__(self, *args):
        super().__init__(*args)

        self.requirer = git.GitRequires(
            self,
            GIT_RELATION_INTERFACE,
            self.reconcile,
        )

        self.framework.observe(self.on.start, self.reconcile)

    def reconcile(self, event) -> None:
        logger.info(f"§Requirer reacting to event: {type(event)}")


class GitIntegratorCharm(ops.CharmBase):
    """Mock git integrator to enable testing git integrator charm lib."""

    def __init__(self, *args):
        super().__init__(*args)

        self.provider = git.GitProvides(
            self,
            GIT_RELATION_INTERFACE,
            self.reconcile,
        )

        self.framework.observe(self.on.start, self.reconcile)

    def reconcile(self, event) -> None:
        logger.info(f"§Provider reacting to event: {type(event)}")


@pytest.fixture(scope="function")
def requirer_context():
    return ops.testing.Context(
        charm_type=GitRequirerCharm,
        meta={
            "name": "git-requirer",
            "requires": {
                GIT_RELATION_INTERFACE: {
                    "interface": GIT_RELATION_INTERFACE,
                    "limit": 1,
                },
            },
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
def credentials_data(personal_access_token_secret):
    return {
        "repository-url": "https://github.com/org/repo",
        "path": "my/directory",
        "tracking-ref": "custom/branch",
        "authentication-method": git.AuthenticationMethodEnum.CREDENTIALS,
        "username": "custom-user",
        "secret-personal-access-token": personal_access_token_secret.id,
    }


@pytest.fixture(scope="function")
def requirer_credentials_relation(credentials_data):
    return ops.testing.Relation(
        "git",
        interface="git",
        remote_app_data=credentials_data,
    )


@pytest.fixture(scope="function")
def ssh_private_key_secret():
    return ops.testing.Secret(
        {
            "ssh-private-key": "custom-ssh-private-key",
        },
    )


@pytest.fixture(scope="function")
def ssh_data(ssh_private_key_secret):
    return {
        "repository-url": "https://github.com/org/repo",
        "path": "my/directory",
        "tracking-ref": "custom/branch",
        "authentication-method": git.AuthenticationMethodEnum.SSH,
        "secret-ssh-private-key": ssh_private_key_secret.id,
        "ssh-strict-host-key-checking": "false",
    }


@pytest.fixture(scope="function")
def requirer_ssh_relation(ssh_data):
    return ops.testing.Relation(
        "git",
        interface="git",
        remote_app_data=ssh_data,
    )


@pytest.fixture(scope="function")
def requirer_credentials_state(requirer_credentials_relation, personal_access_token_secret):
    return ops.testing.State(
        leader=True,
        relations=[requirer_credentials_relation],
        secrets=[personal_access_token_secret],
    )


@pytest.fixture(scope="function")
def requirer_ssh_state(requirer_ssh_relation, ssh_private_key_secret):
    return ops.testing.State(
        leader=True,
        relations=[requirer_ssh_relation],
        secrets=[ssh_private_key_secret],
    )


@pytest.fixture(scope="function")
def provider_context():
    return ops.testing.Context(
        charm_type=GitIntegratorCharm,
        meta={
            "name": "git-integrator",
            "provides": {
                GIT_RELATION_INTERFACE: {
                    "interface": GIT_RELATION_INTERFACE,
                    "limit": 1,
                },
            },
        },
    )


@pytest.fixture(scope="function")
def provider_git_relation(credentials_data):
    return ops.testing.Relation(
        "git",
        interface="git",
        local_app_data=credentials_data,
    )


@pytest.fixture(scope="function")
def provider_state(provider_git_relation, personal_access_token_secret):
    return ops.testing.State(
        leader=True,
        relations=[provider_git_relation],
        secrets=[personal_access_token_secret],
    )


class TestGitRequires:
    def get_juju_log_line(self, log_level: str, event: ops.EventBase):
        return ops.testing.JujuLogLine(
            level=log_level, message=f"§Requirer reacting to event: {event}"
        )

    def test_on(self, requirer_context, requirer_credentials_state):
        """Ensure that custom events are accessible."""
        with requirer_context(requirer_context.on.start(), requirer_credentials_state) as manager:
            assert isinstance(manager.charm.requirer.on, ops.CharmEvents)

            assert hasattr(manager.charm.requirer.on, "git_connection_information_updated")

    @pytest.mark.parametrize("state", ["requirer_credentials_state", "requirer_ssh_state"])
    def test_missing_git_relation(self, request, requirer_context, state):
        """Ensure safe method/property access when git relation is missing."""
        state_with_missing_relation = dataclasses.replace(
            request.getfixturevalue(state), relations=[], secrets=[]
        )

        with requirer_context(requirer_context.on.start(), state_with_missing_relation) as manager:
            manager.run()

            assert self.get_juju_log_line("INFO", ops.StartEvent) in requirer_context.juju_log

            assert manager.charm.requirer.get_git_connection_information() == {}
            assert manager.charm.requirer.repository_url is None
            assert manager.charm.requirer.path is None
            assert manager.charm.requirer.tracking_ref is None
            assert manager.charm.requirer.authentication_method is None
            assert manager.charm.requirer.credentials == {}
            assert manager.charm.requirer.ssh_private_key is None
            assert manager.charm.requirer.strict_host_key_checking is None

    def test_credentials(
        self,
        requirer_context,
        requirer_credentials_state,
        requirer_credentials_relation,
        credentials_data,
    ):
        """Ensure valid access to git connection with credentials."""
        with requirer_context(
            requirer_context.on.relation_changed(requirer_credentials_relation),
            requirer_credentials_state,
        ) as manager:
            manager.run()

            assert (
                self.get_juju_log_line("INFO", git.GitConnectionInformationUpdatedEvent)
                in requirer_context.juju_log
            )

            credentials_data.pop("secret-personal-access-token")
            credentials_data["personal-access-token"] = "custom-personal-access-token"

            assert manager.charm.requirer.get_git_connection_information() == credentials_data
            assert manager.charm.requirer.repository_url == "https://github.com/org/repo"
            assert manager.charm.requirer.path == "my/directory"
            assert manager.charm.requirer.tracking_ref == "custom/branch"
            assert (
                manager.charm.requirer.authentication_method
                is git.AuthenticationMethodEnum.CREDENTIALS
            )
            assert manager.charm.requirer.credentials == {
                "username": "custom-user",
                "personal_access_token": "custom-personal-access-token",
            }
            assert manager.charm.requirer.ssh_private_key is None
            assert manager.charm.requirer.strict_host_key_checking is None

    def test_ssh_private_key(
        self, requirer_context, requirer_ssh_state, requirer_ssh_relation, ssh_data
    ):
        """Ensure valid access to git connection with ssh key."""
        with requirer_context(
            requirer_context.on.relation_changed(requirer_ssh_relation), requirer_ssh_state
        ) as manager:
            manager.run()

            assert (
                self.get_juju_log_line("INFO", git.GitConnectionInformationUpdatedEvent)
                in requirer_context.juju_log
            )

            ssh_data.pop("secret-ssh-private-key")
            ssh_data["ssh-private-key"] = "custom-ssh-private-key"
            ssh_data["ssh-strict-host-key-checking"] = False

            assert manager.charm.requirer.get_git_connection_information() == ssh_data
            assert manager.charm.requirer.repository_url == "https://github.com/org/repo"
            assert manager.charm.requirer.path == "my/directory"
            assert manager.charm.requirer.tracking_ref == "custom/branch"
            assert manager.charm.requirer.authentication_method is git.AuthenticationMethodEnum.SSH
            assert manager.charm.requirer.credentials == {}
            assert manager.charm.requirer.ssh_private_key == "custom-ssh-private-key"
            assert (
                isinstance(manager.charm.requirer.strict_host_key_checking, bool)
                and not manager.charm.requirer.strict_host_key_checking
            )

    def test_ssh_private_key_secret_changed(
        self,
        requirer_context,
        requirer_ssh_state,
        requirer_ssh_relation,
        ssh_data,
        ssh_private_key_secret,
    ):
        """Ensure valid access to git connection with ssh key when secret changed."""
        requirer_context.run(
            requirer_context.on.relation_changed(requirer_ssh_relation), requirer_ssh_state
        )

        updated_secret = ops.testing.Secret(
            id=ssh_private_key_secret.id,
            tracked_content={"ssh-private-key": "updated-ssh-private-key"},
        )
        updated_requirer_ssh_state = dataclasses.replace(
            requirer_ssh_state, secrets=[updated_secret]
        )

        with requirer_context(
            requirer_context.on.secret_changed(updated_secret), updated_requirer_ssh_state
        ) as manager:
            manager.run()

            assert (
                self.get_juju_log_line("INFO", git.GitConnectionInformationUpdatedEvent)
                in requirer_context.juju_log
            )

            ssh_data.pop("secret-ssh-private-key")
            ssh_data["ssh-private-key"] = "updated-ssh-private-key"
            ssh_data["ssh-strict-host-key-checking"] = False

            assert manager.charm.requirer.get_git_connection_information() == ssh_data
            assert manager.charm.requirer.repository_url == "https://github.com/org/repo"
            assert manager.charm.requirer.path == "my/directory"
            assert manager.charm.requirer.tracking_ref == "custom/branch"
            assert manager.charm.requirer.authentication_method is git.AuthenticationMethodEnum.SSH
            assert manager.charm.requirer.credentials == {}
            assert manager.charm.requirer.ssh_private_key == "updated-ssh-private-key"
            assert (
                isinstance(manager.charm.requirer.strict_host_key_checking, bool)
                and not manager.charm.requirer.strict_host_key_checking
            )

    def test_git_relation_breaking(
        self, requirer_context, requirer_ssh_state, requirer_ssh_relation
    ):
        """Ensure reconciler callback invoked upon relation breaking."""
        with requirer_context(
            requirer_context.on.relation_broken(requirer_ssh_relation), requirer_ssh_state
        ) as manager:
            manager.run()

            assert (
                self.get_juju_log_line("INFO", ops.RelationBrokenEvent)
                in requirer_context.juju_log
            )

            assert manager.charm.requirer.get_git_connection_information() == {}
            assert manager.charm.requirer.repository_url is None
            assert manager.charm.requirer.path is None
            assert manager.charm.requirer.tracking_ref is None
            assert manager.charm.requirer.authentication_method is None
            assert manager.charm.requirer.credentials == {}
            assert manager.charm.requirer.ssh_private_key is None
            assert manager.charm.requirer.strict_host_key_checking is None


class TestGitProvides:
    def get_juju_log_line(self, log_level: str, event: ops.EventBase):
        return ops.testing.JujuLogLine(
            level=log_level, message=f"§Provider reacting to event: {event}"
        )

    def test_missing_git_relation(self, provider_context, provider_state):
        """Ensure safe GitProvides instantiation when git relation is missing."""
        state_with_missing_relation = dataclasses.replace(provider_state, relations=[], secrets=[])

        with provider_context(provider_context.on.start(), state_with_missing_relation) as manager:
            manager.run()

            assert self.get_juju_log_line("INFO", ops.StartEvent) in provider_context.juju_log

            # should no-op without errors
            manager.charm.provider.update_git_connection_info({"path": "new/path"})

    def test_update_git_connection_info(
        self, provider_context, provider_state, provider_git_relation
    ):
        """Ensure correct partial update of git connection info."""
        with provider_context(
            provider_context.on.relation_changed(provider_git_relation), provider_state
        ) as manager:
            manager.run()

            assert (
                provider_state.get_relation(provider_git_relation.id).local_app_data.get("path")
                == "my/directory"
            )

            manager.charm.provider.update_git_connection_info({"path": "new/path"})

            assert (
                manager.charm.model.get_relation(GIT_RELATION_INTERFACE)
                .data[manager.charm.app]
                .get("path")
                == "new/path"
            )

            secret_id = provider_state.get_relation(provider_git_relation.id).local_app_data[
                "secret-personal-access-token"
            ]
            secret = manager.charm.model.get_secret(id=secret_id)

            assert (
                secret.get_content().get("personal-access-token") == "custom-personal-access-token"
            )

            with unittest.mock.patch(
                "charms.data_platform_libs.v1.data_interfaces.CachedSecret.set_content"
            ) as mock_set_content:
                manager.charm.provider.update_git_connection_info(
                    {"personal_access_token": "new-personal-access-token"}
                )

                mock_set_content.assert_called_with(
                    {"personal-access-token": "new-personal-access-token"}
                )

    def test_git_relation_broken(
        self, provider_context, provider_state, provider_git_relation, credentials_data
    ):
        """Ensure invoke of reconciler callback on git integratorrelation broken."""
        with provider_context(
            provider_context.on.relation_broken(provider_git_relation), provider_state
        ) as manager:
            manager.run()

            assert (
                self.get_juju_log_line("INFO", ops.RelationBrokenEvent)
                in provider_context.juju_log
            )
