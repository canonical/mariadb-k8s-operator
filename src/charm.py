#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""MariaDB K8s Charm.

Implements the holistic (reconciler) pattern: every interesting Juju event
is routed to :meth:`MariaDBCharm._reconcile`, which reads all state,
computes the desired world, and writes it out.  No ``defer`` is used.

Architecture:
  * ``state.py``    - runtime state abstraction (CharmState, Pydantic)
  * ``workload.py`` - all Pebble / MariaDB exec interactions (MariaDBWorkload)
  * ``charm.py``    - Juju event wiring and orchestration (this file)

Relations:
  * ``database`` (provides) - mysql_client interface via data-platform-libs
  * ``mariadb-peers`` (peers) - shares root-password secret URI between units
"""

import logging

import ops
from charms.data_platform_libs.v0.data_interfaces import DatabaseProvides

from state import (
    PEER_RELATION,
    CharmState,
    clear_provisioned,
    create_root_password,
    mark_provisioned,
)
from workload import (
    MariaDBWorkload,
    WorkloadError,
    database_endpoint,
    generate_password,
)

logger = logging.getLogger(__name__)

CONTAINER_NAME = "mariadb"
DATABASE_RELATION = "database"
MARIADB_PORT = 3306


class MariaDBCharm(ops.CharmBase):
    """Charm for deploying MariaDB 10.6 on Kubernetes."""

    def __init__(self, framework: ops.Framework) -> None:
        super().__init__(framework)

        self._container = self.unit.get_container(CONTAINER_NAME)
        self._workload = MariaDBWorkload(self._container)

        self._database_provides = DatabaseProvides(self, relation_name=DATABASE_RELATION)

        # ── Holistic event subscription ───────────────────────────────────────
        # All state-mutating events converge on _reconcile.
        for event in [
            self.on[CONTAINER_NAME].pebble_ready,
            self.on.config_changed,
            self.on.leader_elected,
            self.on.secret_changed,
            self.on[PEER_RELATION].relation_changed,
            self._database_provides.on.database_requested,
        ]:
            framework.observe(event, self._reconcile)

        # Database relation departure: clean up provisioned state.
        framework.observe(
            self.on[DATABASE_RELATION].relation_broken,
            self._on_database_relation_broken,
        )

        # upgrade-charm is handled outside _reconcile (refresh semantics).
        framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)

        # collect_unit_status is fired after every hook and is the recommended
        # ops pattern for setting unit status composably without scattering
        # self.unit.status assignments across multiple code paths.
        framework.observe(self.on.collect_unit_status, self._on_collect_unit_status)

    # ── Main reconciler ───────────────────────────────────────────────────────

    def _reconcile(self, _: ops.EventBase) -> None:
        """Reconcile towards the desired state.

        Structure:
        1. Pre-checks - exit early if fundamental prerequisites are not met.
        2. Bootstrap - ensure root password exists (leader only).
        3. Configure workload - apply Pebble layer.
        4. Provision databases - handle pending database relation requests.
        5. Status is reported via collect_unit_status.
        """
        # Open the MariaDB port so Juju knows the charm exposes it.
        self.unit.open_port("tcp", MARIADB_PORT)

        state = CharmState.from_charm(self, self._container, self._database_provides)

        # ── 1. Pre-checks ─────────────────────────────────────────────────────
        if not state.container_ready:
            logger.debug("Pebble not ready; deferring reconciliation")
            return

        # ── 2. Bootstrap: ensure root password exists ─────────────────────────
        root_password = state.root_password
        if root_password is None:
            if not state.is_leader:
                logger.debug("Waiting for leader to create root password secret")
                return
            logger.info("Creating root password secret")
            try:
                root_password = create_root_password(self)
            except ops.ModelError as exc:
                logger.error("Failed to create root password secret: %s", exc)
                return

        # ── 3. Configure workload ─────────────────────────────────────────────
        try:
            self._workload.configure_pebble_layer(root_password)
        except WorkloadError as exc:
            logger.error("Pebble configuration failed: %s", exc)
            return

        # ── 4. Provision pending databases (leader only) ──────────────────────
        if not state.is_leader:
            return

        if not self._workload.is_ready():
            logger.debug("MariaDB not yet accepting connections; skipping provisioning")
            return

        for relation_id, database_name in state.pending_databases.items():
            try:
                self._provision_database(relation_id, database_name, root_password)
            except (WorkloadError, ops.ModelError) as exc:
                logger.error(
                    "Failed to provision database %r for relation %d: %s",
                    database_name,
                    relation_id,
                    exc,
                )

    # ── Relation handlers ─────────────────────────────────────────────────────

    def _on_database_relation_broken(self, event: ops.RelationBrokenEvent) -> None:
        """Clean up when a consumer departs."""
        if not self.unit.is_leader():
            return

        state = CharmState.from_charm(self, self._container, self._database_provides)
        root_password = state.root_password
        if root_password is None or not self._workload.is_ready():
            logger.warning(
                "Cannot drop database for relation %d: MariaDB unavailable", event.relation.id
            )
            clear_provisioned(self, event.relation.id)
            return

        database_name = event.relation.data.get(event.relation.app, {}).get("database", "")
        username = database_name  # user == database (Frappe/bench assumption)

        try:
            self._workload.drop_database(database_name, username, root_password)
        except WorkloadError as exc:
            logger.error("Failed to drop database %r: %s", database_name, exc)

        clear_provisioned(self, event.relation.id)

    # ── Refresh handler ───────────────────────────────────────────────────────

    def _on_upgrade_charm(self, _: ops.UpgradeCharmEvent) -> None:
        """Handle charm refresh: reapply Pebble layer."""
        state = CharmState.from_charm(self, self._container, self._database_provides)
        if not state.container_ready or state.root_password is None:
            return
        try:
            self._workload.configure_pebble_layer(state.root_password)
        except WorkloadError as exc:
            logger.error("Pebble reconfiguration after upgrade failed: %s", exc)

    # ── Status reporting ──────────────────────────────────────────────────────

    def _on_collect_unit_status(self, event: ops.CollectStatusEvent) -> None:
        """Set the unit status based on the current state."""
        state = CharmState.from_charm(self, self._container, self._database_provides)

        if not state.container_ready:
            event.add_status(ops.WaitingStatus("Waiting for Pebble"))
            return

        if state.root_password is None:
            event.add_status(ops.WaitingStatus("Waiting for root password secret"))
            return

        if not self._workload.is_ready():
            event.add_status(ops.WaitingStatus("Waiting for MariaDB to start"))
            return

        n_provisioned = len(state.provisioned_relation_ids)
        n_pending = len(state.pending_databases)

        if n_pending > 0:
            event.add_status(ops.WaitingStatus(f"Provisioning {n_pending} database(s)"))
            return

        if n_provisioned == 0:
            event.add_status(ops.ActiveStatus("Ready - waiting for database relations"))
        else:
            event.add_status(ops.ActiveStatus(f"Ready - serving {n_provisioned} database(s)"))

    # ── Private helpers ───────────────────────────────────────────────────────

    def _provision_database(
        self, relation_id: int, database_name: str, root_password: str
    ) -> None:
        """Create a MariaDB database and user for *relation_id*, then write
        the credentials to the relation databag.

        Args:
            relation_id: The Juju relation ID being provisioned.
            database_name: The database name requested by the consumer.
            root_password: Root password for the admin MariaDB connection.

        Raises:
            WorkloadError: If the database or user creation fails.
            ops.ModelError: If writing to the relation databag fails.
        """
        # Use database_name as the username: Frappe (and bench) assume user == db_name,
        # so the credential the charm writes to the relation must use that same name.
        username = database_name
        password = generate_password()

        logger.info(
            "Provisioning database %r / user %r for relation %d",
            database_name,
            username,
            relation_id,
        )

        self._workload.create_database(database_name, username, password, root_password)

        self._database_provides.set_credentials(relation_id, username, password)
        self._database_provides.set_database(relation_id, database_name)
        self._database_provides.set_endpoints(relation_id, database_endpoint(self.app.name))

        version = self._workload.mariadb_version(root_password)
        if version:
            self._database_provides.set_version(relation_id, version)

        mark_provisioned(self, relation_id)

        logger.info(
            "Database %r provisioned successfully for relation %d", database_name, relation_id
        )


if __name__ == "__main__":
    ops.main(MariaDBCharm)
