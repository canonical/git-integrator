#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Git Integrator charm."""

import logging

import ops

logger = logging.getLogger(__name__)


class GitIntegratorCharm(ops.CharmBase):
    """Encapsulation of the git integrator charm."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)


if __name__ == "__main__":  # pragma: nocover
    ops.main(GitIntegratorCharm)
