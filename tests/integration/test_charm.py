#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for the MariaDB K8s charm."""

import logging

import jubilant
import pytest

logger = logging.getLogger(__name__)

MARIADB_APP = "mariadb-k8s"
MARIADB_PORT = 3306


@pytest.mark.abort_on_fail
def test_deploy(juju: jubilant.Juju, charm: str):
    """
    arrange: A Juju model with the mariadb-k8s charm file.
    act: Deploy the charm.
    assert: The application reaches active/idle.
    """
    juju.deploy(charm, app=MARIADB_APP, num_units=1)
    juju.wait(jubilant.all_active, timeout=5 * 60)
    status = juju.status()
    assert MARIADB_APP in status.apps


@pytest.mark.abort_on_fail
def test_charm_active_after_deploy(juju: jubilant.Juju):
    """
    arrange: The mariadb-k8s charm is deployed and active.
    act: Query the Juju status.
    assert: The unit is in active/idle state.
    """
    status = juju.status()
    app = status.apps[MARIADB_APP]
    assert app.is_active

