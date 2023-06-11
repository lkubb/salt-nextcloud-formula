.. _readme:

Nextcloud Server Formula
========================

|img_sr| |img_pc|

.. |img_sr| image:: https://img.shields.io/badge/%20%20%F0%9F%93%A6%F0%9F%9A%80-semantic--release-e10079.svg
   :alt: Semantic Release
   :scale: 100%
   :target: https://github.com/semantic-release/semantic-release
.. |img_pc| image:: https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white
   :alt: pre-commit
   :scale: 100%
   :target: https://github.com/pre-commit/pre-commit

Manage Nextcloud Server installation, updates, apps, users, groups and more with Salt.

This formula includes an execution and state module to achieve tight integration with Nextcloud and thus makes administration much more convenient. Many of the ``occ`` functions have been wrapped.

This formula takes care of the Nextcloud part only. To be able to run Nextcloud, you will need to configure PHP as well as an HTTP server, at least. I use my own formulae for `PHP <https://github.com/lkubb/salt-php-formula>`_, `MariaDB <https://github.com/lkubb/salt-mariadb-formula>`_, `Nginx <https://github.com/lkubb/salt-nginx-formula>`_ and `Redis <https://github.com/lkubb/salt-redis-formula>`_, but most of those are a bit simpler than the official ones found in `the official organization <https://github.com/saltstack-formulas>`_. You can find sample parameters for my formulae in the docs.

.. contents:: **Table of Contents**
   :depth: 1

General notes
-------------

See the full `SaltStack Formulas installation and usage instructions
<https://docs.saltstack.com/en/latest/topics/development/conventions/formulas.html>`_.

If you are interested in writing or contributing to formulas, please pay attention to the `Writing Formula Section
<https://docs.saltstack.com/en/latest/topics/development/conventions/formulas.html#writing-formulas>`_.

If you want to use this formula, please pay attention to the ``FORMULA`` file and/or ``git tag``,
which contains the currently released version. This formula is versioned according to `Semantic Versioning <http://semver.org/>`_.

See `Formula Versioning Section <https://docs.saltstack.com/en/latest/topics/development/conventions/formulas.html#versioning>`_ for more details.

If you need (non-default) configuration, please refer to:

- `how to configure the formula with map.jinja <map.jinja.rst>`_
- the ``pillar.example`` file
- the `Special notes`_ section

Special notes
-------------


Configuration
-------------
An example pillar is provided, please see `pillar.example`. Note that you do not need to specify everything by pillar. Often, it's much easier and less resource-heavy to use the ``parameters/<grain>/<value>.yaml`` files for non-sensitive settings. The underlying logic is explained in `map.jinja`.


Available states
----------------

The following states are found in this formula:

.. contents::
   :local:


``nextcloud``
^^^^^^^^^^^^^
*Meta-state*.

This installs the nextcloud package,
manages the nextcloud configuration file
and then starts the associated nextcloud service.


``nextcloud.package``
^^^^^^^^^^^^^^^^^^^^^
Installs the nextcloud package only.


``nextcloud.config``
^^^^^^^^^^^^^^^^^^^^
Manages the nextcloud service configuration.
Has a dependency on `nextcloud.package`_.


``nextcloud.config.base``
^^^^^^^^^^^^^^^^^^^^^^^^^



``nextcloud.config.file``
^^^^^^^^^^^^^^^^^^^^^^^^^



``nextcloud.service``
^^^^^^^^^^^^^^^^^^^^^
Starts the Nextcloud Cron service and enables it at boot time.
Has a dependency on `nextcloud.config`_.


``nextcloud.users``
^^^^^^^^^^^^^^^^^^^



``nextcloud.groups``
^^^^^^^^^^^^^^^^^^^^



``nextcloud.apps``
^^^^^^^^^^^^^^^^^^



``nextcloud.clean``
^^^^^^^^^^^^^^^^^^^
*Meta-state*.

Undoes everything performed in the ``nextcloud`` meta-state
in reverse order, i.e.
stops the service,
removes the configuration file and then
uninstalls the package.


``nextcloud.package.clean``
^^^^^^^^^^^^^^^^^^^^^^^^^^^
Removes the nextcloud package.
Has a dependency on `nextcloud.config.clean`_.


``nextcloud.config.clean``
^^^^^^^^^^^^^^^^^^^^^^^^^^
Removes the configuration of the nextcloud service and has a
dependency on `nextcloud.service.clean`_.


``nextcloud.service.clean``
^^^^^^^^^^^^^^^^^^^^^^^^^^^
Stops the Nextcloud Cron service and disables it at boot time.


``nextcloud.users.clean``
^^^^^^^^^^^^^^^^^^^^^^^^^



``nextcloud.groups.clean``
^^^^^^^^^^^^^^^^^^^^^^^^^^



``nextcloud.apps.clean``
^^^^^^^^^^^^^^^^^^^^^^^^




Contributing to this repo
-------------------------

Commit messages
^^^^^^^^^^^^^^^

**Commit message formatting is significant!**

Please see `How to contribute <https://github.com/saltstack-formulas/.github/blob/master/CONTRIBUTING.rst>`_ for more details.

pre-commit
^^^^^^^^^^

`pre-commit <https://pre-commit.com/>`_ is configured for this formula, which you may optionally use to ease the steps involved in submitting your changes.
First install  the ``pre-commit`` package manager using the appropriate `method <https://pre-commit.com/#installation>`_, then run ``bin/install-hooks`` and
now ``pre-commit`` will run automatically on each ``git commit``. ::

  $ bin/install-hooks
  pre-commit installed at .git/hooks/pre-commit
  pre-commit installed at .git/hooks/commit-msg

State documentation
~~~~~~~~~~~~~~~~~~~
There is a script that semi-autodocuments available states: ``bin/slsdoc``.

If a ``.sls`` file begins with a Jinja comment, it will dump that into the docs. It can be configured differently depending on the formula. See the script source code for details currently.

This means if you feel a state should be documented, make sure to write a comment explaining it.

Testing
-------

Linux testing is done with ``kitchen-salt``.

Requirements
^^^^^^^^^^^^

* Ruby
* Docker

.. code-block:: bash

   $ gem install bundler
   $ bundle install
   $ bin/kitchen test [platform]

Where ``[platform]`` is the platform name defined in ``kitchen.yml``,
e.g. ``debian-9-2019-2-py3``.

``bin/kitchen converge``
^^^^^^^^^^^^^^^^^^^^^^^^

Creates the docker instance and runs the ``nextcloud`` main state, ready for testing.

``bin/kitchen verify``
^^^^^^^^^^^^^^^^^^^^^^

Runs the ``inspec`` tests on the actual instance.

``bin/kitchen destroy``
^^^^^^^^^^^^^^^^^^^^^^^

Removes the docker instance.

``bin/kitchen test``
^^^^^^^^^^^^^^^^^^^^

Runs all of the stages above in one go: i.e. ``destroy`` + ``converge`` + ``verify`` + ``destroy``.

``bin/kitchen login``
^^^^^^^^^^^^^^^^^^^^^

Gives you SSH access to the instance for manual testing.

Todo
----
* manage log config
* manage 2fa
* manage theme config
* manage app/user config
