# vim: ft=sls

{#-
    *Meta-state*.

    Undoes everything performed in the ``nextcloud`` meta-state
    in reverse order, i.e.
    stops the service,
    removes the configuration file and then
    uninstalls the package.
#}

include:
  - .apps.clean
  - .groups.clean
  - .users.clean
  - .service.clean
  - .config.clean
  - .package.clean
