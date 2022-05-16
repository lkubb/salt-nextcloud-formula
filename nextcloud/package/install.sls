# -*- coding: utf-8 -*-
# vim: ft=sls

{%- set tplroot = tpldir.split('/')[0] %}
{%- from tplroot ~ "/map.jinja" import mapdata as nextcloud with context %}
{%- from tplroot ~ "/libtofs.jinja" import files_switch with context %}

{%- if "latest" != nextcloud.version %}
{%-   set pkg_lookup, version = nextcloud.lookup.pkg.exact, nextcloud.version %}
{%- else %}
{%-   set pkg_lookup, version = nextcloud.lookup.pkg.latest_major, nextcloud.version_major %}
{%- endif %}

{%- set tmp_base = salt["temp.dir"]() %}
{%- set pkg_src = pkg_lookup.source.format(version=version) %}
{%- set sig_src = pkg_lookup.sig.format(version=version) %}
{%- set tmp_pkg = tmp_base | path_join(salt["file.basename"](pkg_src)) %}
{%- set tmp_sig = tmp_base | path_join(salt["file.basename"](sig_src)) %}

{%- if nextcloud.required_states %}

include:
{%-   for req in nextcloud.required_states %}
  - {{ req }}
{%-   endfor %}
{%- endif %}

Nextcloud user/group are present:
  user.present:
    - name: {{ nextcloud.lookup.user }}
    - system: true
    - usergroup: {{ nextcloud.lookup.group == nextcloud.lookup.user }}
{%- if nextcloud.lookup.user != nextcloud.lookup.group %}
    - gid: {{ nextcloud.lookup.group }}
    - require:
      - group: {{ nextcloud.lookup.group }}
  group.present:
    - name: {{ nextcloud.lookup.group }}
    - system: true
{%- endif %}

{%- if nextcloud.additional_groups %}

# this is necessary for socket access, e.g.
# to redis or the database
Nextcloud user is member of additional groups:
  group.present:
    - names: {{ nextcloud.additional_groups }}
    - addusers:
      - {{ nextcloud.lookup.user }}
    - require:
      - Nextcloud user/group are present
{%-   for req in nextcloud.required_states %}
      - sls: {{ req }}
{%-   endfor %}
{%- endif %}

Nextcloud paths are setup:
  file.directory:
    - names:
      - {{ nextcloud.lookup.webroot }}
      - {{ nextcloud.lookup.datadir }}
    - user: {{ nextcloud.lookup.user }}
    - group: {{ nextcloud.lookup.group }}
    - mode: '0755'
    - makedirs: true
    - require:
      - Nextcloud user/group are present

Salt can manage gpg for Nextcloud:
  pkg.installed:
    - pkgs: {{ nextcloud.lookup.gpg.requirements | json }}
  cmd.run:
    - name: gpg --list-keys
    - unless:
      - test -d /root/.gnupg

Nextcloud signing key is present (from keyserver):
  gpg.present:
    - name: {{ nextcloud.lookup.gpg.fingerprint }}
    - keyserver: {{ nextcloud.lookup.gpg.keyserver }}
    - require:
      - Salt can manage gpg for Nextcloud

Nextcloud signing key is present (fallback):
  file.managed:
    - name: /tmp/nextcloud.asc
    - source: {{ files_switch(['nextcloud.asc'],
                              lookup='Nextcloud signing key is present (fallback)'
                 )
              }}
      - {{ nextcloud.lookup.gpg.official_src }}:
        - skip_verify: true
    - onfail:
      - Nextcloud signing key is present (from keyserver)
    - require:
      - Salt can manage gpg for Nextcloud
  module.run:
    - gpg.import_key:
      - filename: /tmp/nextcloud.asc
    - onfail:
      - Nextcloud signing key is present (from keyserver)
    - require:
      - file: /tmp/nextcloud.asc

# Fun fact:
# When the signature cannot be verified because the key is missing,
# `gpg.verify` just returns true. Huh. Unexpected.
# I should definitely write a function for the state module.
Nextcloud gpg key is actually present:
  module.run:
    - gpg.get_key:
      - fingerprint: {{ nextcloud.lookup.gpg.fingerprint }}

Nextcloud is downloaded:
  file.managed:
    - names:
      - {{ tmp_pkg }}:
        - source: {{ pkg_src }}
        - source_hash: {{ pkg_lookup.source_hash.format(version=version) }}
      - {{ tmp_sig }}:
        - source: {{ sig_src }}
        - skip_verify: true
    - require:
      - Nextcloud gpg key is actually present
{%- for req in nextcloud.required_states %}
      - sls: {{ req }}
{%- endfor %}
    # Do not overwrite existing Nextcloud installations.
    # Upgrades should be done with included updater.
    - unless:
      - fun: file.file_exists
        path: {{ nextcloud.lookup.webroot | path_join("occ") }}

Nextcloud signature is verified:
  module.run:
    - gpg.verify:
      - filename: {{ tmp_pkg }}
      - signature: {{ tmp_sig }}
    - require:
      - Nextcloud gpg key is actually present
      - Nextcloud is downloaded
    - unless:
      - fun: file.file_exists
        path: {{ nextcloud.lookup.webroot | path_join("occ") }}

Nextcloud is removed if signature verification failed:
  file.absent:
    - name: {{ tmp_base }}
    - onfail:
      - Nextcloud signature is verified

Nextcloud is extracted:
  archive.extracted:
    - name: {{ nextcloud.lookup.webroot }}
    - source: {{ tmp_pkg }}
    - user: {{ nextcloud.lookup.user }}
    - group: {{ nextcloud.lookup.group }}
    # just dump the files
    - options: --strip-components=1
    # this is needed because of the above
    - enforce_toplevel: false
    - require:
      - Nextcloud signature is verified
      - Nextcloud paths are setup
    - unless:
      - fun: file.file_exists
        path: {{ nextcloud.lookup.webroot | path_join("occ") }}

Nextcloud downloads are removed:
  file.absent:
    - name: {{ tmp_base }}
    - onchanges:
      - Nextcloud is extracted

Custom Nextcloud modules are synced:
  module.run:
    - saltutil.sync_all:
      - refresh: true
      - extmod_whitelist:
          modules:
            - nextcloud_server
          states:
            - nextcloud_server

occ is executable for the web user:
  file.managed:
    - name: {{ nextcloud.lookup.webroot | path_join("occ") }}
    - replace: false
    - mode: '0744'

{%- if nextcloud.update_auto.enabled %}

Nextcloud is up to date:
  nextcloud_server.uptodate:
    - no_backup: {{ nextcloud.update_auto.no_backup }}
    - webroot: {{ nextcloud.lookup.webroot }}
    - webuser: {{ nextcloud.lookup.user }}
    - require:
      - Nextcloud is extracted
      - Custom Nextcloud modules are synced
      - occ is executable for the web user
    - onlyif:
      - fun: nextcloud_server.is_installed
      - fun: nextcloud_server.check
        only_status: true
{%- endif %}

{%- if "systemd" == nextcloud.cron.daemon %}

Nextcloud background service is installed for systemd:
  file.managed:
    - name: {{ nextcloud.lookup.service.unit.format(name=nextcloud.lookup.service.name) }}
    - source: {{ files_switch(['nextcloudcron.service.j2'],
                              lookup='Nextcloud background service is installed for systemd'
                 )
              }}
    - mode: 644
    - user: root
    - group: {{ nextcloud.lookup.rootgroup }}
    - makedirs: True
    - template: jinja
    - context:
        nextcloud: {{ nextcloud | json }}
    - require:
      - Nextcloud is extracted
  module.run:
    - service.systemctl_reload: []
    - onchanges:
      - file: {{ nextcloud.lookup.service.unit.format(name=nextcloud.lookup.service.name) }}

Nextcloud background timer is installed for systemd:
  file.managed:
    - name: {{ nextcloud.lookup.service.unit_timer.format(name=nextcloud.lookup.service.name) }}
    - source: {{ files_switch(['nextcloudcron.timer.j2'],
                              lookup='Nextcloud background timer is installed for systemd'
                 )
              }}
    - mode: 644
    - user: root
    - group: {{ nextcloud.lookup.rootgroup }}
    - makedirs: True
    - template: jinja
    - context:
        nextcloud: {{ nextcloud | json }}
    - require:
      - Nextcloud background service is installed for systemd
  module.run:
    - service.systemctl_reload: []
    - onchanges:
      - file: {{ nextcloud.lookup.service.unit_timer.format(name=nextcloud.lookup.service.name) }}
{%- endif %}
