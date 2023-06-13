# vim: ft=sls

{%- set tplroot = tpldir.split("/")[0] %}
{%- set sls_package_install = tplroot ~ ".package.install" %}
{%- from tplroot ~ "/map.jinja" import mapdata as nextcloud with context %}
{%- from tplroot ~ "/libtofsstack.jinja" import files_switch with context %}

include:
  - {{ sls_package_install }}

{%- if "web" == nextcloud.setup_method %}

Nextcloud installation autoconfig is present:
  file.managed:
    - name: {{ nextcloud.lookup.webroot | path_join("config", "autoconfig.php") }}
    - source: {{ files_switch(
                    ["autoconfig.php", "autoconfig.php.j2"],
                    config=nextcloud,
                    lookup="Nextcloud installation autoconfig is present",
                 )
              }}
    - mode: '0640'
    - user: {{ nextcloud.lookup.user }}
    - group: {{ nextcloud.lookup.group }}
    - makedirs: true
    - template: jinja
    - context:
        nextcloud: {{ nextcloud | json }}
    - require:
      - sls: {{ sls_package_install }}
    - unless:
      - fun: nextcloud_server.is_installed
        webroot: {{ nextcloud.lookup.webroot }}
        webuser: {{ nextcloud.lookup.user }}

# When opting for the web installer, the base setup
# needs to be finished manually and all states depending
# on a functional Nextcloud installation should fail.
Nextcloud web installer needs to be run:
  cmd.run:
    - name: 'false'
    - onchanges:
      - Nextcloud installation autoconfig is present

{%- else %}

Nextcloud installation is initialized:
  nextcloud_server.installed:
{%-   for param in [
        "database",
        "database_name",
        "database_host",
        "database_user",
        "database_pass",
        "database_pass_pillar",
        "admin_user",
        "admin_pass",
        "admin_pass_pillar",
      ]
%}
{%-     if nextcloud.setup_vars[param] %}
    - {{ param }}: {{ nextcloud.setup_vars[param] }}
{%-     endif %}
{%-   endfor %}
{#- Allow empty passwords for the database user #}
{%-   if not nextcloud.setup_vars.database_pass_pillar and nextcloud.setup_vars.database_pass == "" %}
    - database_pass: ''
{%-   endif %}
    - datadir: {{ nextcloud.lookup.datadir }}
    - webroot: {{ nextcloud.lookup.webroot }}
    - webuser: {{ nextcloud.lookup.user }}
    - require:
      - Nextcloud is extracted
      - Custom Nextcloud modules are synced
      - occ is executable for the web user
{%- endif %}

# At this point, Nextcloud should not complain about misconfiguration.
Nextcloud base setup is finished (checkpoint):
  cmd.run:
    - name: 'false'
    - unless:
      - fun: nextcloud_server.check
        only_status: true
    - require:
{%- if "web" == nextcloud.setup_method %}
      - Nextcloud web installer needs to be run
{%- else %}
      - Nextcloud installation is initialized
{%- endif %}
