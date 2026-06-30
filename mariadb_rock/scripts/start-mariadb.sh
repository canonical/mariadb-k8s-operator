#!/bin/bash
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Start-up script for MariaDB inside a Pebble-managed container.
# MYSQL_ROOT_PASSWORD must be set in the environment (injected by the charm
# via the Pebble layer).

set -euo pipefail

DATADIR=/var/lib/mysql
SOCKET=/run/mysqld/mysqld.sock

if [ -z "${MYSQL_ROOT_PASSWORD:-}" ]; then
    echo "ERROR: MYSQL_ROOT_PASSWORD is not set" >&2
    exit 1
fi

# Ensure mysql user and group exist (required for running mariadb)
if ! id mysql &>/dev/null; then
    groupadd -r mysql 2>/dev/null || true
    useradd -r -g mysql mysql 2>/dev/null || true
fi

mkdir -p /run/mysqld
chown mysql:mysql /run/mysqld

if [ ! -d "${DATADIR}/mysql" ]; then
    mkdir -p "${DATADIR}"
    chown mysql:mysql "${DATADIR}"

    mariadb-install-db \
        --user=mysql \
        --datadir="${DATADIR}" \
        --skip-test-db \
        --auth-root-authentication-method=normal

    mariadbd \
        --user=mysql \
        --datadir="${DATADIR}" \
        --skip-networking \
        --socket="${SOCKET}" \
        --pid-file=/run/mysqld/init.pid &
    INIT_PID=$!

    for _ in $(seq 1 60); do
        mariadb --socket="${SOCKET}" -uroot -e "SELECT 1" >/dev/null 2>&1 && break
        sleep 1
    done

    mariadb --socket="${SOCKET}" -uroot <<SQL
ALTER USER 'root'@'localhost' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}';
CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;
DELETE FROM mysql.user WHERE User = '';
DROP DATABASE IF EXISTS test;
DELETE FROM mysql.db WHERE Db = 'test' OR Db = 'test\\_%';
FLUSH PRIVILEGES;
SQL

    kill "${INIT_PID}"
    wait "${INIT_PID}" 2>/dev/null || true
fi

exec mariadbd --user=mysql --datadir="${DATADIR}"
