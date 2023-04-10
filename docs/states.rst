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


``nextcloud.apps``
^^^^^^^^^^^^^^^^^^



``nextcloud.groups``
^^^^^^^^^^^^^^^^^^^^



``nextcloud.users``
^^^^^^^^^^^^^^^^^^^



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
Has a depency on `nextcloud.config.clean`_.


``nextcloud.config.clean``
^^^^^^^^^^^^^^^^^^^^^^^^^^
Removes the configuration of the nextcloud service and has a
dependency on `nextcloud.service.clean`_.


``nextcloud.service.clean``
^^^^^^^^^^^^^^^^^^^^^^^^^^^
Stops the Nextcloud Cron service and disables it at boot time.


``nextcloud.apps.clean``
^^^^^^^^^^^^^^^^^^^^^^^^



``nextcloud.groups.clean``
^^^^^^^^^^^^^^^^^^^^^^^^^^



``nextcloud.users.clean``
^^^^^^^^^^^^^^^^^^^^^^^^^



