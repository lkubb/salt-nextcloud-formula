# vim: ft=sls

{#-
    Removes the configuration of the nextcloud service and has a
    dependency on `nextcloud.service.clean`_.
#}

{%- set tplroot = tpldir.split("/")[0] %}
{%- set sls_service_clean = tplroot ~ ".service.clean" %}
{%- from tplroot ~ "/map.jinja" import mapdata as nextcloud with context %}

include:
  - {{ sls_service_clean }}

Nextcloud Server configuration is absent:
  file.absent:
    - name: {{ nextcloud.lookup.webroot | path_join(nextcloud.lookup.config) }}
    - require:
      - sls: {{ sls_service_clean }}
