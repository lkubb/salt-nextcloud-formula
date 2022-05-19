# -*- coding: utf-8 -*-
# vim: ft=sls

{%- set tplroot = tpldir.split('/')[0] %}
{%- set sls_users_managed = tplroot ~ '.users.managed' %}
{%- from tplroot ~ "/map.jinja" import mapdata as nextcloud with context %}

include:
  - {{ sls_users_managed }}

{%- for group, config in nextcloud.groups.items() %}

Group {{ group }} is present:
  nextcloud_server.group_present:
    - name: {{ group }}
{%-   if config.get("members") %}
    - addusers: {{ config.members | json }}
{%-   endif %}
{%-   if config.get("unwanted") %}
    - delusers: {{ config.unwanted | json }}
{%-   endif %}
    - webroot: {{ nextcloud.lookup.webroot }}
    - webuser: {{ nextcloud.lookup.user }}
    - require:
      - sls: {{ sls_users_managed }}
{%- endfor %}

{%- if nextcloud.groups_absent %}

Unwanted groups are absent:
  nextcloud_server.group_absent:
    - names: {{ nextcloud.groups_absent | json }}
    - webroot: {{ nextcloud.lookup.webroot }}
    - webuser: {{ nextcloud.lookup.user }}
    # This actually requires the base config. Do not overcomplicate though.
    - require:
      - sls: {{ sls_users_managed }}
{%- endif %}
