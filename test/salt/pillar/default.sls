# vim: ft=yaml
# yamllint disable rule:line-length
---
nextcloud:
  lookup:
    master: template-master
    # Just for testing purposes
    winner: lookup
    added_in_lookup: lookup_value
    config: 'config/config.php'
    datadir: data
    formula_reqs:
      - tar
      - gpg
      - bzip2
    gpg:
      fingerprint: 28806A878AE423A28372792ED75899B9A724937A
      keyid: D75899B9A724937A
      keyserver: keys.openpgp.org
      official_src: https://nextcloud.com/nextcloud.asc
    group: www-data
    pkg:
      exact:
        sig: https://download.nextcloud.com/server/releases/nextcloud-{version}.tar.bz2.asc
        source: https://download.nextcloud.com/server/releases/nextcloud-{version}.tar.bz2
        source_hash: https://download.nextcloud.com/server/releases/nextcloud-{version}.tar.bz2.sha512
      latest_major:
        sig: https://download.nextcloud.com/server/releases/latest-{version}.tar.bz2.asc
        source: https://download.nextcloud.com/server/releases/latest-{version}.tar.bz2
        source_hash: https://download.nextcloud.com/server/releases/latest-{version}.tar.bz2.sha512
    redis_group: redis
    service:
      name: nextcloudcron
      unit: /etc/systemd/system/{name}.service
      unit_timer: /etc/systemd/system/{name}.timer
    user: www-data
    webroot: /var/www/nextcloud
  additional_groups: []
  apps: {}
  apps_absent: []
  caching:
    distributed: false
    local: apcu
    locking: false
  config: {}
  cron:
    daemon: systemd
    timer: 5
  groups: {}
  groups_absent: []
  manage_groups_auto: true
  required_states_preinstall: []
  selinux:
    boolean:
      httpd_can_connect_ldap: false
      httpd_can_network_connect: false
      httpd_can_network_connect_db: false
      httpd_can_network_memcache: false
      httpd_can_sendmail: false
      httpd_unified: false
      httpd_use_cifs: false
      httpd_use_fusefs: false
      httpd_use_gpg: false
    policy:
      .htaccess: httpd_sys_rw_content_t
      .user.ini: httpd_sys_rw_content_t
      3rdparty/aws/aws-sdk-php/src/data/logs(/.*)?: httpd_sys_rw_content_t
      apps(/.*)?: httpd_sys_rw_content_t
      config(/.*)?: httpd_sys_rw_content_t
      data(/.*)?: httpd_sys_rw_content_t
  setup_method: cli
  setup_vars:
    admin_pass: correct horse battery staple
    admin_pass_pillar: ''
    admin_user: admin
    database: sqlite
    database_host: ''
    database_name: ''
    database_pass: ''
    database_pass_pillar: ''
    database_user: ''
  update_auto:
    enabled: true
    no_backup: false
  users: {}
  users_absent: []
  version: latest
  version_major: 24
  web_install_use_defaults: false

  tofs:
    # The files_switch key serves as a selector for alternative
    # directories under the formula files directory. See TOFS pattern
    # doc for more info.
    # Note: Any value not evaluated by `config.get` will be used literally.
    # This can be used to set custom paths, as many levels deep as required.
    files_switch:
      - any/path/can/be/used/here
      - id
      - roles
      - osfinger
      - os
      - os_family
    # All aspects of path/file resolution are customisable using the options below.
    # This is unnecessary in most cases; there are sensible defaults.
    # Default path: salt://< path_prefix >/< dirs.files >/< dirs.default >
    #         I.e.: salt://nextcloud/files/default
    # path_prefix: template_alt
    # dirs:
    #   files: files_alt
    #   default: default_alt
    # The entries under `source_files` are prepended to the default source files
    # given for the state
    # source_files:
    #   nextcloud-config-file-file-managed:
    #     - 'example_alt.tmpl'
    #     - 'example_alt.tmpl.jinja'

    # For testing purposes
    source_files:
      nextcloud-config-file-file-managed:
        - 'example.tmpl.jinja'

  # Just for testing purposes
  winner: pillar
  added_in_pillar: pillar_value
