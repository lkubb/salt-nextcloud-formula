# vim: ft=sls

{#-
    Stops the Nextcloud Cron service and disables it at boot time.
#}

{%- set tplroot = tpldir.split("/")[0] %}
{%- from tplroot ~ "/map.jinja" import mapdata as nextcloud with context %}

Nextcloud Cron is dead:
{%- if "systemd" == nextcloud.cron.daemon %}
  service.dead:
    - name: {{ nextcloud.lookup.service.name }}.timer
    - enable: false

{%- elif "cron" == nextcloud.cron.daemon %}
  cron.absent:
    - name: >-
        {{ salt["cmd.run_stdout"]("command -v php", runas=nextcloud.lookup.user) or "php" }}
{%-   if "apcu" == nextcloud.caching.local %}
        --define apc.enable_cli=1
{%-   endif %}
        -f '{{ nextcloud.lookup.webroot | path_join("cron.php") }}'
    - user: {{ nextcloud.lookup.user }}

{%- else %}
  test.nop: []
{%- endif %}
