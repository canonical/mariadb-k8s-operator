# MariaDB K8s Operator
<!-- Use this space for badges -->

> **⚠️ Experimental — not for production use**
>
> This charm is under active development and intended solely as a **temporary placeholder**
> to support the [Frappe HRMS K8s charm](https://github.com/canonical/frappe-hrms-k8s-operator)
> while it awaits native PostgreSQL / MySQL support. It is **not** a general-purpose MariaDB
> operator and should not be relied upon in production environments.

A Kubernetes charm that deploys and manages [MariaDB 10.6](https://mariadb.org/) via Pebble on any Juju K8s substrate.

Like any Juju charm, this charm supports one-line deployment, configuration, integration, scaling, and more. For the MariaDB K8s Operator, this includes:
* Automated first-boot initialisation of the MariaDB data directory
* Secure auto-generated root password stored as a Juju secret
* On-demand database and user provisioning via the `database` relation (`mysql_client` interface)
* Idempotent reconciliation — no `defer()` required

For information about how to deploy, integrate, and manage this charm, see the Official [MariaDB K8s Operator Documentation](https://discourse.charmhub.io).

## Get started

### Prerequisites

* A Juju K8s controller (MicroK8s or any CAPI-backed cluster)
* `charmcraft` and `rockcraft` installed
* `juju` CLI

### Build the OCI image

```bash
cd mariadb-k8s-operator
rockcraft pack
skopeo --insecure-policy copy --dest-tls-verify=false \
    oci-archive:mariadb_10.6_amd64.rock \
    docker://localhost:32000/mariadb-k8s:latest
```

### Build and deploy the charm

```bash
charmcraft pack
juju add-model mariadb-dev
juju deploy ./mariadb-k8s_ubuntu-22.04-amd64.charm \
    --resource mariadb-image=localhost:32000/mariadb-k8s:latest
juju status --watch 5s
```

### Basic operations

Wait for the unit to reach `active/idle`, then integrate with a consumer charm:

```bash
juju deploy frappe-hrms-k8s
juju integrate mariadb-k8s frappe-hrms-k8s
```

The charm creates a dedicated MariaDB database and user for each integration and writes the credentials to the relation data automatically.

## Integrations

| Endpoint | Interface | Role | Description |
|---|---|---|---|
| `database` | `mysql_client` | provides | Provision databases for consumer charms |
| `mariadb-peers` | `mariadb-peers` | peer | Share root-password secret URI between units |

## Learn more

* [Charmhub page](https://charmhub.io/mariadb-k8s)
* [MariaDB documentation](https://mariadb.com/kb/en/documentation/)
* [Juju documentation](https://documentation.ubuntu.com/juju/)
* [Rockcraft documentation](https://documentation.ubuntu.com/rockcraft/stable/)
* [Troubleshooting](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)

## Project and community

* [Issues](https://github.com/canonical/mariadb-k8s-operator/issues)
* [Contributing](CONTRIBUTING.md)
* [Matrix](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
* [Launchpad](https://launchpad.net/~canonical-is-devops)

## Licensing

The MariaDB K8s Operator is distributed under the [Apache 2.0 licence](LICENSE).
MariaDB itself is distributed under the [GPL-2.0 licence](https://mariadb.com/kb/en/licensing-faq/).

