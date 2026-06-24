#!/bin/bash
# Start-up script for MariaDB inside a Pebble-managed container.
#
# On first boot the data directory is empty: we run mariadb-install-db,
# bring up a temporary socket-only instance to harden the installation
# (set root password, drop anonymous users, drop test database), then
# shut the temporary instance down and hand off to the main exec below.
#
# On subsequent boots the data directory already exists so we skip straight
# to the exec.
#
# MYSQL_ROOT_PASSWORD must be set in the environment (injected by the charm
# via the Pebble layer).

set -euo pipefail

DATADIR=/var/lib/mysql
SOCKET=/run/mysqld/mysqld.sock

if [ -z "${MYSQL_ROOT_PASSWORD:-}" ]; then
    echo "ERROR: MYSQL_ROOT_PASSWORD is not set" >&2
    exit 1
fi

mkdir -p /run/mysqld
chown mysql:mysql /run/mysqld

# ── First-boot initialisation ─────────────────────────────────────────────────
if [ ! -d "${DATADIR}/mysql" ]; then
    echo "Initialising MariaDB data directory…"
    mariadb-install-db \
        --user=mysql \
        --datadir="${DATADIR}" \
        --skip-test-db \
        --auth-root-authentication-method=normal

    # Bring up a temporary instance (unix socket only, no networking).
    mariadbd \
        --user=mysql \
        --skip-networking \
        --socket="${SOCKET}" \
        --pid-file=/run/mysqld/init.pid &
    INIT_PID=$!

    echo "Waiting for temporary MariaDB instance…"
    for i in $(seq 1 60); do
        if mariadb --socket="${SOCKET}" -uroot -e "SELECT 1" >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    echo "Hardening installation…"
    mariadb --socket="${SOCKET}" -uroot <<SQL
-- Set root password and lock down remote root access.
ALTER USER 'root'@'localhost' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}';
-- Create root user that the charm can reach over TCP from the same pod.
CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;
-- Remove anonymous accounts and the test database.
DELETE FROM mysql.user WHERE User = '';
DROP DATABASE IF EXISTS test;
DELETE FROM mysql.db WHERE Db = 'test' OR Db = 'test\\_%';
FLUSH PRIVILEGES;
SQL

    echo "Stopping temporary instance…"
    kill "${INIT_PID}"
    wait "${INIT_PID}" 2>/dev/null || true
    echo "Initialisation complete."
fi

# ── Normal startup ────────────────────────────────────────────────────────────
exec mariadbd --user=mysql
