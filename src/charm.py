#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Git Integrator charm."""

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
            logger.exception("Issue retrieving personal access token secret")
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
            logger.exception("Issue retrieving ssh private key secret")
            raise ExitWithStatusError(constants.INVALID_SSH_PRIVATE_KEY_MESSAGE, ops.BlockedStatus)

        ssh_private_key = secret.get_content().get(constants.SSH_PRIVATE_KEY)
        if not ssh_private_key:
            raise ExitWithStatusError(
                constants.MISSING_SSH_PRIVATE_KEY_IN_SECRET_MESSAGE, ops.BlockedStatus
            )

        return ssh_private_key

    @property
    def _ssh_passphrase(self) -> str:
        """SSH key passphrase for authentication."""
        try:
            secret = self.model.get_secret(
                id=self.config[constants.SSH_PASSPHRASE_SECRET_CONFIG],
                label=constants.SSH_PASSPHRASE,
            )
        except (ops.SecretNotFoundError, ops.ModelError):
            logger.exception("Issue retrieving ssh passphrase secret")
            raise ExitWithStatusError(
                constants.INVALID_SSH_PASSPHRASE_SECRET_MESSAGE, ops.BlockedStatus
            )

        ssh_passphrase = secret.get_content().get(constants.SSH_PASSPHRASE)
        if not ssh_passphrase:
            raise ExitWithStatusError(
                constants.MISSING_SSH_PASSPHRASE_IN_SECRET_MESSAGE, ops.BlockedStatus
            )

        return ssh_passphrase

    def _check_credentials_configs(self):
        """Validations for credentials related configs.

        Raises ExitWithStatusError with BlockedStatus if username is missing, or
        if the personal_access_token cannot be retrieved from a juju user secret.
        """
        if not self.config.get(constants.CREDENTIALS_USERNAME_CONFIG):
            raise ExitWithStatusError(constants.MISSING_USERNAME_MESSAGE, ops.BlockedStatus)

        if not self.config.get(constants.CREDENTIALS_PERSONAL_ACCESS_TOKEN_SECRET_CONFIG):
            raise ExitWithStatusError(
                constants.MISSING_PERSONAL_ACCESS_TOKEN_SECRET_MESSAGE,
                ops.BlockedStatus,
            )

        self._personal_access_token  # property implements validity checks

    def _check_ssh_configs(self):
        """Validations for SSH related configs.

        Raises ExitWithStatusError with BlockedStatus if the ssh_private_key
        cannot be retrieved from a juju user secret, or if the ssh_passphrase
        secret is configured but invalid.
        """
        if not self.config.get(constants.SSH_PRIVATE_KEY_SECRET_CONFIG):
            raise ExitWithStatusError(
                constants.MISSING_SSH_PRIVATE_KEY_SECRET_MESSAGE,
                ops.BlockedStatus,
            )

        self._ssh_private_key  # property implements validity checks

        if self.config.get(constants.SSH_PASSPHRASE_SECRET_CONFIG):
            self._ssh_passphrase  # property implements validity checks

    def _check_required_configs(self):
        """Check if required configurations present.

        Raises ExitWithStatusError with BlockedStatus if repository_url is missing,
        if authentication_method is set to an unrecognised value, or if the
        auth-method-specific checks fail.  When authentication_method is unset
        the charm is valid with no authentication credentials.
        """
        if not self.config.get(constants.REPOSITORY_URL_CONFIG):
            raise ExitWithStatusError(
                constants.MISSING_REPOSITORY_URL_MESSAGE,
                ops.BlockedStatus,
            )

        authentication_method = self.config.get(constants.AUTHENTICATION_METHOD_CONFIG)

        if authentication_method and authentication_method not in git.AuthenticationMethodEnum:
            raise ExitWithStatusError(
                constants.INVALID_AUTHENTICATION_MESSAGE,
                ops.BlockedStatus,
            )

        if authentication_method == git.AuthenticationMethodEnum.CREDENTIALS:
            self._check_credentials_configs()
        elif authentication_method == git.AuthenticationMethodEnum.SSH:
            self._check_ssh_configs()

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
            git_connection_information["credentials_username"] = self.config[
                constants.CREDENTIALS_USERNAME_CONFIG
            ]
            git_connection_information["credentials_personal_access_token"] = (
                self._personal_access_token
            )
        elif (
            self.config.get(constants.AUTHENTICATION_METHOD_CONFIG)
            == git.AuthenticationMethodEnum.SSH
        ):
            git_connection_information["ssh_private_key"] = self._ssh_private_key
            git_connection_information["ssh_strict_host_key_checking"] = self.config[
                constants.SSH_STRICT_HOST_KEY_CHECKING_CONFIG
            ]

            if self.config.get(constants.SSH_PASSPHRASE_SECRET_CONFIG):
                git_connection_information["ssh_passphrase"] = self._ssh_passphrase

            if self.config.get(constants.SSH_PORT_CONFIG):
                git_connection_information["ssh_port"] = self.config[constants.SSH_PORT_CONFIG]

        self._git_provider.set_git_connection_info(git_connection_information)

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
