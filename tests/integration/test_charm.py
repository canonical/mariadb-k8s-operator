#!/usr/bin/env python3

# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for the MariaDB K8s charm."""

import logging

import jubilant
import pytest

logger = logging.getLogger(__name__)

MARIADB_APP = "mariadb-k8s"


@pytest.mark.abort_on_fail
def test_deploy(juju: jubilant.Juju, charm_path: str, resource_images: dict):
    """
    arrange: A Juju model with K8s.
    act: Deploy the charm with its OCI image resource.
    assert: The application reaches active/idle.
    """
    juju.deploy(charm_path, app=MARIADB_APP, num_units=1, resources=resource_images)
    juju.wait(jubilant.all_active, timeout=5 * 60)
    status = juju.status()
    assert MARIADB_APP in status.apps
