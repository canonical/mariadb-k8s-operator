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
def test_deploy(juju: jubilant.Juju, charm: str, mariadb_image: str | None):
    """
    arrange: A Juju model with the mariadb-k8s charm file.
    act: Deploy the charm.
    assert: The application reaches active/idle.
    """
    resources = {}
    if mariadb_image:
        resources["mariadb-image"] = mariadb_image
    juju.deploy(charm, app=MARIADB_APP, num_units=1, resources=resources)
    juju.wait(jubilant.all_active, timeout=5 * 60)
    status = juju.status()
    assert MARIADB_APP in status.apps
