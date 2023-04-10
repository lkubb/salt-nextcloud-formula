# vim: ft=sls

{%- set tplroot = tpldir.split("/")[0] %}
{%- set sls_config_file = tplroot ~ ".config.file" %}
{%- from tplroot ~ "/map.jinja" import mapdata as nextcloud with context %}

include:
  - {{ sls_config_file }}

{%- set delusers = nextcloud.users_absent %}

{%- for user, config in nextcloud.users.items() %}
{%-   if "absent" != config.get("state") %}

User {{ user }} is present:
  nextcloud_server.user_present:
    - name: {{ user }}
    - enabled: {{ "enabled" == config.get("state", "enabled") }}
{%-     if config.get("init_password_pillar") %}
    - init_password_pillar: {{ config.init_password_pillar }}
{%-     else %}
{#- This is intended to fail if neither has been set. #}
    - init_password: {{ config.init_password }}
{%-     endif %}
    - webroot: {{ nextcloud.lookup.webroot }}
    - webuser: {{ nextcloud.lookup.user }}
    - require:
      - sls: {{ sls_config_file }}

{%-   else %}
{%-     if user not in delusers %}
{%-       do delusers.append(user) %}
{%-     endif %}
{%-   endif %}
{%- endfor %}

{%- if delusers %}

Unwanted users are absent:
  nextcloud_server.user_absent:
    - names: {{ delusers | json }}
    - webroot: {{ nextcloud.lookup.webroot }}
    - webuser: {{ nextcloud.lookup.user }}
    - require:
      - sls: {{ sls_config_file }}
{%- endif %}
