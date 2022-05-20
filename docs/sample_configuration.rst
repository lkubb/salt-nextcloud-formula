.. _sample_config:

Example Configurations for Other Formulae
=========================================

PHP
---

.. code-block:: yaml

  cli:
    ini:
      memory_limit: 512M
      opcache:
        opcache.enable: 1
        opcache.interned_strings_buffer: 16
        opcache.max_accelerated_files: 10000
        opcache.memory_consumption: 128
        opcache.save_comments: 1
        opcache.revalidate_freq: 1
      post_max_filesize: 16G
      upload_max_filesize: 16G
      max_input_time: 3600
      max_execution_time: 3600
  config: {}
  fpm:
    enable: true
    ini:
      memory_limit: 512M
      opcache:
        opcache.enable: 1
        opcache.interned_strings_buffer: 16
        opcache.max_accelerated_files: 10000
        opcache.memory_consumption: 128
        opcache.save_comments: 1
        opcache.revalidate_freq: 1
        # per POST, can be several files
      post_max_filesize: 16G
        # per file
      upload_max_filesize: 16G
      max_input_time: 3600
      max_execution_time: 3600
    pools:
      nextcloud:
        pm.max_children: 53
        pm.start_servers: 13
        pm.min_spare_servers: 13
        pm.max_spare_servers: 39
        env[HOSTNAME]: $HOSTNAME
        env[PATH]: /usr/local/bin:/usr/bin:/bin
        env[TMP]: /tmp
        env[TMPDIR]: /tmp
        env[TEMP]: /tmp
    remove_default_pool: true
    service:
      harden: true
      requires_mount: []
      wants: []
  modules:
    - apcu
    - bcmath
    - bz2
    # - ctype
    - curl
    # - dom
    # - exif
    - gd
    - gmp
    - imagick
    - intl
    - mbstring
    - mysql
    - smbclient
    - xml
    - zip
  use_external_repo: true
  version: '8.1'

MariaDB
-------

.. code-block:: yaml

  config:
    client:
      default-character-set: utf8mb4
    mysqld:
      character_set_server: utf8mb4
      collation_server: utf8mb4_general_ci
      transaction_isolation: READ-COMMITTED
      binlog_format: ROW
      innodb_large_prefix: 'on'
      innodb_file_format: barracuda
      innodb_file_per_table: 1
    server:
      skip_name_resolve: true
      innodb_buffer_pool_size: 128M
      innodb_buffer_pool_instances: 1
      innodb_flush_log_at_trx_commit: 2
      innodb_log_buffer_size: 32M
      innodb_max_dirty_pages_pct: 90
      query_cache_type: 1
      query_cache_limit: 2M
      query_cache_min_res_unit: 2k
      query_cache_size: 64M
      tmp_table_size: 64M
      max_heap_table_size: 64M
      slow_query_log: 1
      slow_query_log_file: /var/log/mysql/slow.log
      long_query_time: 1
  databases:
    nextcloud:
      charset: utf8mb4
      collate: utf8mb4_general_ci
  databases_absent: []
  users:
    www-data:
      grants:
        'nextcloud.*':
          - all privileges
      socket: true
  users_absent: []

Redis
-----

.. code-block:: yaml

  lookup:
    socket:
      perms: '770'
  config: {}
  port: 0
  socket: true
  system:
    overcommit_memory: true
    transparent_huge_pages: false
  service:
    protect_system_full: true
