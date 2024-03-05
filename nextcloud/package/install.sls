# vim: ft=sls

{%- set tplroot = tpldir.split("/")[0] %}
{%- from tplroot ~ "/map.jinja" import mapdata as nextcloud with context %}
{%- from tplroot ~ "/libtofsstack.jinja" import files_switch with context %}

{%- if "latest" != nextcloud.version %}
{%-   set pkg_lookup, version = nextcloud.lookup.pkg.exact, nextcloud.version %}
{%- else %}
{%-   set pkg_lookup, version = nextcloud.lookup.pkg.latest_major, nextcloud.version_major %}
{%- endif %}

{%- set is_installed =
        salt["file.file_exists"](nextcloud.lookup.webroot | path_join("occ")) and
        salt["nextcloud_server.is_installed"](webroot=nextcloud.lookup.webroot, webuser=nextcloud.lookup.user)
%}

{%- if nextcloud.required_states_preinstall and not is_installed %}

include:
{%-   for req in nextcloud.required_states_preinstall %}
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
{%-   if not is_installed %}
{%-     for req in nextcloud.required_states_preinstall %}
      - sls: {{ req }}
{%-     endfor %}
{%-   endif %}
{%- endif %}

Nextcloud paths are setup:
  file.directory:
    - names:
      - {{ nextcloud.lookup.webroot }}
      - {{ nextcloud.lookup.datadir }}:
        - mode: '0770'
        - unless:
          # Check if path is somewhere on network share, might not be able to ensure ownership.
          # @TODO proper check/config
          - >-
              test -d '{{ nextcloud.lookup.datadir }}' &&
              df -P '{{ nextcloud.lookup.datadir }}' |
              awk 'BEGIN {e=1} $NF ~ /^\/.+/ { e=0 ; print $1 ; exit } END { exit e }'
    - user: {{ nextcloud.lookup.user }}
    - group: {{ nextcloud.lookup.group }}
    - mode: '0755'
    - makedirs: true
    - require:
      - Nextcloud user/group are present

Salt can apply Nextcloud formula:
  pkg.installed:
    - pkgs: {{ nextcloud.lookup.formula_reqs | json }}

Nextcloud signing key is present:
  gpg.present:
    - name: {{ nextcloud.lookup.gpg.fingerprint[-16:] }}
    - keyserver: {{ nextcloud.lookup.gpg.keyserver }}
    - source: {{ files_switch(
                    ["nextcloud.asc"],
                    config=nextcloud,
                    lookup="Nextcloud signing key is present",
                 )
              }}
      - {{ nextcloud.lookup.gpg.official_src }}
    - require:
      - Salt can apply Nextcloud formula

Nextcloud is extracted:
  archive.extracted:
    - name: {{ nextcloud.lookup.webroot }}
    - source: {{ pkg_lookup.source.format(version=version) }}
    - source_hash: {{ pkg_lookup.source_hash.format(version=version) }}
    - signature: {{ pkg_lookup.sig.format(version=version) }}
    - signed_by_any: {{ nextcloud.lookup.gpg.fingerprint | json }}
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
    - require:
      - Nextcloud signing key is present

Custom Nextcloud modules are synced:
  saltutil.sync_all:
    - refresh: true
    - unless:
      - '{{ ("nextcloud_server" in salt["saltutil.list_extmods"]().get("states", [])) | lower }}'

occ is executable for the web user:
  file.managed:
    - name: {{ nextcloud.lookup.webroot | path_join("occ") }}
    - replace: false
    - mode: '0744'
    - require:
      - Nextcloud is extracted

{%- if grains | traverse("selinux:enabled") %}

SELinux policies for Nextcloud are present:
  selinux.fcontext_policy_present:
    - names:
{%-   for path, typ in nextcloud.selinux.policy.items() %}
{%-     if typ is none %}
{%-       continue %}
{%-     elif not path.startswith("/") %}
{%-       set path = nextcloud.lookup.webroot | path_join(path) %}
{%-     endif %}
      - {{ path | json }}:
        - sel_type: {{ typ }}
{%-   endfor %}
    - require:
      - Nextcloud is extracted

SELinux policies for Nextcloud are applied:
  selinux.fcontext_policy_applied:
    - names:
      - {{ nextcloud.lookup.webroot }}
{%-   for path, typ in nextcloud.selinux.policy.items() %}
{%-     if typ is none or not path.startswith("/") %}
{%-       continue %}
{%-     endif %}
      - {{ path | json }}
{%-   endfor %}
    - recursive: true
    - require:
      - SELinux policies for Nextcloud are present

SELinux booleans for Nextcloud are managed:
  selinux.boolean:
    - names:
{%-   for name, val in nextcloud.selinux.boolean.items() %}
{%-     if val is none %}
{%-       continue %}
{%-     endif %}
      - {{ name }}:
        - value: {{ val | to_bool }}
{%-   endfor %}
{%- endif %}

{%- set logfile = nextcloud.config.system.get("logfile", "nextcloud.log") %}
{%- if not logfile.startswith("/") %}
{%-   set logfile = nextcloud.lookup.datadir | path_join(logfile) %}
{%- endif %}
{%- if not logfile.startswith(nextcloud.lookup.datadir) %}

Nextcloud log dest dir is present:
  file.directory:
    - name: {{ salt["file.dirname"](logfile) }}
    # TODO make this configurable, hardcoded for now
    - user: www-data
    - group: www-data
{%- endif %}

{%- if nextcloud.update_auto.enabled %}

Nextcloud is up to date:
  nextcloud_server.uptodate:
    - max_version: {{ version or "null" }}
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
    - source: {{ files_switch(
                    ["nextcloudcron.service", "nextcloudcron.service.j2"],
                    config=nextcloud,
                    lookup="Nextcloud background service is installed for systemd",
                 )
              }}
    - mode: '0644'
    - user: root
    - group: {{ nextcloud.lookup.rootgroup }}
    - makedirs: true
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
    - source: {{ files_switch(
                    ["nextcloudcron.timer", "nextcloudcron.timer.j2"],
                    config=nextcloud,
                    lookup="Nextcloud background timer is installed for systemd"
                 )
              }}
    - mode: '0644'
    - user: root
    - group: {{ nextcloud.lookup.rootgroup }}
    - makedirs: true
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
