# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more about testing at: https://ops.readthedocs.io/en/latest/explanation/testing.html

"""Unit tests for the MariaDB K8s charm.

Tests use ops.testing.Harness (compatible with ops 3.x) to verify
reconciliation behaviour without requiring a running Juju controller or
a real MariaDB instance.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import ops
import pytest
from ops.testing import Harness

from charm import MariaDBCharm, CONTAINER_NAME, DATABASE_RELATION, MARIADB_PORT

CHARM_META = {
    "name": "mariadb-k8s",
    "containers": {CONTAINER_NAME: {"resource": "mariadb-image"}},
    "provides": {DATABASE_RELATION: {"interface": "mysql_client"}},
    "peers": {"mariadb-peers": {"interface": "mariadb-peers"}},
    "resources": {"mariadb-image": {"type": "oci-image"}},
}


def _harness(leader: bool = True) -> Harness:
    h = Harness(MariaDBCharm, meta=str(CHARM_META).replace("'", '"'))
    h.set_leader(leader)
    return h


# ---------------------------------------------------------------------------
# Pebble-not-ready
# ---------------------------------------------------------------------------


def test_waiting_when_pebble_not_ready():
    """Unit should be Waiting when the container is not yet reachable."""
    h = _harness()
    h.begin()
    # Trigger an event so _reconcile runs and collect_unit_status fires.
    h.charm.on.config_changed.emit()
    assert isinstance(h.charm.unit.status, (ops.WaitingStatus, ops.MaintenanceStatus))
    h.cleanup()


# ---------------------------------------------------------------------------
# Port is opened
# ---------------------------------------------------------------------------


def test_mariadb_port_opened():
    """The charm must open TCP 3306 on initialisation."""
    h = _harness()
    h.begin()
    opened = h.charm.unit.opened_ports()
    assert any(p.port == MARIADB_PORT and p.protocol == "tcp" for p in opened)
    h.cleanup()


# ---------------------------------------------------------------------------
# generate_password helper
# ---------------------------------------------------------------------------


def test_generate_password_length():
    from workload import generate_password

    pw = generate_password(32)
    assert len(pw) == 32


def test_generate_password_uniqueness():
    from workload import generate_password

    assert generate_password() != generate_password()


# ---------------------------------------------------------------------------
# database_endpoint helper
# ---------------------------------------------------------------------------


def test_database_endpoint():
    from workload import database_endpoint

    ep = database_endpoint("mariadb-k8s")
    assert "mariadb-k8s" in ep
    assert "3306" in ep


# ---------------------------------------------------------------------------
# CharmState.from_charm – no pending relations
# ---------------------------------------------------------------------------


def test_charm_state_no_relations():
    """CharmState should show no pending databases when no relations exist."""
    from state import CharmState

    charm = MagicMock()
    charm.config.get.return_value = ""
    charm.unit.is_leader.return_value = True
    charm.model.relations.get.return_value = []
    charm.model.get_relation.return_value = None

    container = MagicMock()
    container.can_connect.return_value = True

    db_provides = MagicMock()

    state = CharmState.from_charm(charm, container, db_provides)

    assert state.is_leader is True
    assert state.container_ready is True
    assert state.pending_databases == {}
    assert state.provisioned_relation_ids == set()
    assert state.root_password is None


# ---------------------------------------------------------------------------
# MariaDBWorkload.is_ready
# ---------------------------------------------------------------------------


def test_workload_not_ready_when_container_disconnected():
    from workload import MariaDBWorkload

    container = MagicMock()
    container.can_connect.return_value = False

    wl = MariaDBWorkload(container)
    assert wl.is_ready() is False


def test_workload_not_ready_when_check_down():
    from workload import MariaDBWorkload

    container = MagicMock()
    container.can_connect.return_value = True

    check = MagicMock()
    check.status = ops.pebble.CheckStatus.DOWN
    container.get_check.return_value = check

    wl = MariaDBWorkload(container)
    assert wl.is_ready() is False


def test_workload_ready_when_check_up():
    from workload import MariaDBWorkload

    container = MagicMock()
    container.can_connect.return_value = True

    check = MagicMock()
    check.status = ops.pebble.CheckStatus.UP
    container.get_check.return_value = check

    wl = MariaDBWorkload(container)
    assert wl.is_ready() is True


# ---------------------------------------------------------------------------
# MariaDBWorkload.configure_pebble_layer – no restart when unchanged
# ---------------------------------------------------------------------------


def test_workload_configure_no_restart_when_unchanged():
    """replan should not be called if the service is already running and the
    layer has not changed."""
    from workload import MariaDBWorkload

    container = MagicMock()
    container.can_connect.return_value = True

    # Simulate existing plan that matches the new layer exactly.
    svc_dict = {
        "override": "replace",
        "summary": "MariaDB database server",
        "command": "/usr/local/bin/start-mariadb.sh",
        "startup": "enabled",
        "environment": {"MYSQL_ROOT_PASSWORD": "secret"},
        "on-check-failure": {"mariadb-ready": "restart"},
    }
    mock_plan = MagicMock()
    mock_plan.to_dict.return_value = {"services": {"mariadb": svc_dict}}
    container.get_plan.return_value = mock_plan

    svc = MagicMock()
    svc.is_running.return_value = True
    container.get_service.return_value = svc

    wl = MariaDBWorkload(container)
    wl.configure_pebble_layer("secret")

    container.replan.assert_not_called()


# ---------------------------------------------------------------------------
# MariaDBWorkload.create_database – exec is called
# ---------------------------------------------------------------------------


def test_workload_create_database_calls_exec():
    from workload import MariaDBWorkload

    container = MagicMock()
    proc = MagicMock()
    proc.wait_output.return_value = ("", "")
    container.exec.return_value = proc

    wl = MariaDBWorkload(container)
    wl.create_database("mydb", "myuser", "mypass", "rootpass")

    container.exec.assert_called_once()
    call_kwargs = container.exec.call_args
    # Verify mariadb CLI is invoked as root.
    assert "mariadb" in call_kwargs[0][0]
    assert "--user=root" in call_kwargs[0][0]

