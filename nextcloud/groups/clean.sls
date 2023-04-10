# vim: ft=sls

{%- set tplroot = tpldir.split("/")[0] %}
{%- from tplroot ~ "/map.jinja" import mapdata as nextcloud with context %}

{%- if nextcloud.groups %}

Wanted groups are absent:
  nextcloud_server.group_absent:
    - names: {{ nextcloud.groups.keys() | list | json }}
    - webroot: {{ nextcloud.lookup.webroot }}
    - webuser: {{ nextcloud.lookup.user }}
{%- endif %}
