# -*- coding: utf-8 -*-
# vim: ft=sls

{%- set tplroot = tpldir.split('/')[0] %}
{%- set sls_config_file = tplroot ~ '.config.file' %}
{%- set sls_groups_managed = tplroot ~ '.groups.managed' %}
{%- from tplroot ~ "/map.jinja" import mapdata as nextcloud with context %}

include:
  # needed for enabling apps only for select groups
  - {{ sls_config_file }}
  - {{ sls_groups_managed }}

{%- for app, config in nextcloud.apps.items() %}

App {{ app }} is installed:
  nextcloud_server.app_installed:
    - name: {{ app }}
    - force: {{ config.get("force", False) }}
    - enabled: {{ config.get("enabled", True) }}
{%-   if config.get("groups") %}
    - groups: {{ config.groups | json }}
{%-   endif %}
    - allow_unstable: {{ config.get("allow_unstable", False) }}
    - webroot: {{ nextcloud.lookup.webroot }}
    - webuser: {{ nextcloud.lookup.user }}
    - require:
      - sls: {{ sls_config_file }}
{%-   if config.get("groups") %}
      - sls: {{ sls_groups_managed }}
{%-   endif %}
{%- endfor %}

{%- if nextcloud.apps_absent %}

Unwanted apps are removed:
  nextcloud_server.app_removed:
    - names: {{ nextcloud.apps_absent | json }}
    - webroot: {{ nextcloud.lookup.webroot }}
    - webuser: {{ nextcloud.lookup.user }}
    # This actually requires the base config. Do not overcomplicate though.
    - require:
      - sls: {{ sls_config_file }}
{%- endif %}
