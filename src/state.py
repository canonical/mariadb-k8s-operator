# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Runtime state abstraction for the MariaDB K8s charm.

All Juju-specific state (config, relation data, secrets, unit metadata)
is collected here into plain Pydantic models.  Code outside this module
never touches ``self.config``, ``self.model.relations``, or Juju secrets
directly.
"""

import logging
import secrets
from dataclasses import dataclass, field
from typing import Optional

import ops
from pydantic import BaseModel, SecretStr, field_validator

logger = logging.getLogger(__name__)

# Key used to store the root-password secret URI in the peer relation databag.
_ROOT_SECRET_KEY = "root-password-secret-id"
# Key prefix used to record provisioned databases in the peer relation.
_PROVISIONED_KEY_PREFIX = "provisioned-"

PEER_RELATION = "mariadb-peers"


class DatabaseCredentials(BaseModel):
    """Credentials written to / read from the database relation databag."""

    database: str
    username: str
    password: SecretStr
    relation_id: int

    @field_validator("database", "username")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("must not be empty")
        return v


@dataclass
class CharmState:
    """Assembled runtime state of the MariaDB charm.

    Constructed once per reconciliation cycle via :meth:`from_charm`.
    All fields are plain Python values – no Juju objects leak through.
    """

    is_leader: bool
    container_ready: bool
    root_password: Optional[str]
    # Mapping of relation_id → requested database name for all active
    # database relations that have not yet been provisioned.
    pending_databases: dict[int, str] = field(default_factory=dict)
    # Relation IDs that have already been fully provisioned.
    provisioned_relation_ids: set[int] = field(default_factory=set)

    @classmethod
    def from_charm(
        cls,
        charm: ops.CharmBase,
        container: ops.Container,
        database_provides,  # DatabaseProvides – avoid circular import
    ) -> "CharmState":
        """Build the state from the live charm.

        This is the *only* place where Juju primitives are accessed.
        """
        root_password = cls._load_root_password(charm)

        pending: dict[int, str] = {}
        provisioned: set[int] = set()

        for relation in charm.model.relations.get("database", []):
            if not relation.app:
                continue
            requested_db = relation.data[relation.app].get("database")
            if not requested_db:
                continue
            rel_id = relation.id
            if cls._is_provisioned(charm, rel_id):
                provisioned.add(rel_id)
            else:
                pending[rel_id] = requested_db

        return cls(
            is_leader=charm.unit.is_leader(),
            container_ready=container.can_connect(),
            root_password=root_password,
            pending_databases=pending,
            provisioned_relation_ids=provisioned,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _load_root_password(charm: ops.CharmBase) -> Optional[str]:
        """Return the root password from the Juju secret, or None if not set."""
        peer = charm.model.get_relation(PEER_RELATION)
        if peer is None:
            return None
        secret_id = peer.data[charm.app].get(_ROOT_SECRET_KEY)
        if not secret_id:
            return None
        try:
            secret = charm.model.get_secret(id=secret_id)
            return secret.get_content(refresh=True).get("password")
        except (ops.SecretNotFoundError, KeyError):
            logger.warning("Root password secret %s not found", secret_id)
            return None

    @staticmethod
    def _is_provisioned(charm: ops.CharmBase, relation_id: int) -> bool:
        """Return True if the database for *relation_id* has been provisioned."""
        peer = charm.model.get_relation(PEER_RELATION)
        if peer is None:
            return False
        key = f"{_PROVISIONED_KEY_PREFIX}{relation_id}"
        return bool(peer.data[charm.app].get(key))


def create_root_password(charm: ops.CharmBase) -> str:
    """Generate a random root password, store it as a Juju secret, and
    publish the secret ID to the peer relation.

    Must only be called by the leader unit.

    Returns the new password so the caller can use it immediately.
    """
    password = secrets.token_urlsafe(32)
    secret = charm.unit.add_secret(
        {"password": password},
        label="mariadb-root-password",
        description="MariaDB root password managed by the charm.",
    )
    # Grant access to all units via the app secret grant.
    secret.grant(charm.model.get_relation(PEER_RELATION))

    peer = charm.model.get_relation(PEER_RELATION)
    if peer is not None:
        peer.data[charm.app][_ROOT_SECRET_KEY] = secret.id

    return password


def mark_provisioned(charm: ops.CharmBase, relation_id: int) -> None:
    """Record that the database for *relation_id* has been provisioned."""
    peer = charm.model.get_relation(PEER_RELATION)
    if peer is None:
        return
    key = f"{_PROVISIONED_KEY_PREFIX}{relation_id}"
    peer.data[charm.app][key] = "true"


def clear_provisioned(charm: ops.CharmBase, relation_id: int) -> None:
    """Remove the provisioning record for *relation_id* (called on departure)."""
    peer = charm.model.get_relation(PEER_RELATION)
    if peer is None:
        return
    key = f"{_PROVISIONED_KEY_PREFIX}{relation_id}"
    peer.data[charm.app].pop(key, None)
