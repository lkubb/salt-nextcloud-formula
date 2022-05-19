# -*- coding: utf-8 -*-
# vim: ft=sls

{%- set tplroot = tpldir.split('/')[0] %}
{%- from tplroot ~ "/map.jinja" import mapdata as nextcloud with context %}

{%- if nextcloud.users %}

Wanted users are absent:
  nextcloud_server.user_absent:
    - names: {{ nextcloud.users.keys() | list | json }}
    - webroot: {{ nextcloud.lookup.webroot }}
    - webuser: {{ nextcloud.lookup.user }}
{%- endif %}
