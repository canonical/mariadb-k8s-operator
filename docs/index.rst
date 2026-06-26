.. meta::
   :description: Discover the mariadb-k8s charm, a Juju operator that deploys and manages mariadb-k8s.

.. vale Canonical.007-Headings-sentence-case = NO

.. _index:

``mariadb-k8s`` operator
========================

.. vale Canonical.007-Headings-sentence-case = YES

.. warning::

   **Experimental — not for production use.**

   This charm is under active development and is a **temporary placeholder**
   built specifically for the
   `Frappe HRMS K8s charm <https://github.com/canonical/frappe-hrms-k8s-operator>`_
   while Frappe HRMS awaits native PostgreSQL / MySQL support.
   It is not a general-purpose MariaDB operator and will be retired once
   Frappe HRMS gains first-class support for a supported database backend.

A `Juju <https://juju.is/>`_ `charm <https://documentation.ubuntu.com/juju/3.6/reference/charm/>`_
deploying and managing MariaDB 10.6 on Kubernetes as a temporary database backend
for the `Frappe HRMS K8s charm <https://github.com/canonical/frappe-hrms-k8s-operator>`_.

Like any Juju charm, this charm supports one-line deployment, configuration, integration,
scaling, and more.
For ``mariadb-k8s``, this includes:

* Automated first-boot initialisation of the MariaDB data directory
* Secure auto-generated root password stored as a Juju secret
* On-demand database and user provisioning via the ``database`` relation (``mysql_client`` interface)
* Idempotent reconciliation — no ``defer()`` required

The ``mariadb-k8s`` charm can be deployed on any Juju Kubernetes substrate,
from `MicroK8s <https://microk8s.io/>`_ to
`Charmed Kubernetes <https://ubuntu.com/kubernetes>`_ to public cloud Kubernetes offerings.

This charm is intended for use by teams running
`Frappe HRMS <https://frappehr.com/>`_ on Kubernetes via Juju who need a lightweight
MariaDB backend while awaiting official PostgreSQL or MySQL support upstream.

In this documentation
---------------------

.. list-table::
    :header-rows: 1

    * - 
      - 
    * - Get started
      - :ref:`Guided tutorial <tutorial_index>` | :ref:`High-level deployment <reference_high_level_deployment>` 
    * - Deployment
      - Relevant how-to guides and reference pages (related to initial setup, configurations, and customization)
    * - Operations
      - Relevant how-to guides and reference pages (examples: integrate with COS, backup/restore, redeploy, upgrade)
    * - Design
      - :ref:`Architecture <reference_charm_architecture>` | :ref:`Design <explanation_charm_design>`
    * - Security
      - :ref:`Overview <explanation_security>` | Relevant how-to guides | Relevant reference pages

How this documentation is organized
------------------------------------

This documentation uses the `Diátaxis documentation structure <https://diataxis.fr/>`_.

- The :ref:`Tutorial <tutorial_index>` takes you step-by-step through a basic deployment of the MariaDB K8s charm.
- :ref:`How-to guides <how_to_index>` assume you have basic familiarity with the MariaDB K8s charm. Learn more about setting up, using, maintaining, and contributing to this charm.
- :ref:`Reference <reference_index>` provides a guide to actions, configurations, relations, and other technical details.
- :ref:`Explanation <explanation_index>` includes topic overviews, background and context and detailed discussion.
- :ref:`Release notes <release_notes_index>` holds all the release notes for the charm, including any system or upgrade requirements.

Contributing to this documentation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Documentation is an important part of this project, and we take the same open-source approach
to the documentation as the code. As such, we welcome community contributions, suggestions, and
constructive feedback on our documentation.
See :ref:`How to contribute <how_to_contribute>` for more information.

If there's a particular area of documentation that you'd like to see that's missing, please
`file a bug <https://github.com/canonical/mariadb-k8s-operator/issues>`_.

Project and community
---------------------

The ``mariadb-k8s`` operator is a member of the Ubuntu family. It's an open-source project that warmly welcomes community
projects, contributions, suggestions, fixes, and constructive feedback.

Governance and policies
^^^^^^^^^^^^^^^^^^^^^^^

- `Code of conduct <https://ubuntu.com/community/code-of-conduct>`_

Get involved
^^^^^^^^^^^^

- `Get support <https://discourse.charmhub.io/>`_
- `Join our online chat <https://matrix.to/#/#charmhub-charmdev:ubuntu.com>`_
- :ref:`Contribute <how_to_contribute>`

Releases
^^^^^^^^

- :ref:`Release notes <release_notes_index>`

Thinking about using the ``mariadb-k8s`` operator for your next project?
`Get in touch <https://matrix.to/#/#charmhub-charmdev:ubuntu.com>`_!

.. vale Canonical.013-Spell-out-numbers-below-10 = NO
.. vale Canonical.500-Repeated-words = NO

.. toctree::
    :hidden:
    :maxdepth: 1

    Tutorial <tutorial/index>
    How-to guides <how-to/index>
    Reference <reference/index>
    Explanation <explanation/index>
    Release notes <release-notes/index>

