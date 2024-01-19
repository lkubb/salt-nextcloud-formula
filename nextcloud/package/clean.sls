# vim: ft=sls

{#-
    Removes the nextcloud package.
    Has a dependency on `nextcloud.config.clean`_.
#}

{%- set tplroot = tpldir.split("/")[0] %}
{%- set sls_config_clean = tplroot ~ ".config.clean" %}
{%- from tplroot ~ "/map.jinja" import mapdata as nextcloud with context %}

include:
  - {{ sls_config_clean }}

{%- if "systemd" == nextcloud.cron.daemon %}

Nextcloud systemd unit files are absent:
  file.absent:
    - names:
      - {{ nextcloud.lookup.service.unit.format(name=nextcloud.lookup.service.name) }}
      - {{ nextcloud.lookup.service.unit_timer.format(name=nextcloud.lookup.service.name) }}
{%- endif %}

# Leave data dir to prevent accidental data loss.
# This does not work currently and only leaves the data folder.
# v3005 will have exclude funtionality.
# Until then, just jinja-comment this out: {#
Nextcloud installation is absent:
{%- if nextcloud.lookup.datadir.startswith(nextcloud.lookup.webroot) %}
  file.tidied:
    - name: {{ nextcloud.lookup.webroot }}
    - matches:
      - ^(?!{{ nextcloud.lookup.datadir[(nextcloud.lookup.webroot | length)+1:].split("/")[0] }}).*
    - rmdirs: true
    - require:
      - sls: {{ sls_config_clean }}
{%- else %}
  file.absent:
    - name: {{ nextcloud.lookup.webroot }}
{%- endif %}
#}
# This does not remove the user since usually,
# it is the default user used by the http server.

{%- if grains | traverse("selinux:enabled") %}

SELinux policies for Nextcloud are absent:
  selinux.fcontext_policy_absent:
    - names:
{%-   for path, typ in nextcloud.selinux.policy.items() %}
{%-     if typ is none %}
{%-       continue %}
{%-     elif not path.startswith("/") %}
{%-       set path = nextcloud.lookup.webroot | path_join(path) %}
{%-     endif %}
      - {{ path | json }}:
{%-   endfor %}

SELinux booleans for Nextcloud are managed:
  selinux.boolean:
    - names:
{%-   for name, val in nextcloud.selinux.boolean.items() %}
{%-     if val is none %}
{%-       continue %}
{%-     endif %}
      - {{ name }}:
        - value: false
{%-   endfor %}
{%- endif %}
