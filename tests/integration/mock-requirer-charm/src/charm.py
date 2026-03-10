#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""A mock Git requirer charm to be used in testing the Git Integrator charm."""

import logging

import ops

from charms.git_integrator.v0 import git

logger = logging.getLogger(__name__)

GIT_RELATION = "git"


class MockGitRequirerCharmCharm(ops.CharmBase):
    """Charm that indicates the state of relation with Git Integrator."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        self.git_requirer = git.GitRequires(
            self,
            GIT_RELATION,
            callback=self.log_event_and_set_status,
        )

        self.framework.observe(self.git_requirer.on.git_connection_information_updated, self.log_event)
        self.framework.observe(self.on.get_git_connection_information_action, self.get_git_connection_information)


    def log_event_and_set_status(self, event) -> None:
        """Reconciler mock that logs invoker event + set unit status."""
        logger.info(f"§Handled event: {event}")

        if not self.model.get_relation(GIT_RELATION):
            self.unit.status = ops.BlockedStatus("Missing relation with Git Integrator")
            return

        self.unit.status = ops.ActiveStatus()

    def log_event(self, event: ops.EventBase) -> None:
        """Log dispatched custom requirer events."""
        logger.info(f"§Handled custom event: {event}")

    def get_git_connection_information(self, event: ops.ActionEvent) -> None:
        """Handler to surface git connection info from the relation."""
        if not self.model.get_relation(GIT_RELATION):
            event.fail(f"Missing {GIT_RELATION} relation")
            return

        event.set_results({
            "git_connection_information": self.git_requirer.git_git_connection_information(),
        })


if __name__ == "__main__":  # pragma: nocover
    ops.main(MockGitRequirerCharmCharm)
