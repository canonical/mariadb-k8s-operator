# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Learn more about testing at: https://ops.readthedocs.io/en/latest/explanation/testing.html

"""Unit tests for the MariaDB K8s charm using the scenario framework."""

from unittest.mock import MagicMock

import ops
import ops.testing

from charm import CONTAINER_NAME, MARIADB_PORT, MariaDBCharm
from workload import MariaDBWorkload, database_endpoint, generate_password

# ---------------------------------------------------------------------------
# Pebble-not-ready: container cannot connect
# ---------------------------------------------------------------------------


def test_waiting_when_pebble_not_ready():
    """Unit should be Waiting when the container is not yet reachable."""
    ctx = ops.testing.Context(MariaDBCharm)
    container = ops.testing.Container(name=CONTAINER_NAME, can_connect=False)
    state_in = ops.testing.State(containers={container})
    state_out = ctx.run(ctx.on.config_changed(), state_in)
    assert state_out.unit_status == ops.testing.WaitingStatus("Waiting for Pebble")


# ---------------------------------------------------------------------------
# Port is opened in reconcile
# ---------------------------------------------------------------------------


def test_mariadb_port_opened():
    """The charm must open TCP 3306 on config-changed."""
    ctx = ops.testing.Context(MariaDBCharm)
    container = ops.testing.Container(name=CONTAINER_NAME, can_connect=False)
    state_in = ops.testing.State(containers={container})
    state_out = ctx.run(ctx.on.config_changed(), state_in)
    opened = state_out.opened_ports
    assert any(p.port == MARIADB_PORT and p.protocol == "tcp" for p in opened)


# ---------------------------------------------------------------------------
# generate_password helper
# ---------------------------------------------------------------------------


def test_generate_password_length():
    pw = generate_password(32)
    assert len(pw) == 32


def test_generate_password_uniqueness():
    assert generate_password() != generate_password()


# ---------------------------------------------------------------------------
# database_endpoint helper
# ---------------------------------------------------------------------------


def test_database_endpoint():
    ep = database_endpoint("mariadb-k8s")
    assert "mariadb-k8s" in ep
    assert "3306" in ep


# ---------------------------------------------------------------------------
# CharmState.from_charm - no pending relations
# ---------------------------------------------------------------------------


def test_charm_state_no_relations():
    """CharmState should show no pending databases when no relations exist."""
    from state import CharmState

    charm = MagicMock()
    charm.unit.is_leader.return_value = True
    charm.model.relations.get.return_value = []
    charm.model.get_relation.return_value = None

    container = MagicMock()
    container.can_connect.return_value = True

    state = CharmState.from_charm(charm, container, MagicMock())

    assert state.is_leader is True
    assert state.container_ready is True
    assert state.pending_databases == {}
    assert state.provisioned_relation_ids == set()
    assert state.root_password is None


# ---------------------------------------------------------------------------
# MariaDBWorkload.is_ready
# ---------------------------------------------------------------------------


def test_workload_not_ready_when_container_disconnected():
    container = MagicMock()
    container.can_connect.return_value = False
    assert MariaDBWorkload(container).is_ready() is False


def test_workload_not_ready_when_check_down():
    container = MagicMock()
    container.can_connect.return_value = True
    check = MagicMock()
    check.status = ops.pebble.CheckStatus.DOWN
    container.get_check.return_value = check
    assert MariaDBWorkload(container).is_ready() is False


def test_workload_ready_when_check_up():
    container = MagicMock()
    container.can_connect.return_value = True
    check = MagicMock()
    check.status = ops.pebble.CheckStatus.UP
    container.get_check.return_value = check
    assert MariaDBWorkload(container).is_ready() is True


# ---------------------------------------------------------------------------
# MariaDBWorkload.configure_pebble_layer - no restart when unchanged
# ---------------------------------------------------------------------------


def test_workload_configure_no_restart_when_unchanged():
    """Replan should not be called if the service is already running and the
    layer has not changed.
    """
    container = MagicMock()
    container.can_connect.return_value = True

    svc_dict = {
        "override": "replace",
        "summary": "MariaDB database server",
        "command": "/usr/local/bin/start-mariadb.sh",
        "startup": "enabled",
        "environment": {"MYSQL_ROOT_PASSWORD": "secret"},  # nosec B105
        "on-check-failure": {"mariadb-ready": "restart"},
    }
    mock_plan = MagicMock()
    mock_plan.to_dict.return_value = {"services": {"mariadb": svc_dict}}
    container.get_plan.return_value = mock_plan

    svc = MagicMock()
    svc.is_running.return_value = True
    container.get_service.return_value = svc

    MariaDBWorkload(container).configure_pebble_layer("secret")
    container.replan.assert_not_called()


# ---------------------------------------------------------------------------
# MariaDBWorkload.create_database - exec is called
# ---------------------------------------------------------------------------


def test_workload_create_database_calls_exec():
    container = MagicMock()
    proc = MagicMock()
    proc.wait_output.return_value = ("", "")
    container.exec.return_value = proc

    MariaDBWorkload(container).create_database("mydb", "myuser", "mypass", "rootpass")

    container.exec.assert_called_once()
    cmd = container.exec.call_args[0][0]
    assert "mariadb" in cmd
    assert "--user=root" in cmd
