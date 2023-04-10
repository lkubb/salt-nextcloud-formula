# vim: ft=sls

{%- set tplroot = tpldir.split("/")[0] %}
{%- set sls_config_file = tplroot ~ ".config.file" %}
{%- from tplroot ~ "/map.jinja" import mapdata as nextcloud with context %}

include:
  - {{ sls_config_file }}

Nextcloud Cron is running:
{%- if "systemd" == nextcloud.cron.daemon %}
  service.running:
    - name: {{ nextcloud.lookup.service.name }}.timer
    - enable: true
    - require:
      - sls: {{ sls_config_file }}

{%- elif "cron" == nextcloud.cron.daemon %}
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
  test.nop: []
{%- endif %}
