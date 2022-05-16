# -*- coding: utf-8 -*-
# vim: ft=sls

{%- set tplroot = tpldir.split('/')[0] %}
{%- from tplroot ~ "/map.jinja" import mapdata as nextcloud with context %}

{%- if "systemd" == nextcloud.cron.daemon %}

nextcloud-service-clean-service-dead:
  service.dead:
    - name: {{ nextcloud.lookup.service.name }}.timer
    - enable: False

{%- elif "cron" == nextcloud.cron.daemon %}

nextcloud-service-clean-cron-absent:
  cron.absent:
    - name: >-
        {{ salt["cmd.run_stdout"]("command -v php", runas=nextcloud.lookup.user) or "php" }}
{%-   if "apcu" == nextcloud.caching.local %}
        --define apc.enable_cli=1
{%-   endif %}
        -f '{{ nextcloud.lookup.webroot | path_join("cron.php") }}'
    - user: {{ nextcloud.lookup.user }}

{%- else %}

No system service was installed for Nextcloud:
  test.nop: []
{%- endif %}
