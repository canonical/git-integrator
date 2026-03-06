#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Git Integrator charm application."""

import logging

import charms.git_integrator.v0.git as git
import ops

import constants

logger = logging.getLogger(__name__)


class ExitWithStatusError(Exception):
    """Exception raised to exit with a specific status."""

    def __init__(self, msg: str, status_type):
        super().__init__(str(msg))
        self.msg = str(msg)
        self.status_type = status_type

    @property
    def status(self):
        """Return the Juju unit status represented by this exception."""
        return self.status_type(self.msg)


class GitIntegratorCharm(ops.CharmBase):
    """Encapsulation of the git integrator charm."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        for event in [
            self.on.start,
            self.on.config_changed,
            self.on.update_status,
        ]:
            self.framework.observe(event, self._reconcile)

        self._git_provider = git.GitProvides(
            self,
            constants.GIT_ENDPOINT,
            self._reconcile,
        )

    @property
    def _personal_access_token(self) -> str:
        """Personal access token for authentication."""
        try:
            secret = self.model.get_secret(
                id=self.config[constants.CREDENTIALS_PERSONAL_ACCESS_TOKEN_SECRET_CONFIG],
                label=constants.PERSONAL_ACCESS_TOKEN,
            )
        except (ops.SecretNotFoundError, ops.ModelError):
            raise ExitWithStatusError(
                constants.INVALID_PERSONAL_ACCESS_TOKEN_SECRET_MESSAGE, ops.BlockedStatus
            )

        personal_access_token = secret.get_content().get(constants.PERSONAL_ACCESS_TOKEN)
        if not personal_access_token:
            raise ExitWithStatusError(
                constants.MISSING_PERSONAL_ACCESS_TOKEN_IN_SECRET_MESSAGE, ops.BlockedStatus
            )

        return personal_access_token

    @property
    def _ssh_private_key(self) -> str:
        """SSH private key for authentication."""
        try:
            secret = self.model.get_secret(
                id=self.config[constants.SSH_PRIVATE_KEY_SECRET_CONFIG],
                label=constants.SSH_PRIVATE_KEY,
            )
        except (ops.SecretNotFoundError, ops.ModelError):
            raise ExitWithStatusError(constants.INVALID_SSH_PRIVATE_KEY_MESSAGE, ops.BlockedStatus)

        ssh_private_key = secret.get_content().get(constants.SSH_PRIVATE_KEY)
        if not ssh_private_key:
            raise ExitWithStatusError(
                constants.MISSING_SSH_PRIVATE_KEY_IN_SECRET_MESSAGE, ops.BlockedStatus
            )

        return ssh_private_key

    def _check_required_configs(self):  # noqa: C901
        """Check if required configurations present."""
        if not self.config:
            raise ExitWithStatusError(
                constants.WAITING_FOR_CONFIGURATION_MESSAGE,
                ops.BlockedStatus,
            )

        if not self.config.get(constants.REPOSITORY_URL_CONFIG):
            raise ExitWithStatusError(
                constants.MISSING_REPOSITORY_URL_MESSAGE,
                ops.BlockedStatus,
            )

        authentication_method = self.config.get(constants.AUTHENTICATION_METHOD_CONFIG)

        if authentication_method and authentication_method not in git.AuthenticationMethodEnum:
            raise ExitWithStatusError(
                constants.INVALID_AUTHENTICAITON_MESSAGE,
                ops.BlockedStatus,
            )

        if authentication_method == git.AuthenticationMethodEnum.CREDENTIALS:
            if not self.config.get(constants.CREDENTIALS_USERNAME_CONFIG):
                raise ExitWithStatusError(constants.MISSING_USERNAME_MESSAGE, ops.BlockedStatus)

            if not self.config.get(constants.CREDENTIALS_PERSONAL_ACCESS_TOKEN_SECRET_CONFIG):
                raise ExitWithStatusError(
                    constants.MISSING_PERSONAL_ACCESS_TOKEN_SECRET_MESSAGE,
                    ops.BlockedStatus,
                )

            if not self._personal_access_token:
                pass  # property implements validity checks

        if authentication_method == git.AuthenticationMethodEnum.SSH:
            if not self.config.get(constants.SSH_PRIVATE_KEY_SECRET_CONFIG):
                raise ExitWithStatusError(
                    constants.MISSING_SSH_PRIVATE_KEY_SECRET_MESSAGE,
                    ops.BlockedStatus,
                )

            if not self._ssh_private_key:
                pass  # property implements validity checks

    def _update_git_connection_information(self) -> None:
        """Update git connection information to share with related apps."""
        git_connection_information = {
            "repository_url": self.config[constants.REPOSITORY_URL_CONFIG],
        }

        if self.config.get(constants.PATH_CONFIG):
            git_connection_information["path"] = self.config[constants.PATH_CONFIG]

        if self.config.get(constants.TRACKING_REF_CONFIG):
            git_connection_information["tracking_ref"] = self.config[constants.TRACKING_REF_CONFIG]

        if self.config.get(constants.AUTHENTICATION_METHOD_CONFIG):
            git_connection_information["authentication_method"] = self.config[
                constants.AUTHENTICATION_METHOD_CONFIG
            ]

        if (
            self.config.get(constants.AUTHENTICATION_METHOD_CONFIG)
            == git.AuthenticationMethodEnum.CREDENTIALS
        ):
            git_connection_information["username"] = self.config[
                constants.CREDENTIALS_USERNAME_CONFIG
            ]
            git_connection_information["personal_access_token"] = self._personal_access_token
        elif (
            self.config.get(constants.AUTHENTICATION_METHOD_CONFIG)
            == git.AuthenticationMethodEnum.SSH
        ):
            git_connection_information["ssh_private_key"] = self._ssh_private_key
            git_connection_information["ssh_strict_host_key_checking"] = self.config[
                constants.SSH_STRICT_HOST_KEY_CHECKING_CONFIG
            ]

        self._git_provider.update_git_connection_info(git_connection_information)

    def _reconcile(self, _) -> None:
        """Reconciler method for events handled by this charm."""
        if not self.unit.is_leader():
            return

        try:
            self._check_required_configs()
            self._update_git_connection_information()
        except ExitWithStatusError as e:
            self.unit.status = e.status
            return

        self.unit.status = ops.ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    ops.main(GitIntegratorCharm)
