# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Workload operations for the MariaDB K8s charm.

All Pebble and MariaDB-specific logic lives here.  ``charm.py`` depends on
this module; ``state.py`` does not.

The Pebble layer is applied on every reconciliation so that configuration
changes (e.g. a new root password) are always reflected.  The MariaDB
service is only restarted when the layer actually changes.
"""

import logging
import secrets
import string
from typing import Optional

import ops

logger = logging.getLogger(__name__)

MARIADB_PORT = 3306
_SERVICE_NAME = "mariadb"


class WorkloadError(Exception):
    """Raised when a workload operation fails."""


_STARTUP_SCRIPT_PATH = "/usr/local/bin/start-mariadb.sh"


class MariaDBWorkload:
    """Encapsulates all interactions with the MariaDB workload container."""

    def __init__(self, container: ops.Container) -> None:
        self._container = container

    # ── Pebble layer ──────────────────────────────────────────────────────────

    def configure_pebble_layer(self, root_password: str) -> None:
        """Push the Pebble layer and restart the service only if it changed.

        The ``level=alive`` check is intentionally omitted per the charm
        implementation guidelines: Pebble's own health is sufficient for the
        K8s liveness probe.  A ``level=ready`` TCP check drives the K8s
        readiness probe and also triggers a Pebble auto-restart if MariaDB
        stops accepting connections.
        """
        new_layer = ops.pebble.Layer(
            {
                "summary": "MariaDB layer",
                "description": "Pebble layer for MariaDB 10.6",
                "services": {
                    _SERVICE_NAME: {
                        "override": "replace",
                        "summary": "MariaDB database server",
                        "command": "/usr/local/bin/start-mariadb.sh",
                        "startup": "enabled",
                        "environment": {
                            "MYSQL_ROOT_PASSWORD": root_password,
                        },
                        "on-check-failure": {
                            "mariadb-ready": "restart",
                        },
                    }
                },
                "checks": {
                    "mariadb-ready": {
                        "override": "replace",
                        # level=ready drives the K8s readiness probe.
                        # level=alive is intentionally NOT used (see guidelines).
                        "level": "ready",
                        "tcp": {"port": MARIADB_PORT},
                        "period": "10s",
                        "timeout": "5s",
                        "threshold": 3,
                    }
                },
            }
        )

        current_plan = self._container.get_plan()
        current_layer = current_plan.to_dict().get("services", {}).get(_SERVICE_NAME, {})
        new_layer_dict = new_layer.to_dict().get("services", {}).get(_SERVICE_NAME, {})

        self._container.add_layer(_SERVICE_NAME, new_layer, combine=True)

        service_running = self._service_is_running()
        layer_changed = current_layer != new_layer_dict

        if not service_running or layer_changed:
            try:
                self._container.replan()
            except ops.pebble.ChangeError as exc:
                raise WorkloadError(f"Failed to start MariaDB service: {exc}") from exc

    # ── Readiness ─────────────────────────────────────────────────────────────

    def is_ready(self) -> bool:
        """Return True when MariaDB is accepting TCP connections."""
        if not self._container.can_connect():
            return False
        try:
            check = self._container.get_check("mariadb-ready")
            return check.status == ops.pebble.CheckStatus.UP
        except ops.pebble.APIError:
            return False

    # ── Database / user provisioning ──────────────────────────────────────────

    def create_database(
        self, database: str, username: str, password: str, root_password: str
    ) -> None:
        """Create *database* and *username* with full privileges on it.

        Idempotent: uses ``CREATE DATABASE IF NOT EXISTS`` and
        ``CREATE USER IF NOT EXISTS``.

        Args:
            database: Name of the database to create.
            username: MariaDB username to create.
            password: Password for the new user.
            root_password: Root password used to authenticate the admin connection.

        Raises:
            WorkloadError: If the exec command fails.
        """
        sql = (
            f"CREATE DATABASE IF NOT EXISTS `{database}`;\n"
            f"CREATE USER IF NOT EXISTS '{username}'@'%' IDENTIFIED BY '{password}';\n"
            f"GRANT ALL PRIVILEGES ON `{database}`.* TO '{username}'@'%';\n"
            "FLUSH PRIVILEGES;\n"
        )
        self._exec_sql(sql, root_password)

    def drop_database(self, database: str, username: str, root_password: str) -> None:
        """Drop *database* and *username*.

        Idempotent: uses ``DROP DATABASE IF EXISTS`` and ``DROP USER IF EXISTS``.

        Args:
            database: Name of the database to drop.
            username: MariaDB username to drop.
            root_password: Root password used to authenticate the admin connection.

        Raises:
            WorkloadError: If the exec command fails.
        """
        sql = (
            f"DROP DATABASE IF EXISTS `{database}`;\n"
            f"DROP USER IF EXISTS '{username}'@'%';\n"
            "FLUSH PRIVILEGES;\n"
        )
        self._exec_sql(sql, root_password)

    def mariadb_version(self, root_password: str) -> Optional[str]:
        """Return the MariaDB server version string, or None on failure."""
        try:
            proc = self._container.exec(
                [
                    "mariadb",
                    "--user=root",
                    f"--password={root_password}",
                    "--host=127.0.0.1",
                    "--batch",
                    "--skip-column-names",
                    "--execute=SELECT VERSION();",
                ],
                environment={"MYSQL_PWD": root_password},
            )
            stdout, _ = proc.wait_output()
            return stdout.strip()
        except (ops.pebble.ExecError, ops.pebble.APIError) as exc:
            logger.warning("Could not retrieve MariaDB version: %s", exc)
            return None

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _service_is_running(self) -> bool:
        try:
            svc = self._container.get_service(_SERVICE_NAME)
            return svc.is_running()
        except (ops.pebble.APIError, KeyError):
            return False

    def _exec_sql(self, sql: str, root_password: str) -> None:
        """Execute *sql* via the mariadb CLI inside the container."""
        try:
            proc = self._container.exec(
                ["mariadb", "--user=root", "--host=127.0.0.1", "--batch", "--skip-column-names"],
                environment={"MYSQL_PWD": root_password},
                stdin=sql,
            )
            proc.wait_output()
        except ops.pebble.ExecError as exc:
            raise WorkloadError(f"SQL execution failed: {exc.stderr}") from exc
        except ops.pebble.APIError as exc:
            raise WorkloadError(f"Pebble API error during SQL exec: {exc}") from exc


def generate_password(length: int = 24) -> str:
    """Generate a cryptographically-random alphanumeric password."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def database_endpoint(app_name: str) -> str:
    """Return the K8s DNS endpoint for the MariaDB service.

    Juju exposes the application as ``<app-name>.<namespace>.svc.cluster.local``.
    The charm writes this as the ``endpoints`` field in the relation databag so
    consumers can build a DSN without needing to know the pod IP.
    """
    # The namespace is not directly available to the charm; the K8s DNS
    # short-name ``<app-name>`` resolves within the same namespace and is
    # sufficient for in-cluster consumers.
    return f"{app_name}:{MARIADB_PORT}"
