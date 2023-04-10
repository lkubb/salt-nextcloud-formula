# vim: ft=sls

{#-
    *Meta-state*.

    This installs the nextcloud package,
    manages the nextcloud configuration file
    and then starts the associated nextcloud service.
#}

include:
  - .package
  - .config
  - .service
  - .users
  - .groups
  - .apps
