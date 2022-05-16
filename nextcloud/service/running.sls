# -*- coding: utf-8 -*-
# vim: ft=sls

{%- set tplroot = tpldir.split('/')[0] %}
{%- set sls_config_file = tplroot ~ '.config.file' %}
{%- from tplroot ~ "/map.jinja" import mapdata as nextcloud with context %}

include:
  - {{ sls_config_file }}

{%- if "systemd" == nextcloud.cron.daemon %}

nextcloud-service-running-service-running:
  service.running:
    - name: {{ nextcloud.lookup.service.name }}.timer
    - enable: True
    - require:
      - sls: {{ sls_config_file }}

{%- elif "cron" == nextcloud.cron.daemon %}

nextcloud-service-running-cron-present:
  cron.present:
# {#- "command -v php" or php is necessary if php is just setup by including its state here
#    since jinja parsing is done before running any states #}
    - name: >-
        {{ salt["cmd.run_stdout"]("which php", runas=nextcloud.lookup.user) or "php" }}
{%-   if "apcu" == nextcloud.caching.local %}
        --define apc.enable_cli=1
{%-   endif %}
        -f '{{ nextcloud.lookup.webroot | path_join("cron.php") }}'
    - user: {{ nextcloud.lookup.user }}
    - minute: {{ nextcloud.cron.timer }}
    - require:
      - sls: {{ sls_config_file }}

{%- else %}

nextcloud-service-running-test-nop:
  test.nop: []
{%- endif %}
