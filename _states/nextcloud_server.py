"""
Nextcloud Server salt state module
==================================

Manage Nextcloud Server installation, upgrade and configuration
with Salt, using ``occ`` and the inbuilt updater.
"""

import logging
from pathlib import Path

import salt.utils.dictdiffer
import salt.utils.json
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

__virtualname__ = "nextcloud_server"


def __virtual__():
    return __virtualname__


def installed(
    name=None,
    database=None,
    database_name=None,
    database_host=None,
    database_user=None,
    database_pass=None,
    database_pass_pillar=None,
    admin_user=None,
    admin_pass=None,
    admin_pass_pillar=None,
    admin_email=None,
    datadir=None,
    webroot=None,
    webuser=None,
):
    """
    Make sure an the Nextcloud installation is finished, i.e.
    the installation wizard has been run successfully once.

    This will not update the configuration parameters if Nextcloud
    reports it is already installed. You will need to use the
    appropriate configuration state, while migrating a database
    to a different type is possible using the execution module
    (see ``nextcloud_server.db_convert_type).

    name
        Unused. Needs to be here because of Salt architecture.

    database
        Supported database type [sqlite (CE), mysql, pgsql, oci (EE)].
        Defaults to ``sqlite``.

    database_name
        Name of the database. Defaults to ``nextcloud``.
        Ignored for database = ``sqlite``.

    database_host
        Hostname of the database. Defaults to ``localhost``.
        Ignored for database = ``sqlite``.

    database_user
        User name to connect to the database. Defaults to ``nextcloud``.
        Ignored for database = ``sqlite``.

    database_pass
        Password of the database user. Better use ``database_pass_pillar``.
        Ignored for database = ``sqlite``.

        Note:
            Try to avoid special characters that might interfere with
            shell parsing:
            To prevent the password being logged and since ``maintenance:install``
            does not provide the option to read environment variables itself,
            the password is passed as --database-pass "$NC_DB_PASS".

    database_pass_pillar
        Pillar to look up the database password in. See note on ``database_pass``.
        Ignored for database = ``sqlite``.

    database_table_space
        Table space of the database. Ignored for database != ``oci``.

    admin_user
        User name of the admin account. Defaults to "admin".

    admin_pass
        Password of the admin account. Better use ``admin_pass_pillar``.

        Note:
            Try to avoid special characters that might interfere with
            shell parsing:
            To prevent the password being logged and since ``maintenance:install``
            does not provide the option to read environment variables itself,
            the password is passed as --admin-pass "$NC_ADMIN_PASS".

    admin_pass_pillar
        Pillar to look up the admin password in. See note on ``admin_pass``.

    admin_email
        E-Mail of the admin account.

    datadir
        Path to data directory. Default: ``<webroot>/data``

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    try:
        if __salt__["nextcloud_server.is_installed"](webroot=webroot, webuser=webuser):
            ret["comment"] = "Nextcloud installation is already finished."
        elif __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "Nextcloud would have been installed."
            ret["changes"] = {"installed": "Nextcloud"}
        elif __salt__["nextcloud_server.install"](
            database=database,
            database_name=database_name,
            database_host=database_host,
            database_user=database_user,
            database_pass=database_pass,
            database_pass_pillar=database_pass_pillar,
            admin_user=admin_user,
            admin_pass=admin_pass,
            admin_pass_pillar=admin_pass_pillar,
            admin_email=admin_email,
            datadir=datadir,
            webroot=webroot,
            webuser=webuser,
        ):
            ret["comment"] = "Nextcloud has been installed."
            ret["changes"] = {"installed": "Nextcloud"}
        else:
            # this should never hit because errors are raised
            ret["result"] = False
            ret["comment"] = "Something went wrong while installing Nextcloud."
    except (SaltInvocationError, CommandExecutionError) as e:
        ret["result"] = False
        ret["comment"] = str(e)

    return ret


def uptodate(
    name=None,
    max_version=None,
    no_backup=False,
    ensure_apc=True,
    webroot=None,
    webuser=None,
):
    """
    Make sure the Nextcloud base system is up to date.

    name
        Unused. Needs to be here because of Salt architecture.

    max_version
        Restrict updates to this maximum version, if specified.
        Passing only parts will allow updates to point releases,
        e.g. when current = 23.0.3, specifying ``max_version: 23``
        will allow updates to 23.0.4, but not 24.0.0.
        ``max_version: 23.0`` would work as well.

    no_backup
        Skip backup of current Nextcloud version (the installation files).
        Defaults to False.

    ensure_apc
        APCu is disabled by default on CLI which could cause issues with
        Nextcloud’s command line based updater. ``apc.enable_cli`` needs
        to be set to ``1`` in the CLI ``php.ini``. This ensures the value
        is set by passing it as a parameter to the ``php`` executable.
        Defaults to True.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    # Maybe implement some kind of notification capability on
    # upgrade failures or check if there is some simple inbuilt method. @TODO

    # Also, consider upgrading db indices etc. somewhere. @TODO

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    try:
        if __salt__["nextcloud_server.is_uptodate"](
            max_version=max_version, webroot=webroot, webuser=webuser
        ):
            ret["comment"] = "Nextcloud is already up to date."
            if max_version is not None:
                ret[
                    "comment"
                ] += " Updates are restricted to versions matching '{}'.".format(
                    max_version
                )
            return ret

        update_version = __salt__["nextcloud_server.update_check"](
            webroot=webroot, webuser=webuser
        )["Nextcloud"]

        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "Nextcloud would have been updated to version {}.".format(
                update_version
            )
            ret["changes"] = {"upgraded": update_version}
        # @TODO this fails with NFS
        # so, correct procedure would be:
        # catch exceptions, check nextcloud_server.status
        # if version is reported as new one, continue.
        # then run nextcloud_server.finish_upgrade
        elif __salt__["nextcloud_server.upgrade"](
            no_backup=no_backup, ensure_apc=ensure_apc, webroot=webroot, webuser=webuser
        ):
            ret["comment"] = "Nextcloud has been updated to version {}.".format(
                update_version
            )
            ret["changes"] = {"upgraded": update_version}
        else:
            # this should not hit, errors are raised
            ret["result"] = False
            ret[
                "comment"
            ] = "Something went wrong while upgrading Nextcloud to version '{}'.".format(
                update_version
            )
    except (SaltInvocationError, CommandExecutionError) as e:
        ret["result"] = False
        ret["comment"] = str(e)

    return ret


def app_removed(name, webroot=None, webuser=None):
    """
    Make sure an app is removed.

    name
        Name of the app.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    try:
        current = __salt__["nextcloud_server.app_list"](
            webroot=webroot, webuser=webuser
        )
        is_installed = name in current["enabled"] or name in current["disabled"]

        if not is_installed:
            ret["comment"] = "App '{}' is already removed.".format(name)
        elif __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "App '{}' would have been removed.".format(name)
            ret["changes"] = {"removed": name}
        elif __salt__["nextcloud_server.app_remove"](
            name, webroot=webroot, webuser=webuser
        ):
            ret["comment"] = "App '{}' has been removed.".format(name)
            ret["changes"] = {"removed": name}
        else:
            # this should not hit, errors are raised
            ret["result"] = False
            ret["comment"] = "Something went wrong while removing app '{}'.".format(
                name
            )

    except (SaltInvocationError, CommandExecutionError) as e:
        ret["result"] = False
        ret["comment"] += str(e)

    return ret


def app_installed(
    name,
    force=False,
    enabled=True,
    groups=None,
    allow_unstable=False,
    webroot=None,
    webuser=None,
):
    """
    Make sure an app is installed.

    name
        Name of the app.

    force
        Install the app regardless of the Nextcloud version requirement. Defaults to False.

    enabled
        Enable the app. Defaults to True.

    groups
        If enabled, only enable this app for specific groups.

    allow_unstable
        Allow installing unstable releases. Defaults to False.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    enabled_str = "enable" if enabled else "disable"

    try:
        current = __salt__["nextcloud_server.app_list"](
            webroot=webroot, webuser=webuser
        )

        is_enabled = name in current["enabled"]
        is_installed = is_enabled or name in current["disabled"]

        add_groups = None
        del_groups = None

        # Groups make this a bit complicated.
        # occ does not allow changing the value of groups once an app
        # has been enabled. Therefore, to change the group settings,
        # an app has to be disabled temporarily.
        # The following checks if this is necessary and helps to report
        # correct changes.
        if enabled and is_enabled:
            # this can return the string "yes" or a list of groups
            current_groups = __salt__["nextcloud_server.config_app_get"](
                name, "enabled"
            )

            # If the app is enabled for all users, set add_groups to
            # groups. This covers both set and unset groups.
            if "yes" == current_groups:
                add_groups = groups
            # If the app is restricted to certain groups and should be,
            # see if wanted and current state match
            elif groups:
                # For some reason, the json output outputs a string
                # that contains the list of groups in json format, not
                # the list itself.
                current_groups = salt.utils.json.loads(current_groups)
                add_groups = set(groups) - set(current_groups)
                del_groups = set(current_groups) - set(groups)
            # If the app is restricted to certain groups, but should
            # not be, make sure they are removed.
            else:
                del_groups = salt.utils.json.loads(current_groups)

        elif enabled:
            add_groups = groups

        need_reset = bool(add_groups or del_groups)

        if is_installed and enabled == is_enabled and not need_reset:
            ret["comment"] = "App '{}' is already installed and {}d".format(
                name, enabled_str
            )
            ret["comment"] += " for the correct groups." if enabled and groups else "."
            return ret

        if not is_installed:
            if __opts__["test"]:
                ret["result"] = None
                ret[
                    "comment"
                ] = "App '{}' would have been installed and {}d afterwards.".format(
                    name, enabled_str
                )
                ret["changes"] = {"installed": name, enabled_str + "d": name}
            elif __salt__["nextcloud_server.app_install"](
                name,
                force=force,
                keep_disabled=not enabled,
                allow_unstable=allow_unstable,
                webroot=webroot,
                webuser=webuser,
            ):
                ret["result"] = True
                ret["comment"] = "App '{}' has been installed in {}d state.".format(
                    name, enabled_str
                )
                ret["changes"] = {"installed": name, enabled_str + "d": name}
            else:
                # this should not hit, errors are raised
                ret["result"] = False
                ret[
                    "comment"
                ] = "Something went wrong while installing app '{}'.".format(name)
            if not need_reset or not ret["result"]:
                return ret

        if need_reset and not __opts__["test"]:
            # This will only be needed if the app should be enabled for a selection
            # of groups that has to change.
            __salt__["nextcloud_server.app_disable"](
                name, webroot=webroot, webuser=webuser
            )

        if enabled or need_reset:
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"] += "The app '{}' would have been enabled".format(name)
                ret["comment"] += " for a selection of groups." if groups else "."
                ret["changes"]["enabled"] = name
                if add_groups:
                    ret["changes"]["enabled_for"] = add_groups
                if del_groups:
                    ret["changes"]["disabled_for"] = del_groups
            elif __salt__["nextcloud_server.app_enable"](
                name, force=force, groups=groups, webroot=webroot, webuser=webuser
            ):
                ret["comment"] += "The app '{}' has been enabled".format(name)
                ret["comment"] += " for a selection of groups." if groups else "."
                ret["changes"]["enabled"] = name
                if add_groups:
                    ret["changes"]["enabled_for"] = add_groups
                if del_groups:
                    ret["changes"]["disabled_for"] = del_groups
            else:
                # this should not hit, errors are raised
                ret["result"] = False
                ret[
                    "comment"
                ] += "Something went wrong while enabling app '{}'.".format(name)
            return ret

        # Now only disabling is on the table

        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] += "The app '{}' would have been disabled".format(name)
            ret["changes"]["disabled"] = name

        elif __salt__["nextcloud_server.app_disable"](
            name, webroot=webroot, webuser=webuser
        ):
            ret["comment"] += "The app '{}' has been disabled".format(name)
            ret["changes"]["disabled"] = name
        else:
            # this should not hit, errors are raised
            ret["result"] = False
            ret["comment"] += "Something went wrong while disabling app '{}'.".format(
                name
            )

    except (SaltInvocationError, CommandExecutionError) as e:
        ret["result"] = False
        ret["comment"] = str(e)

    return ret


def config_set(name, value, vtype=None, separator=":", webroot=None, webuser=None):
    """
    Make sure a Nextcloud system configuration is set as specified.

    name
        Name of the config to set. Separate nested keys with
        separator, which defaults to ``:``.

    value
        The config value to set.

    vtype
        Value type [string, integer, double, boolean].
        If unspecified, will autodiscover the type.

    separator
        Separator for nested keys. Defaults to ``:``.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    if vtype is None:
        if isinstance(value, int):
            vtype = "integer"
        elif isinstance(value, bool):
            vtype = "boolean"
        elif isinstance(value, float):
            vtype = "double"
        else:
            vtype = "string"
    elif vtype not in ["string", "integer", "double", "boolean"]:
        ret["result"] = False
        ret["comment"] = "vtype '{}' is invalid.".format(vtype)
        return ret

    try:
        if value == __salt__["nextcloud_server.config_system_get"](
            name, "__UNSET", separator=separator
        ):
            ret[
                "comment"
            ] = "Nextcloud system setting '{}' is already in the correct state.".format(
                name
            )
        elif __opts__["test"]:
            ret["result"] = None
            ret[
                "comment"
            ] = "Nextcloud system setting '{}' would have been updated.".format(name)
            ret["changes"] = {"config_set": {name: value}}
        elif __salt__["nextcloud_server.config_system_set"](
            name, value, vtype, separator=separator, webroot=webroot, webuser=webuser
        ):
            ret["comment"] = "Nextcloud system setting '{}' has been updated.".format(
                name
            )
            ret["changes"] = {"config_set": {name: value}}
        else:
            # this should not hit, errors are raised
            ret["result"] = False
            ret[
                "comment"
            ] = "Something went wrong while setting Nextcloud system config '{}'.".format(
                name
            )

    except (SaltInvocationError, CommandExecutionError) as e:
        ret["result"] = False
        ret["comment"] = str(e)

    return ret


def config_absent(name, separator=":", webroot=None, webuser=None):
    """
    Make sure a Nextcloud system configuration is absent.

    name
        Name of the config to set. Separate nested keys with
        separator, which defaults to ``:``.

    separator
        Separator for nested keys. Defaults to ``:``.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    try:
        if "__UNSET" == __salt__["nextcloud_server.config_system_get"](
            name, "__UNSET", separator=separator
        ):
            ret["comment"] = "Nextcloud system setting '{}' is already absent.".format(
                name
            )
        elif __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "Nextcloud system setting '{}' would have deleted.".format(
                name
            )
            ret["changes"] = {"deleted": name}
        elif __salt__["nextcloud_server.config_system_delete"](
            name, separator=separator, webroot=webroot, webuser=webuser
        ):
            ret["comment"] = "Nextcloud system setting '{}' has been deleted.".format(
                name
            )
            ret["changes"] = {"deleted": name}
        else:
            # this should not hit, errors are raised
            ret["result"] = False
            ret[
                "comment"
            ] = "Something went wrong while deleting Nextcloud system config '{}'.".format(
                name
            )

    except (SaltInvocationError, CommandExecutionError) as e:
        ret["result"] = False
        ret["comment"] = str(e)

    return ret


def config_imported(name, config=None, force=False, webroot=None, webuser=None):
    """
    Make sure multiple Nextcloud settings are imported.

    name
        If config is unspecified, this can point to a file containing
        a json array to import.

    config
        Configuration values to import. Make sure they are formatted correctly:

        1) root keys are the scope, "system" for system settings,
           "apps" for apps. See output of ``nextcloud_server.config_list all``
           / ``occ config:list`` for reference.
        2) When YAML is involved, make sure the types are correct since
           vtype is not enforced. This is especially important for
           string values of "yes" and "no", which YAML interprets as booleans
           if not quoted.

    force
        Import configuration, even if the current or new one has errors.
        Defaults to false.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    if (
        not __salt__["nextcloud_server.check"](
            only_status=True, webroot=webroot, webuser=webuser
        )
        and not force
    ):
        ret["result"] = False
        ret[
            "comment"
        ] = "Nextcloud reports errors in your current configuration, therefore cannot securely update configuration. Use force=True to override."
        return ret

    try:
        if config is None:
            if not Path(name).exists():
                ret["result"] = False
                ret["comment"] = "File '{}' does not exist.".format(name)
                return ret

            with open(name, "r") as f:
                new_config = salt.utils.json.load(f)
            config = name
        else:
            new_config = config
    # Not sure which specific exception to catch since the library might vary
    except Exception as e:
        ret["result"] = False
        ret[
            "comment"
        ] = "The JSON parser threw an exception. Are you sure your file is formatted correctly? Output was:\n\n{}".format(
            str(e)
        )
        return ret

    try:
        current = __salt__["nextcloud_server.config_list"](
            "all", private=True, webroot=webroot, webuser=webuser
        )
        diff = PatchedRecursiveDiffer(current, new_config, ignore_missing_keys=True)
        changed = diff.changed()
        added = diff.added()

        if not added and not changed:
            ret["comment"] = "Configuration is already imported."
        elif __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "Configuration would have been updated."
            ret["changes"] = {"added": added, "changed": changed}
        elif __salt__["nextcloud_server.config_import"](
            config, webroot=webroot, webuser=webuser
        ):
            ret["comment"] = "Configuration has been updated."
            ret["changes"] = {"added": added, "changed": changed}
        else:
            # this should not hit, errors are raised
            ret["result"] = False
            ret["comment"] = "Something went wrong while importing Nextcloud config."

    except (SaltInvocationError, CommandExecutionError) as e:
        ret["result"] = False
        ret["comment"] = str(e)

    if force:
        return ret

    status = __salt__["nextcloud_server.check"](webroot=webroot, webuser=webuser)

    if status is True:
        return ret

    # If we're here, this means changing the configuration produced errors.
    # Revert as much as possible without much hassle (added app configuration stays currently).

    try:
        __salt__["nextcloud_server.config_import"](
            current, webroot=webroot, webuser=webuser
        )

        for new_val in diff.added(separator="|||"):
            if new_val.startswith("system"):
                key = "|||".join(new_val.split("|||")[1:])
                __salt__["nextcloud_server.delete"](
                    key, separator="|||", webroot=webroot, webuser=webuser
                )

        ret["result"] = False
        ret[
            "comment"
        ] = "Applied configuration successfully, but resulting configuration had errors. Reverted most of the changes, but added app settings stay. Use force: true to override this check and leave resulting configuration."
        ret["changes"] = {
            "added": [x for x in added if not x.startswith("system")],
            "changed": [],
        }
    except (SaltInvocationError, CommandExecutionError) as e:
        ret["result"] = False
        ret[
            "comment"
        ] = "Applied configuration successfully, but resulting configuration had errors. Tried to revert, but that resulted in an exception. Output was:\n\n{}".format(
            e
        )

    return ret


def group_absent(name, webroot=None, webuser=None):
    """
    Make sure a group does not exist.

    name
        The Nextcloud group ID to ensure absence of.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    try:
        if not __salt__["nextcloud_server.group_exists"](
            name, webroot=webroot, webuser=webuser
        ):
            ret["comment"] = "Group '{}' is already absent.".format(name)
        elif __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "Group '{}' would have been deleted.".format(name)
            ret["changes"] = {"deleted": name}
        elif __salt__["nextcloud_server.group_delete"](
            name, webroot=webroot, webuser=webuser
        ):
            ret["comment"] = "Group '{}' has been deleted.".format(name)
            ret["changes"] = {"deleted": name}
        else:
            # this should not hit, errors are raised
            ret["result"] = False
            ret["comment"] = "Something went wrong while deleting user '{}'.".format(
                name
            )

    except (SaltInvocationError, CommandExecutionError) as e:
        ret["result"] = False
        ret["comment"] += str(e)

    return ret


def group_present(
    name, addusers=None, delusers=None, max_iterations=3, webroot=None, webuser=None
):
    """
    Make sure a group exists.

    name
        The Nextcloud group ID.

    addusers
        List of user IDs to make sure are in the group.

    delusers
        List of user IDs to make sure are absent from the group.

    max_iterations
        Maximum allowed number of calls to group_list to find
        information about a group. Every call returns 500 groups,
        so this is only relevant for very large installations.
        Defaults to 3.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    if addusers is None:
        addusers = []

    if delusers is None:
        delusers = []

    try:
        if __salt__["nextcloud_server.group_exists"](
            name, webroot=webroot, webuser=webuser
        ):
            ret["comment"] = "Group '{}' already exists.".format(name)
        elif __opts__["test"]:
            ret["result"] = None
            ret[
                "comment"
            ] = "Group '{}' would have been created. This does not check for existence of user accounts, so make sure they exist before adding them to the group".format(
                name
            )
            ret["changes"] = {"group_created": name, "members_added": addusers}
            return ret
        elif __salt__["nextcloud_server.group_add"](
            name, webroot=webroot, webuser=webuser
        ):
            ret["comment"] = "User '{}' has been created.".format(name)
            ret["changes"] = {"group_created": name}
        else:
            # this should not hit, errors are raised
            ret["result"] = False
            ret["comment"] = "Something went wrong while creating user '{}'.".format(
                name
            )
            return ret

        if not addusers and not delusers:
            return ret

        # For very large installations, one call might not be enough
        # to get information about the group.

        current = {}
        iterations = 0
        limit = 500

        while name not in current and iterations < max_iterations:
            offset = limit * iterations
            current = __salt__["nextcloud_server.group_list"](
                limit=limit, offset=offset, webroot=webroot, webuser=webuser
            )
            iterations += 1

        if name not in current:
            ret["result"] = False
            ret[
                "comment"
            ] += " Could not find the group member list though. In case you have more than {} groups, try to increase max_iterations.".format(
                str(limit * max_iterations)
            )
            return ret

        current = current[name]

        ret["changes"]["users_added"] = []
        ret["changes"]["users_removed"] = []

        for user in addusers:
            if user not in current:
                __salt__["nextcloud_server.group_adduser"](
                    name, user, webroot=webroot, webuser=webuser
                )
                ret["changes"]["users_added"].append(user)

        for user in delusers:
            if user in current:
                __salt__["nextcloud_server.group_removeuser"](
                    name, user, webroot=webroot, webuser=webuser
                )
                ret["changes"]["users_removed"].append(user)

        # Doing it like this to avoid information loss when
        # a user account does not exist.
        if not ret["changes"]["users_added"]:
            ret["changes"].pop("users_added")

        if not ret["changes"]["users_removed"]:
            ret["changes"].pop("users_removed")

    except (SaltInvocationError, CommandExecutionError) as e:
        ret["result"] = False
        ret["comment"] += str(e)

    return ret


def user_absent(name, webroot=None, webuser=None):
    """
    Make sure a user account does not exist.

    name
        User ID of the user to ensure absence of.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    try:
        if not __salt__["nextcloud_server.user_exists"](
            name, webroot=webroot, webuser=webuser
        ):
            ret["comment"] = "User '{}' is already absent.".format(name)
        elif __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "User '{}' would have been deleted.".format(name)
            ret["changes"] = {"deleted": name}
        elif __salt__["nextcloud_server.user_delete"](
            name, webroot=webroot, webuser=webuser
        ):
            ret["comment"] = "User '{}' has been deleted.".format(name)
            ret["changes"] = {"deleted": name}
        else:
            # this should not hit, errors are raised
            ret["result"] = False
            ret["comment"] = "Something went wrong while deleting user '{}'.".format(
                name
            )

    except (SaltInvocationError, CommandExecutionError) as e:
        ret["result"] = False
        ret["comment"] += str(e)

    return ret


def user_present(
    name,
    enabled=True,
    init_password=None,
    init_password_pillar=None,
    webroot=None,
    webuser=None,
):
    """
    Make sure a user account is present.

    name
        User ID used to login. Can only contain alphanumeric chars and ``-_@``.

    enabled
        Whether this user account is enabled. Defaults to True.

    init_password
        The user's initial password. Will not be managed after creation.
        Better use password_pillar to avoid logs/caches.
        ``init_password`` or ``init_password_pillar`` is required.

    init_password_pillar
        The pillar key where the user's initial password can be looked up.
        ``password`` or ``password_pillar`` is required.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    try:
        if __salt__["nextcloud_server.user_exists"](
            name, webroot=webroot, webuser=webuser
        ):
            ret["comment"] = "User '{}' already exists.".format(name)
        elif __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "User '{}' would have been created.".format(name)
            ret["changes"] = {"created": name}
        elif __salt__["nextcloud_server.user_add"](
            name,
            password=init_password,
            password_pillar=init_password_pillar,
            webroot=webroot,
            webuser=webuser,
        ):
            ret["comment"] = "User '{}' has been created.".format(name)
            ret["changes"] = {"created": name}
        else:
            # this should not hit, errors are raised
            ret["result"] = False
            ret["comment"] = "Something went wrong while creating user '{}'.".format(
                name
            )
            return ret

        # when testing, return early to not cause exceptions on lookup
        # of absent user account
        if ret["result"] is None:
            if not enabled:
                ret[
                    "comment"
                ] += " The user account would have been disabled after creation."
                ret["changes"] |= {"disabled": name}
            return ret

        current = __salt__["nextcloud_server.user_enabled"](
            name, webroot=webroot, webuser=webuser
        )

        enabled_str = "enable" if enabled else "disable"

        if current == enabled:
            ret["comment"] += " The account is already {}d.".format(enabled_str)
        elif __opts__["test"]:
            ret["result"] = None
            ret["comment"] += " The account would have been {}d.".format(enabled_str)
            ret["changes"] = {enabled_str + "d": name}
        elif __salt__["nextcloud_server.user_" + enabled_str](
            name, webroot=webroot, webuser=webuser
        ):
            ret["comment"] += " The account has been {}d.".format(enabled_str)
            ret["changes"] = {enabled_str + "d": name}
        else:
            # this should not hit, errors are raised
            ret["result"] = False
            ret["comment"] = "Something went wrong while {} user '{}'.".format(
                "enabling" if enabled else "disabling", name
            )

    except (SaltInvocationError, CommandExecutionError) as e:
        ret["result"] = False
        ret["comment"] += str(e)

    return ret


class PatchedRecursiveDiffer(salt.utils.dictdiffer.RecursiveDictDiffer):
    def added(self, include_nested=False, separator="."):
        """
        Returns all keys that have been added.

        include_nested
            If an added key contains a dictionary, include its
            keys in dot notation as well. Defaults to false.

        If the keys are in child dictionaries they will be represented with
        . notation.

        This works for added nested dicts as well, where the parent class
        tries to access keys on non-dictionary values and throws an exception.
        """
        return sorted(self._it("old", "new", include_nested, separator=separator))

    def removed(self, include_nested=False):
        """
        Returns all keys that have been removed.

        include_nested
            If an added key contains a dictionary, include its
            keys in dot notation as well. Defaults to false.

        If the keys are in child dictionaries they will be represented with
        . notation

        This works for removed nested dicts as well, where the parent class
        tries to access keys on non-dictionary values and throws an exception.
        """
        return sorted(self._it("new", "old", include_nested))

    def _it(
        self,
        key_a,
        key_b,
        include_nested=False,
        diffs=None,
        prefix="",
        is_nested=False,
        separator=".",
    ):
        keys = []
        if diffs is None:
            diffs = self.diffs

        for key in diffs.keys():
            if is_nested:
                keys.append("{}{}".format(prefix, key))

            if not isinstance(diffs[key], dict):
                continue

            if is_nested:
                keys.extend(
                    self._it(
                        key_a,
                        key_b,
                        diffs=diffs[key],
                        prefix="{}{}{}".format(prefix, key, separator),
                        is_nested=is_nested,
                        include_nested=include_nested,
                    )
                )
            elif "old" not in diffs[key]:
                keys.extend(
                    self._it(
                        key_a,
                        key_b,
                        diffs=diffs[key],
                        prefix="{}{}{}".format(prefix, key, separator),
                        is_nested=is_nested,
                        include_nested=include_nested,
                    )
                )
            elif diffs[key][key_a] == self.NONE_VALUE:
                keys.append("{}{}".format(prefix, key))

                if isinstance(diffs[key][key_b], dict) and include_nested:
                    keys.extend(
                        self._it(
                            key_a,
                            key_b,
                            diffs=diffs[key][key_b],
                            is_nested=True,
                            prefix="{}{}{}".format(prefix, key, separator),
                            include_nested=include_nested,
                        )
                    )
        return keys
