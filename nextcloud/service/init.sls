# vim: ft=sls

{#-
    Starts the Nextcloud Cron service and enables it at boot time.
    Has a dependency on `nextcloud.config`_.
#}

include:
  - .running
