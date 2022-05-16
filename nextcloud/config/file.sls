# -*- coding: utf-8 -*-
# vim: ft=sls

{%- set tplroot = tpldir.split('/')[0] %}
{%- set sls_config_base = tplroot ~ '.config.base' %}
{%- from tplroot ~ "/map.jinja" import mapdata as nextcloud with context %}

include:
  - {{ sls_config_base }}

Nextcloud configuration is imported:
  nextcloud_server.config_imported:
    - config: {{ nextcloud.config | json }}
    - webroot: {{ nextcloud.lookup.webroot }}
    - webuser: {{ nextcloud.lookup.user }}
    - require:
      - sls: {{ sls_config_base }}
