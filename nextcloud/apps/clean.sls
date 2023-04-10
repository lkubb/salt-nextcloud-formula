# vim: ft=sls

{%- set tplroot = tpldir.split("/")[0] %}
{%- from tplroot ~ "/map.jinja" import mapdata as nextcloud with context %}

{%- if nextcloud.apps %}

Wanted apps are absent:
  nextcloud_server.app_removed:
    - names: {{ nextcloud.apps.keys() | list | json }}
    - webroot: {{ nextcloud.lookup.webroot }}
    - webuser: {{ nextcloud.lookup.user }}
{%- endif %}
