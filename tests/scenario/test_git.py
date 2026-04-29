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
def requirer_credentials_relation(credentials_data):
    return ops.testing.Relation(
        "git",
        interface="git",
        remote_app_data=credentials_data,
    )


@pytest.fixture(scope="function")
def requirer_ssh_relation(ssh_data):
    return ops.testing.Relation(
        "git",
        interface="git",
        remote_app_data=ssh_data,
    )


@pytest.fixture(scope="function")
def requirer_state(
    requirer_credentials_relation,
    personal_access_token_secret,
    requirer_ssh_relation,
    ssh_private_key_secret,
):
    return ops.testing.State(
        leader=True,
        relations=[requirer_credentials_relation, requirer_ssh_relation],
        secrets=[personal_access_token_secret, ssh_private_key_secret],
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

    def test_on(self, requirer_context, requirer_state):
        """Ensure that custom events are accessible."""
        with requirer_context(requirer_context.on.start(), requirer_state) as manager:
            assert isinstance(manager.charm.requirer.on, ops.CharmEvents)

            assert hasattr(manager.charm.requirer.on, "git_connection_information_updated")

    def test_missing_git_relation(self, requirer_context, requirer_state):
        """Ensure safe method/property access when git relation is missing."""
        relation_ids = [relation.id for relation in requirer_state.relations]

        state_with_missing_relation = dataclasses.replace(requirer_state, relations=[], secrets=[])

        with requirer_context(requirer_context.on.start(), state_with_missing_relation) as manager:
            manager.run()

            assert self.get_juju_log_line("INFO", ops.StartEvent) in requirer_context.juju_log

            assert manager.charm.requirer.get_git_connection_information() == {}
            assert all(
                manager.charm.requirer.get_git_connection_information_for_relation(relation_id)
                is None
                for relation_id in relation_ids
            )

    def test_get_git_connection_information(
        self,
        requirer_context,
        requirer_state,
        requirer_credentials_relation,
        requirer_ssh_relation,
        credentials_provider_model,
        ssh_provider_model,
    ):
        """Ensure valid access to git connection."""
        with requirer_context(
            requirer_context.on.relation_changed(requirer_credentials_relation),
            requirer_state,
        ) as manager:
            manager.run()

            assert (
                self.get_juju_log_line("INFO", git.GitConnectionInformationUpdatedEvent)
                in requirer_context.juju_log
            )

            assert manager.charm.requirer.get_git_connection_information() == {
                requirer_credentials_relation.id: credentials_provider_model,
                requirer_ssh_relation.id: ssh_provider_model,
            }
            assert (
                manager.charm.requirer.get_git_connection_information_for_relation(
                    requirer_credentials_relation.id
                )
                == credentials_provider_model
            )
            assert (
                manager.charm.requirer.get_git_connection_information_for_relation(
                    requirer_ssh_relation.id
                )
                == ssh_provider_model
            )

    def test_ssh_passphrase_and_port_trigger_reconciler(
        self,
        requirer_context,
        requirer_credentials_relation,
        credentials_provider_model,
        ssh_private_key_secret,
        ssh_passphrase_secret,
        personal_access_token_secret,
        ssh_data_with_passphrase_and_port,
        ssh_provider_model_with_passphrase_and_port,
    ):
        """Ensure ssh_port and ssh_passphrase fields in relation data trigger the reconciler."""
        requirer_ssh_relation_with_extras = ops.testing.Relation(
            "git",
            interface="git",
            remote_app_data=ssh_data_with_passphrase_and_port,
        )
        requirer_state = ops.testing.State(
            leader=True,
            relations=[requirer_credentials_relation, requirer_ssh_relation_with_extras],
            secrets=[personal_access_token_secret, ssh_private_key_secret, ssh_passphrase_secret],
        )

        with requirer_context(
            requirer_context.on.relation_changed(requirer_ssh_relation_with_extras),
            requirer_state,
        ) as manager:
            manager.run()

            assert (
                self.get_juju_log_line("INFO", git.GitConnectionInformationUpdatedEvent)
                in requirer_context.juju_log
            )

            assert (
                manager.charm.requirer.get_git_connection_information_for_relation(
                    requirer_ssh_relation_with_extras.id
                )
                == ssh_provider_model_with_passphrase_and_port
            )

    def test_ssh_private_key_secret_changed(
        self,
        requirer_context,
        requirer_state,
        requirer_ssh_relation,
        requirer_credentials_relation,
        ssh_private_key_secret,
        personal_access_token_secret,
        credentials_provider_model,
        ssh_provider_model,
    ):
        """Ensure valid access to git connection with ssh key when secret changed."""
        requirer_context.run(
            requirer_context.on.relation_changed(requirer_ssh_relation), requirer_state
        )

        updated_secret = ops.testing.Secret(
            id=ssh_private_key_secret.id,
            tracked_content={"ssh-private-key": "updated-ssh-private-key"},
        )
        updated_requirer_state = dataclasses.replace(
            requirer_state, secrets=[updated_secret, personal_access_token_secret]
        )

        ssh_provider_model.ssh_private_key = "updated-ssh-private-key"

        with requirer_context(
            requirer_context.on.secret_changed(updated_secret), updated_requirer_state
        ) as manager:
            manager.run()

            assert (
                self.get_juju_log_line("INFO", git.GitConnectionInformationUpdatedEvent)
                in requirer_context.juju_log
            )
            assert manager.charm.requirer.get_git_connection_information() == {
                requirer_credentials_relation.id: credentials_provider_model,
                requirer_ssh_relation.id: ssh_provider_model,
            }
            assert (
                manager.charm.requirer.get_git_connection_information_for_relation(
                    requirer_credentials_relation.id
                )
                == credentials_provider_model
            )
            assert (
                manager.charm.requirer.get_git_connection_information_for_relation(
                    requirer_ssh_relation.id
                )
                == ssh_provider_model
            )

    def test_git_relation_breaking(
        self,
        requirer_context,
        requirer_state,
        requirer_ssh_relation,
        requirer_credentials_relation,
        credentials_provider_model,
    ):
        """Ensure reconciler callback invoked upon relation breaking."""
        with requirer_context(
            requirer_context.on.relation_broken(requirer_ssh_relation), requirer_state
        ) as manager:
            manager.run()

            assert (
                self.get_juju_log_line("INFO", ops.RelationBrokenEvent)
                in requirer_context.juju_log
            )

            assert manager.charm.requirer.get_git_connection_information() == {
                requirer_credentials_relation.id: credentials_provider_model,
            }


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
            manager.charm.provider.set_git_connection_info({"path": "new/path"})

    def test_set_git_connection_info_invalid(
        self, provider_context, provider_state, provider_git_relation
    ):
        """Ensure proper handling of invalid git connection info updates."""
        with provider_context(
            provider_context.on.relation_changed(provider_git_relation), provider_state
        ) as manager:
            manager.run()

            assert (
                provider_state.get_relation(provider_git_relation.id).local_app_data.get("path")
                == "my/directory"
            )

            with pytest.raises(ValueError, match="Invalid keys in provided connection info"):
                manager.charm.provider.set_git_connection_info({"invalid_key": "invalid_value"})

            with pytest.raises(ValueError, match="Prohibited fields in provided connection info"):
                manager.charm.provider.set_git_connection_info(
                    {"secret_credentials_personal_access_token": "random"}
                )

            with pytest.raises(
                ValueError, match="Missing required credentials fields in provided connection info"
            ):
                manager.charm.provider.set_git_connection_info(
                    {"authentication_method": git.AuthenticationMethodEnum.CREDENTIALS.value}
                )

            with pytest.raises(
                ValueError, match="Unexpected SSH fields in provided connection info"
            ):
                manager.charm.provider.set_git_connection_info(
                    {
                        "authentication_method": git.AuthenticationMethodEnum.CREDENTIALS.value,
                        "credentials_username": "test_username",
                        "credentials_personal_access_token": "test_personal_access_token",
                        "ssh_private_key": "test_private_key",
                    }
                )

            with pytest.raises(
                ValueError, match="Missing required SSH fields in provided connection info"
            ):
                manager.charm.provider.set_git_connection_info(
                    {"authentication_method": git.AuthenticationMethodEnum.SSH.value}
                )

            with pytest.raises(
                ValueError, match="Unexpected credentials fields in provided connection info"
            ):
                manager.charm.provider.set_git_connection_info(
                    {
                        "authentication_method": git.AuthenticationMethodEnum.SSH.value,
                        "ssh_private_key": "test_private_key",
                        "credentials_username": "test_username",
                    }
                )

    def test_set_git_connection_info_on_empty_relation(self, provider_context, provider_state):
        """Ensure proper update of git connection info on an empty relation."""
        empty_provider_git_relation = ops.testing.Relation(GIT_RELATION_INTERFACE)

        provider_state = dataclasses.replace(
            provider_state, relations=[empty_provider_git_relation], secrets=[]
        )

        with provider_context(provider_context.on.start(), provider_state) as manager:
            manager.run()

            # Should not surface pydantic.ValidationError when building model to update
            # with provided dictionary
            manager.charm.provider.set_git_connection_info({"repository_url": "test_repo_url"})

            assert (
                manager.charm.model.get_relation(GIT_RELATION_INTERFACE)
                .data[manager.charm.app]
                .get("repository-url")
                == "test_repo_url"
            )

    def test_set_git_connection_info(
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

            with unittest.mock.patch(
                "charms.data_platform_libs.v1.data_interfaces.CachedSecret.set_content"
            ) as mock_set_content:
                manager.charm.provider.set_git_connection_info(
                    {
                        "repository_url": "test-url",
                        "path": "new/path",
                    }
                )

                relation_data = manager.charm.model.get_relation(GIT_RELATION_INTERFACE).data[
                    manager.charm.app
                ]

                assert relation_data.get("repository-url") == "test-url"
                assert relation_data.get("path") == "new/path"
                assert relation_data.get("authentication-method") is None  # should be reset

                (
                    mock_set_content.assert_called_with(
                        {"credentials-personal-access-token": "None"}
                    ),
                    "Secret content not 'nullified' due to missing authentication_method",
                )

            with unittest.mock.patch(
                "charms.data_platform_libs.v1.data_interfaces.CachedSecret.set_content"
            ) as mock_set_content:
                manager.charm.provider.set_git_connection_info(
                    {
                        "repository_url": "test-url-2",
                        "authentication_method": "credentials",
                        "credentials_username": "test-user-2",
                        "credentials_personal_access_token": "new-personal-access-token",
                    }
                )

                mock_set_content.assert_called_with(
                    {"credentials-personal-access-token": "new-personal-access-token"}
                )

    def test_set_git_connection_info_with_ssh_passphrase_and_port(
        self,
        provider_context,
        ssh_private_key_secret,
        ssh_passphrase_secret,
        ssh_data_with_passphrase_and_port,
    ):
        """Ensure GitProvides correctly sets ssh_passphrase and ssh_port."""
        ssh_provider_relation = ops.testing.Relation(
            GIT_RELATION_INTERFACE,
            interface=GIT_RELATION_INTERFACE,
            local_app_data=ssh_data_with_passphrase_and_port,
        )
        provider_state = ops.testing.State(
            leader=True,
            relations=[ssh_provider_relation],
            secrets=[ssh_private_key_secret, ssh_passphrase_secret],
        )

        with provider_context(
            provider_context.on.relation_changed(ssh_provider_relation), provider_state
        ) as manager:
            manager.run()

            with unittest.mock.patch(
                "charms.data_platform_libs.v1.data_interfaces.CachedSecret.set_content"
            ) as mock_set_content:
                manager.charm.provider.set_git_connection_info(
                    {
                        "authentication_method": git.AuthenticationMethodEnum.SSH.value,
                        "ssh_private_key": "updated-ssh-private-key",
                        "ssh_passphrase": "updated-ssh-passphrase",
                        "ssh_port": 3333,
                    }
                )

                relation_data = manager.charm.model.get_relation(GIT_RELATION_INTERFACE).data[
                    manager.charm.app
                ]

                assert relation_data.get("ssh-port") == "3333"
                mock_set_content.assert_any_call({"ssh-passphrase": "updated-ssh-passphrase"})

    def test_git_relation_broken(self, provider_context, provider_state, provider_git_relation):
        """Ensure invoke of reconciler callback on git integratorrelation broken."""
        with provider_context(
            provider_context.on.relation_broken(provider_git_relation), provider_state
        ) as manager:
            manager.run()

            assert (
                self.get_juju_log_line("INFO", ops.RelationBrokenEvent)
                in provider_context.juju_log
            )
