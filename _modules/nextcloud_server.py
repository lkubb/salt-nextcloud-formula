"""
Nextcloud Server salt execution module
=======================================

Manage Nextcloud Server by calling ``occ``.

There are three Salt configuration values that modify the default
behavior of this module:

nextcloud_server.ensure_apc
    Run commands with ``php --define apc.enable_cli=1`` to ensure
    apcu is enabled in CLI mode, which it is not by default.
    Defaults to True.

    Mind that setting this if not enabled in Nextcloud is fine,
    but the absence of apcu when enabled causes occ to break.

nextcloud_server.webroot
    The root directory of the Nextcloud installation.
    Defaults to ``/var/www/nextcloud``.

nextcloud_server.user
    The user that runs Nextcloud/owns the files in the webroot.
    Defaults to ``www-data``, irrespectible of OS currently. @TODO
"""

import logging
import re
import shlex
from pathlib import Path

import salt.utils.json
import yaml
from pkg_resources import packaging
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)
__virtualname__ = "nextcloud_server"

ensure_apc_global = True
web_user = "www-data"
web_root = "/var/www/nextcloud"


def __virtual__():
    return __virtualname__


def __init__(opts):
    global web_user
    global web_root
    global ensure_apc_global
    web_user = opts.get("nextcloud_server.user", web_user)
    web_root = opts.get("nextcloud_server.webroot", web_root)
    ensure_apc_global = opts.get("nextcloud_server.ensure_apc", ensure_apc_global)


def occ(
    command,
    arguments=None,
    parameters=None,
    flags=None,
    webroot=None,
    webuser=None,
    ensure_apc=None,
    json=True,
    raise_error=True,
    expect_error=False,
    env=None,
    stdin=None,
    quiet=False,
    python_shell=False,
):
    """
    Run arbitrary ``occ`` commands.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.occ preview:repair flags=["batch"] json=False

    command
        The ``occ`` sub-command.

    arguments
        List of command arguments.

    parameters
        List of parameter: value mappings.

    flags:
        List of flags.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.

    ensure_apc
        Run commands with ``php --define apc.enable_cli=1`` to ensure
        apcu is enabled in CLI mode, which it is not by default.
        Defaults to minion config value ``nextcloud_server.ensure_apc`` or True.

        Mind that setting this if not enabled in Nextcloud is fine,
        but the absence of apcu when enabled causes occ to break.

    json
        Make sure parameters includes --output json and parse the output accordingly.
        Defaults to True currently, but not all commands support it.

    raise_error
        Raise an exception if the return code is not 0. Defaults to true.

    expect_error
        Do not treat a return code != 0 as an error condition.
        This causes Salt to not log the command as an error.
        Defaults to False. Setting this to True implies raise_error=False.

    env
        Mapping of environment variables to set prior to execution.

    stdin
        String that will be passed in stdin.

    quiet
        Suppress all logging output (sets output_loglevel)

    python_shell
        Parameter for ``cmd.run_all``. Needed when using shell features
        like pipes and variable substitution.
    """

    if arguments is None:
        arguments = []
    if parameters is None:
        parameters = []
    if flags is None:
        flags = []
    if webuser is None:
        webuser = web_user
    if webroot is None:
        webroot = web_root
    if ensure_apc is None:
        ensure_apc = ensure_apc_global
    if env is None:
        env = {}

    output_loglevel = "quiet" if quiet else "debug"

    if json:
        parameters.append(("output", "json"))

    flags.append("no-interaction")

    if not (Path(webroot) / "occ").exists():
        raise SaltInvocationError(
            "'{}' does not exist. Is Nextcloud installed in '{}'?".format(occ, webroot)
        )

    cmd = ["php"]

    if ensure_apc:
        cmd += ["--define", "apc.enable_cli=1"]

    cmd += ["./occ", command]
    cmd += ["{}{}".format("--" if not f.startswith("-") else "", f) for f in flags]

    for param, val in parameters:
        # for some commands that do not allow reading sensitive values via env vars
        # themselves (looking at you, maintenance:install), need to allow quoting
        # parameters in the downstream functions
        val_fmt = "'{}'" if isinstance(val, str) and not val.startswith('"') else "{}"
        cmd.extend(["--{}".format(param), val_fmt.format(val)])

    cmd.extend(["--"] + arguments)

    out = __salt__["cmd.run_all"](
        " ".join(cmd),
        cwd=webroot,
        env=env,
        output_loglevel=output_loglevel,
        runas=webuser,
        stdin=stdin,
        python_shell=python_shell,
        ignore_retcode=expect_error,
    )

    if not expect_error and raise_error and out["retcode"]:
        raise CommandExecutionError(
            "Failed running occ {}.\nstderr: {}\nstdout: {}".format(
                command, out["stderr"], out["stdout"]
            )
        )

    if not out["retcode"] and json:
        out["parsed"] = salt.utils.json.loads(out["stdout"])

    return out


def check(only_status=False, webroot=None, webuser=None):
    """
    Check dependencies of the server environment.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.check

    only_status
        Only return boolean, do not return error output on failure.
        Defaults to False.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    out = occ("check", webroot=webroot, webuser=webuser, raise_error=False, json=False)

    if 0 == out["retcode"]:
        return True

    if only_status:
        return False

    return out["stdout"]


def finish_upgrade(webroot=None, webuser=None):
    """
    Run upgrade routines after installation of a new release.
    The release has to be installed before.
    This actually runs ``occ upgrade``.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.finish_upgrade

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    out = occ("upgrade", json=False, webroot=webroot, webuser=webuser)

    return out["stdout"] or True


def install(
    database=None,
    database_name=None,
    database_host=None,
    database_user=None,
    database_pass=None,
    database_pass_pillar=None,
    database_table_space=None,
    admin_user=None,
    admin_pass=None,
    admin_pass_pillar=None,
    admin_email=None,
    datadir=None,
    webroot=None,
    webuser=None,
):
    """
    Finish the initial installation using the command line instead of
    the web installer.

    This command is only available if no installation has taken place before.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.install

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

    # maintenance:install has database-port as well, but only appends it
    # since the value is not exposed in config.php

    stat = status(webroot=webroot, webuser=webuser)

    if stat.get("installed"):
        raise CommandExecutionError(
            "{}.install is not available since Nextcloud seems to be installed already.".format(
                __virtualname__
            )
        )

    if (
        database
        and "sqlite" != database
        and database_pass is None
        and database_pass_pillar is None
    ):
        raise SaltInvocationError(
            "You need to specify either database_pass or database_pass_pillar when database is not sqlite."
        )

    if admin_pass is None and admin_pass_pillar is None:
        raise SaltInvocationError(
            "You need to specify either admin_pass or admin_pass_pillar."
        )

    params = []
    env = {}

    if database:
        params.append(("database", database))

    if database and "sqlite" != database:
        for p, d, n in [
            (database_name, "nextcloud", "database-name"),
            (database_host, "localhost", "database-host"),
            (database_user, "nextcloud", "database-user"),
        ]:
            params.append((n, p or d))

        if database_pass_pillar:
            database_pass = __salt__["pillar.get"](database_pass_pillar)

        if database_pass is None:
            raise CommandExecutionError(
                "Could not find database_pass_pillar `{}`.".format(database_pass_pillar)
            )

        params.append(("database-pass", '"$NC_DB_PASS"'))
        env["NC_DB_PASS"] = database_pass

        if "oci" == database and database_table_space:
            params.append(("database-table-space", database_table_space))

    if admin_user:
        params.append(("admin-user", admin_user))

    if admin_pass_pillar:
        admin_pass = __salt__["pillar.get"](admin_pass_pillar)

    if admin_pass is None:
        raise CommandExecutionError(
            "Could not find admin_pass_pillar '{}'.".format(admin_pass_pillar)
        )

    params.append(("admin-pass", '"$NC_ADMIN_PASS"'))
    env["NC_ADMIN_PASS"] = admin_pass

    if admin_email:
        params.append(("admin-email", admin_email))

    datadir = datadir or str(Path(webroot or web_root) / "data")

    params.append(("data-dir", datadir))

    out = occ(
        "maintenance:install",
        parameters=params,
        quiet=True,
        env=env,
        json=False,
        webroot=webroot,
        webuser=webuser,
        python_shell=True,
    )

    return out["stdout"] or True


def is_installed(raise_error=False, webroot=None, webuser=None):
    """
    Check if Nextcloud itself is installed and working correctly.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.stat

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """
    try:
        stat = status(webroot=webroot, webuser=webuser)
    except CommandExecutionError:  # pylint: disable=broad-except
        if raise_error:
            raise
        stat = {}

    return bool(stat.get("installed"))


def is_uptodate(max_version=None, webroot=None, webuser=None):
    """
    Check if Nextcloud itself is up to date.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.status

    max_version
        If the proposed update is higher than this version,
        report True. Empty for latest.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    updates = update_check(webroot=webroot, webuser=webuser)

    if "Nextcloud" not in updates:
        return True

    if max_version is None:
        return False

    # pkg_util always normalizes versions, so e.g.
    # 24.0.1 > 24. If only parts of the version string were defined,
    # we want to update to point releases though.

    if isinstance(max_version, int):
        max_version = "{}.999.999".format(max_version)
    elif isinstance(max_version, float) or (
        isinstance(max_version, str) and 1 == max_version.count(".")
    ):
        max_version = "{}.999".format(max_version)

    update = packaging.version.parse(updates["Nextcloud"])
    target = packaging.version.parse(max_version)

    if update > target:
        return True

    return False


def status(webroot=None, webuser=None):
    """
    Check dependencies of the server environment.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.status

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    out = occ("status", webroot=webroot, webuser=webuser)

    return out["parsed"]


def upgrade(no_backup=False, webroot=None, webuser=None, ensure_apc=None):
    """
    Runs ``updater.phar`` in non-interactive mode.

    Mind that the updater **does not perform backups** of data files
    and database, only of the Nextcloud code.

    For details, see `the official docs <
    https://docs.nextcloud.com/server/latest/admin_manual/maintenance/update.html>`_

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.upgrade

    no_backup
        Skip backup of current Nextcloud version (the installation files).
        Defaults to False.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.

    ensure_apc
        Run commands with ``php --define apc.enable_cli=1`` to ensure
        apcu is enabled in CLI mode, which it is not by default.
        Defaults to minion config value ``nextcloud_server.ensure_apc`` or True.
    """

    webroot = webroot or web_root
    webuser = webuser or web_user
    ensure_apc = ensure_apc_global if ensure_apc is None else ensure_apc

    updater = Path(webroot) / "updater" / "updater.phar"

    if not updater.exists():
        raise CommandExecutionError("Could not find updater at '{}'.".format(updater))

    cmd = ["php"]

    if ensure_apc:
        cmd += ["--define", "apc.enable_cli=1"]

    cmd += [str(updater), "--no-interaction"]

    if no_backup:
        cmd += "--no-backup"

    out = __salt__["cmd.run_all"](" ".join(cmd), cwd=webroot, runas=webuser)

    if out["retcode"] > 0:
        raise CommandExecutionError(
            "Upgrading Nextcloud failed.\n\nStdout:\n{}\n\nStderr:\n{}".format(
                out["stdout"], out["stderr"]
            )
        )

    return out["stdout"] or True


def version(webroot=None, webuser=None):
    """
    Return the installed Nextcloud version.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.version

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    # There is also status()["version"] and status()["versionstring"],
    # the latter matching this output. The former might have another
    # point version.

    out = occ("--version", json=False, webroot=webroot, webuser=webuser)

    return out["stdout"].split(" ")[1]


def version_raw(webroot=None, webuser=None):
    """
    Return the installed Nextcloud version. Uses information from the
    `version.php` file directly instead of relying on a functional `occ` command.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.version_raw

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """
    cmd = f"require_once('{webroot or web_root}/version.php'); "
    cmd += "echo json_encode(implode('.', $OC_Version));"
    return _php(cmd, webroot=webroot, webuser=webuser)


def app_disable(app, webroot=None, webuser=None):
    """
    Disable an app.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.app_disable recommendations

    app
        Name of the app.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    out = occ("app:disable", [app], webroot=webroot, webuser=webuser, json=False)

    return out["stdout"] or True


def app_enable(app, force=False, groups=None, webroot=None, webuser=None):
    """
    Enable an app.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.app_enable oauth2

    app
        Name of the app.

    force
        Enable the app regardless of the Nextcloud version requirement. Defaults to False.

    groups
        Enable the app only for a list of groups.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    if groups is None:
        groups = []
    elif not isinstance(groups, list):
        groups = [groups]

    params = []
    flags = []

    for group in groups:
        params.append(("groups", group))

    if force:
        flags.append("force")

    out = occ(
        "app:enable",
        [app],
        flags=flags,
        parameters=params,
        webroot=webroot,
        webuser=webuser,
        json=False,
    )

    return out["stdout"] or True


def app_getpath(app, webroot=None, webuser=None):
    """
    Get an absolute path to the app directory.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.app_getpath oauth2

    app
        Name of the app.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    out = occ("app:getpath", [app], webroot=webroot, webuser=webuser, json=False)

    return out["stdout"]


def app_install(
    app,
    force=False,
    keep_disabled=False,
    allow_unstable=False,
    webroot=None,
    webuser=None,
):
    """
    Install an app.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.app_install oauth2

    app
        Name of the app.

    force
        Install the app regardless of the Nextcloud version requirement. Defaults to False.

    keep_disabled
        Don't enable the app afterwards. Defaults to False.

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

    flags = []

    if keep_disabled:
        flags.append("keep-disabled")

    if force:
        flags.append("force")

    if allow_unstable:
        flags.append("allow-unstable")

    out = occ(
        "app:install", [app], flags=flags, webroot=webroot, webuser=webuser, json=False
    )

    return out["stdout"] or True


def app_list(shipped=None, webroot=None, webuser=None):
    """
    List all available apps.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.app_list

    shipped
        True:  Limit to shipped apps only.
        False: Limit to non-shipped apps only.
        Defaults to None.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    params = []

    if shipped is not None:
        params.append(str(shipped).lower())

    out = occ("app:list", parameters=params, webroot=webroot, webuser=webuser)

    return out["parsed"]


def app_remove(app, keep_data=False, webroot=None, webuser=None):
    """
    Remove an app.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.app_remove recommendations

    app
        Name of the app.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = []

    if keep_data:
        flags.append("keep-data")

    out = occ(
        "app:remove", [app], flags=flags, webroot=webroot, webuser=webuser, json=False
    )

    return out["stdout"] or True


def app_update(app=None, allow_unstable=False, webroot=None, webuser=None):
    """
    Update an app/all apps.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.app_update oauth2

    app
        Name of the app. Unspecified for all.

    allow_unstable
        Allow updating to unstable releases. Defaults to False.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = []
    args = [app]

    if allow_unstable:
        flags.append("allow-unstable")

    if app is None:
        args = []
        flags.append("all")

    out = occ(
        "app:update", args, flags=flags, webroot=webroot, webuser=webuser, json=False
    )

    return out["stdout"] or True


def app_list_updates(allow_unstable=False, webroot=None, webuser=None):
    """
    List upgradable apps.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.app_list_updates

    allow_unstable
        Include unstable releases. Defaults to False.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = ["showonly"]

    if allow_unstable:
        flags.append("allow-unstable")

    # does not support json output
    out = occ("app:update", flags=flags, webroot=webroot, webuser=webuser, json=False)

    updates = re.findall(
        r"^([\S]+) new version available: ([\d\.]+)$", out["stdout"], re.MULTILINE
    )

    return {app: version for app, version in updates}


def config_app_delete(app, name, error_if_not_exists=False, webroot=None, webuser=None):
    """
    Remove an app setting.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.config_app_delete files_external allow_user_mounting

    app
        Name of the app.

    name
        Name of the config to delete.

    error_if_not_exists
        Throw error if the config does not exit. Defaults to False.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = []

    if error_if_not_exists:
        flags.append("error-if-not-exists")

    # claims to support json output, does not
    out = occ(
        "config:app:delete",
        [app, name],
        flags=flags,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"] or True


def config_app_get(app, name, default=None, webroot=None, webuser=None):
    """
    Get an app setting.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.config_app_get files_sharing enabled

    app
        Name of the app.

    name
        Name of the config to get.

    default
        Instead of raising an exception, return this default value.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    out = occ(
        "config:app:get",
        [app, name],
        raise_error=False,
        webroot=webroot,
        webuser=webuser,
    )

    if not out["retcode"]:
        return out["parsed"]
    if default is not None:
        # this returns with non-zero exit code though @FIXME
        return default

    raise CommandExecutionError(
        "Could not get app setting named '{}'. Output was:\n{}".format(
            name, out["stderr"]
        )
    )


def config_app_set(app, name, value, update_only=False, webroot=None, webuser=None):
    """
    Set an app setting.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.config_app_set files_sharing enabled true

    app
        Name of the app.

    name
        Name of the config to set.

    value
        The config value to set.

    update_only
        Only update existing values, do not add new ones.
        Defaults to False.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = []

    if update_only:
        flags.append("update-only")

    # @TODO Reconsider this, not sure if valid.
    # "enabled" seems to be "yes" consistently, not sure
    # about other settings though.
    if isinstance(value, bool):
        value = "yes" if value else "no"

    params = [("value", value)]

    # claims to support json output, does not
    out = occ(
        "config:app:set",
        [app, name],
        parameters=params,
        flags=flags,
        webroot=webroot,
        webuser=webuser,
        json=False,
    )

    return out["stdout"] or True


def config_import(config, webroot=None, webuser=None):
    """
    Import multiple configuration values.

    Mind that currently, occ (wrongly) disallows float/double values
    for ``config:import``. This function implements a workaround
    by filtering those values and setting them separately one by one.
    This workaround only applies when passing the data directly,
    not when passing a file path. For app settings, nested floats
    are not allowed.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.config_import /my/custom/config.json

    config
        Configuration to import. This can either be a path to
        a json-formatted file local to the minion or the config
        itself.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = []
    stdin = None

    doubles = []

    if isinstance(config, str):
        args = [config]
    else:
        # ---- workaround for https://github.com/nextcloud/server/issues/32468
        # tldr: import of float/doubles is prohibited by config:import
        # this skips list items to not overcomplicate the workaround
        # this should be fixed in 24.0.3
        try:
            cur_version = version(webroot=webroot, webuser=webuser)
        except CommandExecutionError:
            cur_version = version_raw(webroot=webroot, webuser=webuser)

        fixed_version = packaging.version.parse("24.0.3")

        if packaging.version.parse(cur_version) < fixed_version:

            def find_double(data):
                if not isinstance(data, dict):
                    if isinstance(data, float):
                        return data
                    return
                filtered = {key: find_double(val) for key, val in data.items()}
                return {key: val for key, val in filtered.items() if val is not None}

            def filter_double(data, doubles):
                if not isinstance(data, dict):
                    return
                filtered = {
                    key: filter_double(val, doubles[key]) if key in doubles else val
                    for key, val in data.items()
                }
                return {key: val for key, val in filtered.items() if val is not None}

            def flatten_dict(data, prefix="", separator="|||"):
                ret = []
                if not isinstance(data, dict):
                    return [(prefix[: -1 * len(separator)], data)]
                for key, val in data.items():
                    ret.extend(flatten_dict(val, prefix + key + separator))
                return ret

            doubles = find_double(config)
            config = filter_double(config, doubles)
            doubles = flatten_dict(doubles)
        # ---- end workaround --------------
        stdin = salt.utils.json.dumps(config)

    out = occ(
        "config:import", args, json=False, stdin=stdin, webroot=webroot, webuser=webuser
    )

    # ------ workaround, part 2 ------------
    # this needs to be below the import, otherwise nested
    # values would be overwritten
    # doubles are always empty, unless the workaround was necessary,
    # so checking for version is superfluous

    for p, val in doubles:
        scope, *key = p.split("|||")
        if "system" == scope:
            config_system_set(
                "|||".join(key),
                val,
                vtype="double",
                separator="|||",
                webroot=webroot,
                webuser=webuser,
            )
        elif "app" == scope:
            app, *name = key
            if len(name) > 1:
                raise CommandExecutionError(
                    "The app configuration for '{}' contains a double inside a dictionary ({}). This is currently unsupported by occ.".format(
                        app, ":".join(name)
                    )
                )
            config_app_set(
                app,
                name[0],
                val,
                vtype="double",
                separator="|||",
                webroot=webroot,
                webuser=webuser,
            )
    # -------- end workaround, part 2 ------

    return out["stdout"] or True


def config_list(app="system", private=False, webroot=None, webuser=None):
    """
    List configuration values.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.config_list

    app
        Name of the app. Defaults to ``system``.
        Set to ``all`` to query for all apps and system configuration.

    private
        Include sensitive settings. Defaults to False.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = []

    if private:
        flags.append("private")

    out = occ("config:list", [app], flags=flags, webroot=webroot, webuser=webuser)

    return out["parsed"]


def config_list_raw(config_file="config/config.php", webroot=None, webuser=None):
    """
    Renders the raw configuration file. This is not intended for general usage, only to recover
    from configuration errors that render the ``occ`` command unusable.

    config_file
        The file name to import and write, relative to ``webroot``. Defaults to ``config/config.php``.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """
    conf = Path(webroot or web_root) / config_file
    if not conf.exists():
        log.warning(f"Specified config file '{conf}' does not exist")
        return {}
    if not conf.read_text().strip():
        log.warning(f"Specified config file '{conf}' is empty")
        return {}
    return _php(
        f"require('{webroot or web_root}/{config_file}'); echo json_encode($CONFIG);",
        webroot=webroot,
        webuser=webuser,
    )


def config_import_raw(
    config, config_file="config/config.php", webroot=None, webuser=None
):
    """
    Imports raw configuration, skipping validation.
    This is not intended for general usage, only to recover from configuration
    errors that render the ``occ`` command unusable or for cluster setups.

    config
        A mapping of config names to values to set. This must be a dictionary,
        which will be passed into a PHP script via JSON.

    config_file
        The file name to import and write, relative to ``webroot``. Defaults to ``config/config.php``.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """
    config_json = salt.utils.json.dumps(config)
    # https://stackoverflow.com/questions/7696548/how-to-remove-empty-entries-of-an-array-recursively
    cmd = """\
function array_remove_empty($haystack)
{
    foreach ($haystack as $key => $value) {
        if (is_array($value)) {
            $haystack[$key] = array_remove_empty($haystack[$key]);
        }

        if (is_null($haystack[$key])) {
            unset($haystack[$key]);
        }
    }

    return $haystack;
}
"""
    cmd += f"""
$CONFIG = [];
$configFile = '{webroot or web_root}/{config_file}';
is_file($configFile) AND require($configFile);
$newCfgJson = <<<'JSONCONF'
{config_json}
JSONCONF;
$newCfg = json_decode($newCfgJson, true);
$mergedCfg = array_merge($CONFIG, $newCfg);
$mergedCfg = array_remove_empty($mergedCfg);
$content = "<?php\n";
$content .= '$CONFIG = ';
$content .= var_export($mergedCfg, true);
$content .= ";\n";
touch($configFile);
chmod($configFile, 0640);
file_put_contents($configFile, $content);
echo 'true';
"""
    out = _php(cmd, webroot=webroot, webuser=webuser)
    if out is True:
        return True
    raise CommandExecutionError(f"Failed raw import of config. Output was: {out}")


def config_system_delete(
    name, error_if_not_exists=False, separator=":", webroot=None, webuser=None
):
    """
    Remove a system setting.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.config_system_delete redis

    name
        Name of the system config to delete. Separate nested keys with
        separator, which defaults to ``:``.

    error_if_not_exists
        Throw error if the config does not exit. Defaults to False.

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

    args = [name] if separator not in name else name.split(separator)
    flags = []

    if error_if_not_exists:
        flags.append("error-if-not-exists")

    # claims to support json output, does not
    out = occ(
        "config:system:delete",
        args,
        flags=flags,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"] or True


def config_system_get(name, default=None, separator=":", webroot=None, webuser=None):
    """
    Get a system setting.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.config_system_get installed

    name
        Name of the system config to get. Separate nested keys with
        separator, which defaults to ``:``.

    default
        Instead of raising an exception, return this default value.

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

    args = [name] if separator not in name else name.split(separator)

    out = occ(
        "config:system:get", args, raise_error=False, webroot=webroot, webuser=webuser
    )

    if not out["retcode"]:
        return out["parsed"]
    if default is not None:
        return default

    raise CommandExecutionError(
        "Could not get system setting named '{}'. Output was:\n{}".format(
            name, out["stderr"]
        )
    )


def config_system_set(
    name,
    value,
    vtype="string",
    update_only=False,
    separator=":",
    webroot=None,
    webuser=None,
):
    """
    Set a system setting.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.config_system_set loglevel 2 integer

    name
        Name of the config to set. Separate nested keys with
        separator, which defaults to ``:``.

    value
        The config value to set.

    vtype
        Value type [string, integer, double, boolean]. Defaults to ``string``.

    update_only
        Only update existing values, do not add new ones.
        Defaults to False.

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

    if vtype not in ["string", "integer", "double", "boolean"]:
        raise CommandExecutionError("Value type '{}' is invalid.".format(vtype))

    args = [name] if separator not in name else name.split(separator)

    flags = []

    if update_only:
        flags.append("update-only")

    params = [("value", str(value)), ("type", vtype)]

    # claims to support json output, does not
    out = occ(
        "config:system:set",
        args,
        parameters=params,
        flags=flags,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"] or True


def db_add_missing_columns(webroot=None, webuser=None):
    """
    Add missing optional columns to the database tables.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.db_add_missing_columns

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    out = occ("db:add-missing-columns", json=False, webroot=webroot, webuser=webuser)

    return out["stdout"] or True


def db_add_missing_indices(webroot=None, webuser=None):
    """
    Add missing indices to the database tables.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.db_add_missing_indices

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    out = occ("db:add-missing-indices", json=False, webroot=webroot, webuser=webuser)

    return out["stdout"] or True


def db_add_missing_primary_keys(webroot=None, webuser=None):
    """
    Add missing primary keys to the database tables.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.db_add_missing_primary_keys

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    out = occ(
        "db:add-missing-primary-keys", json=False, webroot=webroot, webuser=webuser
    )

    return out["stdout"] or True


def db_convert_filecache_bigint(webroot=None, webuser=None):
    """
    Convert the ID columns of the filecache to BigInt.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.db_convert_filecache_bigint

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    out = occ(
        "db:convert-filecache-bigint", json=False, webroot=webroot, webuser=webuser
    )

    return out["stdout"] or True


def db_convert_mysql_charset(webroot=None, webuser=None):
    """
    Convert charset of MySQL/MariaDB to use utf8mb4.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.db_convert_mysql_charset

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    if "mysql" != config_system_get("dbtype", ""):
        raise CommandExecutionError("Configured database is not MySQL/MariaDB.")

    out = occ("db:convert-mysql-charset", json=False, webroot=webroot, webuser=webuser)

    return out["stdout"] or True


def db_convert_type(
    dbtype,
    username,
    hostname,
    database,
    port=None,
    password=None,
    password_pillar=None,
    clear_schema=False,
    all_apps=False,
    chunk_size=None,
    webroot=None,
    webuser=None,
):
    """
    Convert the Nextcloud database to the newly configured one.
    ``occ`` does not support migration to the same database type
    for some reason.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.db_convert_type pgsql chad localhost nextcloud password=password1

    dbtype
        The type of the database to convert to [mysql, pgsql, oci (EE)].
        Converting to ``sqlite`` is currently not supported by ``occ``.

    username
        The username of the database to convert to.

    hostname
        The hostname of the database to convert to.

    database
        The name of the database to convert to.

    port
        The port of the database to convert to. Default depending on dbtype.

    password
        The password of the database to convert to. Better use ``password_pillar``.

    password_pillar
        Pillar to look up the database password in.

    clear_schema
        Remove all tables from the destination database.
        This does not work with ``oci`` type.

    all_apps
        Create schema for all apps insteaf of only installed apps.

    chunk_size
        The maximum number of database rows to handle in a single query, bigger
        tables will be handled in chunks of this size. Lower this if the process
        runs out of memory during conversion. Defaults to 1000.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    if dbtype == config_system_get("dbtype"):
        raise SaltInvocationError(
            "`occ` does not allow migration between two databases of the same type."
        )

    if dbtype not in ["mysql", "pgsql", "oci"]:
        raise SaltInvocationError(
            "Migration to dbtype `{}` is not supported by `occ`.".format(dbtype)
        )

    if "oci" == dbtype and clear_schema:
        raise SaltInvocationError(
            "`occ` does not allow clear_schema for target databases of `oci` type."
        )

    if password is None and password_pillar is None:
        raise SaltInvocationError(
            "You need to specify a password for the database user."
        )

    args = [dbtype, username, hostname, database]
    flags = []
    params = []

    if port is not None:
        params.append(("port", port))

    if password_pillar:
        password = __salt__["pillar.get"](password_pillar)

        if password is None:
            raise CommandExecutionError(
                "It seems password_pillar '{}' is unset.".format(password_pillar)
            )

    if clear_schema:
        flags.append("clear-schema")

    if all_apps:
        flags.append("all-apps")

    if chunk_size:
        params.append(("chunk-size", chunk_size))

    out = occ(
        "db:convert-type",
        args,
        parameters=params,
        flags=flags,
        stdin=password,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"] or True


def files_cleanup(webroot=None, webuser=None):
    """
    Cleanup filecache.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.files_cleanup

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    out = occ("files:cleanup", json=False, webroot=webroot, webuser=webuser)

    return out["stdout"] or True


def files_repair_tree(dry_run=False, verbosity=0, webroot=None, webuser=None):
    """
    Try and repair malformed filesystem tree structures.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.files_repair_tree

    dry_run
        Only test, do not actually modify.

    verbosity
        1 normal output
        2 more verbose output
        3 debug

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = []

    if dry_run:
        flags.append("dry-run")

    if verbosity > 0:
        flags.append("-{}".format("v" * verbosity))

    out = occ("files:repair-tree", json=False, webroot=webroot, webuser=webuser)

    return out["stdout"] or True


def files_scan(
    user_id=None,
    path=None,
    all_users=False,
    unscanned=True,
    shallow=False,
    home_only=True,
    webroot=None,
    webuser=None,
):
    """
    Rescan filesystem.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.files_scan all_users=True

    user_id
        Rescan all files of the given user(s).

    path
        Limit rescan to this path, eg. ``/alica/files/Music``. The user_id
        is determined by the path and the user_id parameter and ``all`` are ignored.

    all_users
        Rescan files of all known users. Defaults to False.

    unscanned
        Only scan files which are marked as not fully scanned. Defaults to True.

    shallow
        Do not scan folders recursively. Defaults to False.

    home_only
        Only scan the home storage, ignoring any mounted external storage or share.
        Defaults to True.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    arguments = []
    flags = []
    params = []

    if path:
        params.append(("path", path))
    elif all_users:
        flags.append("all")
    elif user_id:
        if isinstance(user_id, str):
            arguments = [user_id]
        elif isinstance(user_id, list):
            arguments = user_id
    else:
        raise SaltInvocationError("Need all_users, user_id or path specified.")

    if unscanned:
        flags.append("unscanned")

    if shallow:
        flags.append("shallow")

    if home_only:
        flags.append("home-only")

    # claims to provide json output, does not
    out = occ(
        "files:scan",
        arguments,
        parameters=params,
        flags=flags,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"] or True


def files_scan_app_data(folder=None, webroot=None, webuser=None):
    """
    Rescan the AppData folder.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.files_scan_app_data

    folder
        The AppData subfolder to scan. Empty for root.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    arguments = []

    if folder is not None:
        arguments = [folder]

    # claims to support json, does not
    out = occ(
        "files:scan-app-data", arguments, json=False, webroot=webroot, webuser=webuser
    )

    return out["stdout"] or True


def files_transfer_ownership(
    source_user, destination_user, path=None, move=False, webroot=None, webuser=None
):
    """
    Move all files and folders to another user, including shares.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.files_transfer_ownership chad karen

    source_user
        Owner of files which shall be moved.

    destination_user:
        User who will be the new owner of the files.

    path
        Selectively provide the path to transfer.

    move
        Move data from source user to root directory of destination
        user, which must be empty. Defaults to False.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [source_user, destination_user]
    flags = []
    params = []

    if path is not None:
        params = [("path", path)]

    if move:
        flags.append("move")

    out = occ(
        "files:transfer-ownership",
        args,
        parameters=params,
        flags=flags,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"] or True


def group_add(groupid, display_name="", webroot=None, webuser=None):
    """
    Add a group.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.group_add fsociety

    groupid
        The Nextcloud group ID.

    display_name:
        Group name used in the web UI (can contain any characters).

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [groupid]
    params = []

    if display_name:
        params.append(("display-name", display_name))

    out = occ(
        "group:add",
        args,
        parameters=params,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"] or True


def group_adduser(group, user, webroot=None, webuser=None):
    """
    Add a user to a group.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.group_adduser fsociety mrrobot

    group
        Group to add the user to.

    user
        User to add to the group.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [group, user]

    out = occ("group:adduser", args, json=False, webroot=webroot, webuser=webuser)

    return out["stdout"] or True


def group_delete(groupid, webroot=None, webuser=None):
    """
    Delete a group.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.group_delete evilcorp

    groupid
        The Nextcloud group ID.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [groupid]

    out = occ(
        "group:delete",
        args,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"] or True


def group_exists(groupid, webroot=None, webuser=None):
    """
    Check if a group exists.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.group_exists fsociety

    groupid
        The Nextcloud group ID.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [groupid, "le7s_hop3_n0_0ne_cr34t3s_a_user_l1ke_thi5"]

    # Since group_list has a limit, we need to use another method
    # to reliably determine the existence of a group.
    # Using the occ command directly to not bloat the config of group_removeuser
    # to hide the error output.
    out = occ(
        "group:removeuser",
        args,
        json=False,
        expect_error=True,
        webroot=webroot,
        webuser=webuser,
    )

    if out["retcode"] == 0:
        raise CommandExecutionError(
            "Uhm, did you actually create a user named 'le7s_hop3_n0_0ne_cr34t3s_a_user_l1ke_thi5' and added it to group '{}'? Well, he's gone from that group now, sorry.".format(
                groupid
            )
        )

    if "group not found" in out["stdout"]:
        return False
    if "user not found" in out["stdout"]:
        return True

    raise CommandExecutionError(
        "An unexpected error occured while trying to determine if group '{}' exists. The output was:\n\nstdout:\n{}\n\nstderr:\n{}\n".format(
            groupid, out["stdout"], out["stderr"]
        )
    )


def group_list(limit=500, offset=0, webroot=None, webuser=None):
    """
    List configured groups and their users.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.group_list

    limit
        Maximum number of groups to retrieve. Defaults to 500.
        0 actually means zero, not unlimited (SQL ``LIMIT``).

    offset
        Offset for retrieving groups. Defaults to 0.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    params = [
        ("limit", limit),
        ("offset", offset),
    ]

    out = occ("group:list", parameters=params, webroot=webroot, webuser=webuser)

    return out["parsed"]


def group_removeuser(group, user, webroot=None, webuser=None):
    """
    Remove a user from a group.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.group_removeuser fsociety elliot

    group
        Group to remove the user from.

    user
        User to remove from the group.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [group, user]

    out = occ("group:removeuser", args, json=False, webroot=webroot, webuser=webuser)

    return out["stdout"] or True


def log_manage(backend=None, level=None, timezone=None, webroot=None, webuser=None):
    """
    Manage logging configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.log_manage backend=syslog level=info

    backend
        Set the logging backend [file, syslog, errorlog, systemd].

    level
        Set the log level [debug, info, warning, error, fatal].

    timezone
        Set the logging timezone.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    params = []

    if backend is not None:
        if backend not in ["file", "syslog", "errorlog", "systemd"]:
            raise SaltInvocationError("'{}' is not a valid backend.".format(backend))
        params.append(("backend", backend))

    if level is not None:
        if level not in ["debug", "info", "warning", "error", "fatal"]:
            raise SaltInvocationError("'{}' is not a valid log level.".format(backend))
        params.append(("level", level))

    if timezone is not None:
        params.append(("timezone", timezone))

    if not params:
        raise SaltInvocationError("No logging configuration was specified.")

    out = occ(
        "log:manage", parameters=params, json=False, webroot=webroot, webuser=webuser
    )

    return out["stdout"] or True


def log_tail(lines=10, webroot=None, webuser=None):
    """
    Tail the nextcloud logfile.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.log_tail 20

    lines
        The number of log entries to return. Defaults to 10.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [str(lines)]

    # claims to support json output, does not
    out = occ("log:tail", args, json=False, webroot=webroot, webuser=webuser)

    return out["stdout"]


def maintenance_data_fingerprint(webroot=None, webuser=None):
    """
    Update the system's data-fingerprint after a backup is restored.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.maintenance_data_fingerprint

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    out = occ(
        "maintenance:data-fingerprint", json=False, webroot=webroot, webuser=webuser
    )

    return out["stdout"] or True


def maintenance_mimetype_update_db(repair_filecache=False, webroot=None, webuser=None):
    """
    Update database mimetypes and filecache.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.maintenance_mimetype_update_db

    repair_filecache
        Repair filecache for all mimetypes, not just new ones.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = []

    if repair_filecache:
        flags.append("repair-filecache")

    out = occ(
        "maintenance:mimetype:update-db",
        json=False,
        flags=flags,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"] or True


def maintenance_mimetype_update_js(webroot=None, webuser=None):
    """
    Update ``mimetypelist.js``.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.maintenance_mimetype_update_js

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    out = occ(
        "maintenance:mimetype:update-js", json=False, webroot=webroot, webuser=webuser
    )

    return out["stdout"] or True


def maintenance_mode(enabled=True, webroot=None, webuser=None):
    """
    Set maintenance mode.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.maintenance_mode
        salt '*' nextcloud_server.maintenance_mode false

    enabled
        Enable maintenance mode. Defaults to True.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = ["on"] if enabled else ["off"]

    out = occ(
        "maintenance:mode", flags=flags, json=False, webroot=webroot, webuser=webuser
    )

    return out["stdout"] or True


def is_maintenance(webroot=None, webuser=None):
    """
    Check if maintenance mode is enabled.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.is_maintenance

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    out = occ("maintenance:mode", json=False, webroot=webroot, webuser=webuser)

    return "is currently enabled" in out["stdout"]


def maintenance_repair(include_expensive=False, webroot=None, webuser=None):
    """
    Repair this installation.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.maintenance_repair

    include_expensive
        Include resource and load expensive tasks. (?)

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = []

    if include_expensive:
        flags.append("include-expensive")

    out = occ(
        "maintenance:repair", flags=flags, json=False, webroot=webroot, webuser=webuser
    )

    return out["stdout"] or True


def maintenance_theme_update(webroot=None, webuser=None):
    """
    Apply custom theme changes.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.maintenance_theme_update

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    out = occ("maintenance:theme:update", json=False, webroot=webroot, webuser=webuser)

    return out["stdout"] or True


def maintenance_update_htaccess(webroot=None, webuser=None):
    """
    Updates the ``.htaccess`` file.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.maintenance_update_htaccess

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    out = occ(
        "maintenance:update:htaccess", json=False, webroot=webroot, webuser=webuser
    )

    return out["stdout"] or True


def notification_generate(
    user_id, short_message, long_message="", webroot=None, webuser=None
):
    """
    Generate a notification for the given user.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.notification_generate phillip_price "Pwn3d!"

    user_id
        User ID of the user to notify.

    short_message
        Short message to be sent to the user (max. 255 characters).

    long_message
        Long message to be sent to the user (max. 4000 characters).
        Defaults to empty.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [user_id, short_message]
    params = []

    if long_message:
        params.append(("long-message", long_message))

    out = occ(
        "notification:generate",
        args,
        parameters=params,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"] or True


def preview_repair(
    dry_run=False, verbosity=0, delete=False, webroot=None, webuser=None
):
    """
    Distribute the existing previews into subfolders.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.preview_repair

    dry_run
        Do not actually create, move or delete any files. Defaults to False.

    delete
        Delete instead of migrate. Useful if there are too many items to migrate.
        Defaults to False.

    verbosity
        1 normal output
        2 more verbose output
        3 debug

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = ["batch"]

    if dry_run:
        flags.append("dry")

    if verbosity > 0:
        flags.append("-{}".format("v" * verbosity))

    if delete:
        flags.append("delete")

    out = occ(
        "preview:repair", flags=flags, json=False, webroot=webroot, webuser=webuser
    )

    return out["stdout"] or True


def preview_reset_rendered_texts(
    dry_run=False, verbosity=0, webroot=None, webuser=None
):
    """
    Delete all generated avatars and previews of text and ``.md`` files.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.preview_repair

    dry_run
        Do not actually delete any files. Defaults to False.

    verbosity
        1 normal output
        2 more verbose output
        3 debug

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = []

    if dry_run:
        flags.append("dry")

    if verbosity > 0:
        flags.append("-{}".format("v" * verbosity))

    out = occ(
        "preview:reset-rendered-texts",
        flags=flags,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"] or True


def theming_config_get(name=None, webroot=None, webuser=None):
    """
    Get theming app config values.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.theming_config_get imprintUrl

    name
        Name of the theming config value to get [name, url, imprintUrl,
        privacyUrl, slogan, color]. Empty for all.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [name] if name is not None else []

    # does not support json output
    out = occ("theming:config", args, json=False, webroot=webroot, webuser=webuser)

    parsed = yaml.safe_load(out["stdout"])

    if name is None:
        return {
            var: val for d in parsed["Current theming config"] for var, val in d.items()
        }

    if isinstance(parsed, str) and "currently not set" in parsed:
        return

    return out["stdout"].split("is currently set to ")[1]


def theming_config_set(name, value=None, webroot=None, webuser=None):
    """
    Set theming app config values.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.theming_config_set name H4xx3dcloud

    name
        Name of the theming config value to set [name, url, imprintUrl,
        privacyUrl, slogan, color].

    value
        Value to set the theming config to. Leave empty to reset
        the given config key to default.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [name]
    flags = []

    if value is not None:
        args.append(value)
    else:
        flags.append("reset")

    out = occ(
        "theming:config",
        args,
        flags=flags,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"] or True


def trashbin_cleanup(user_id=None, webroot=None, webuser=None):
    """
    Remove deleted files.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.trashbin_cleanup allsafe

    user_id
        Remove deleted files of the given user(s).
        Defaults to all users.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = []

    if user_id is None:
        user_id = []
        flags.append("all-users")

    args = user_id if isinstance(user_id, list) else [user_id]

    out = occ(
        "trashbin:cleanup",
        args,
        flags=flags,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"] or True


def trashbin_expire(user_id=None, webroot=None, webuser=None):
    """
    Expires the user's trashbin.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.trashbin_expire allsafe

    user_id
        Remove deleted files of the given user(s).
        Defaults to all users.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = []

    if user_id is None:
        user_id = []

    args = user_id if isinstance(user_id, list) else [user_id]

    out = occ(
        "trashbin:expire",
        args,
        flags=flags,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"] or True


def twofactorauth_enforce_status(webroot=None, webuser=None):
    """
    Check whether two factor authentication is enforced.
    Returns a mapping: {
        state: enabled/disabled/only_groups/except_groups
        groups: [<target groups>]
    }

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.twofactorauth_enforced

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    # does not support json output
    out = occ("twofactorauth:enforce", json=False, webroot=webroot, webuser=webuser)
    groups = []

    if "is enforced for members of the group" in out["stdout"]:
        state = "only_groups"
        groups = out["stdout"].split("group(s)")[1].strip().split(", ")
    elif "is enforced for all users, except members of" in out["stdout"]:
        state = "except_groups"
        groups = out["stdout"].split("except members of")[1].strip().split(", ")
    elif "is not enforced" in out["stdout"]:
        state = "disabled"
    elif "Two-factor authentication is enforced for all users" == out["stdout"].strip():
        state = "enabled"
    else:
        raise CommandExecutionError(
            "Failed parsing the output of occ twofactorauth:enforce. Output was:\n{}".format(
                out["stdout"]
            )
        )

    return {
        "state": state,
        "groups": groups,
    }


def twofactorauth_enforce(
    enable=True, only=None, exclude=None, webroot=None, webuser=None
):
    """
    Set two factor authentication enforcement status.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.twofactorauth_enforce

    enable
        Whether to enable or disable enforcing 2FA. Defaults to True.
        When False, ``only`` and ``exclude`` will have no effect.

    only
        Only enforce 2FA for groups in this list.

    exclude
        Generally enforce 2FA, except for groups in this list.
        Takes precedence before ``only``.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = ["on" if enable else "off"]
    params = []

    if enable:
        # DRY for parsing groups with different semantics
        for spec, param_name in [(exclude, "exclude"), (only, "group")]:
            if spec:
                if not isinstance(spec, list):
                    spec = [spec]
                for group in spec:
                    params.append((param_name, group))
                break

    # this will actually return the new status in stdout
    out = occ(
        "twofactorauth:enforce",
        flags=flags,
        parameters=params,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return True


def twofactorauth_state(user_id, include_providers=False, webroot=None, webuser=None):
    """
    Check the activation state of two factor authentication for a user.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.twofactorauth_state admin

    user_id
        User ID to check for.

    include_providers
        Do not only return True or False, but return a dictionary with
        keys ``enabled``, ``enabled_providers`` and ``disabled_provider``.
        Defaults to False.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [user_id]

    # pretends to provide json, but ignores the parameter
    out = occ("twofactorauth:state", args, json=False, webroot=webroot, webuser=webuser)

    enabled = out["stdout"].startswith(
        "Two-factor authentication is enabled for user " + user_id
    )

    if not include_providers:
        return enabled

    providers = yaml.safe_load("\n".join(out["stdout"].splitlines()[1:]))

    return {
        "enabled": enabled,
        "enabled_providers": providers.get("Enabled providers", []),
        "disabled_providers": providers.get("Disabled providers", []),
    }


def update_check(webroot=None, webuser=None):
    """
    Check for server and app updates.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.update_check

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    # does not support json output
    out = occ("update:check", json=False, webroot=webroot, webuser=webuser)

    if "Everything up to date" in out["stdout"]:
        return {}

    system = re.findall(
        r"^Nextcloud ([\d\.]+) is available", out["stdout"], re.MULTILINE
    )
    apps = re.findall(
        r"^Update for ([\S]+) to version ([\d\.]+) is available\.$",
        out["stdout"],
        re.MULTILINE,
    )
    count = re.findall(r"^([\d]+) update(s|) available", out["stdout"], re.MULTILINE)

    if not count or len(system) + len(apps) != int(count[0][0]):
        raise CommandExecutionError(
            "Something went wrong parsing the following Nextcloud output:\n\n{}".format(
                out["stdout"]
            )
        )

    ret = dict(apps)

    if system:
        ret["Nextcloud"] = system[0]

    return ret


def user_add(
    user_id,
    password=None,
    password_pillar=None,
    display_name="",
    group=None,
    webroot=None,
    webuser=None,
):
    """
    Add a user.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.user_add h4xx0r password=hunter1 group=[admin, pwn3d]

    user_id
        User ID used to login. Can only contain alphanumeric chars and ``-_@``.

    password
        The user's password. Better use password_pillar to avoid logs/caches.
        ``password`` or ``password_pillar`` is required.

    password_pillar
        The pillar key where the user's password can be looked up.
        ``password`` or ``password_pillar`` is required.

    display_name:
        User name used in the web UI (can contain any characters).

    group
        Group(s) the user should be added to (list or string).
        Nonexistant groups will be created automatically.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    if not re.fullmatch(r"[A-z0-9_@\-]+", user_id):
        raise SaltInvocationError(
            "The user ID seems to contain illegal characters. Can only contain alphanumeric chars and `-_@`."
        )

    if password is None and password_pillar is None:
        raise SaltInvocationError("Cannot create a user without a password.")

    args = [user_id]
    flags = ["password-from-env"]
    params = []

    if password_pillar:
        password = __salt__["pillar.get"](password_pillar)

        if password is None:
            raise CommandExecutionError(
                "Specified password_pillar '{}' is not set.".format(password_pillar)
            )

    env = {"OC_PASS": password}

    if display_name:
        params.append(("display-name", display_name))

    if group:
        if not isinstance(group, list):
            group = [group]
        for g in group:
            params.append(("group", g))

    out = occ(
        "user:add",
        args,
        parameters=params,
        flags=flags,
        env=env,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"] or True


def user_add_app_password(
    user_id, password=None, password_pillar=None, webroot=None, webuser=None
):
    """
    Add an app password for a user.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.user_add_app_password h4xx0r "correct horse battery staple"

    user_id
        User ID to add app password for.

    password
        The user's app password. Better use password_pillar to avoid logs/caches.
        ``password`` or ``password_pillar`` is required.

    password_pillar
        The pillar key where the user's app password can be looked up.
        ``password`` or ``password_pillar`` is required.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    if password is None and password_pillar is None:
        raise SaltInvocationError("Need to know which password to set.")

    args = [user_id]
    flags = ["password-from-env"]

    if password_pillar:
        password = __salt__["pillar.get"](password_pillar)

        if password is None:
            raise CommandExecutionError(
                "Specified password_pillar '{}' is not set.".format(password_pillar)
            )

    # needs to be NC_PASS, not OC_PASS
    env = {"NC_PASS": password}

    out = occ(
        "user:add-app-password",
        args,
        flags=flags,
        env=env,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"].splitlines()[1]


def user_delete(user_id, webroot=None, webuser=None):
    """
    Delete a user.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.user_delete admin

    user_id
        User ID of the user to delete.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [user_id]

    out = occ("user:delete", args, json=False, webroot=webroot, webuser=webuser)

    return out["stdout"] or True


def user_disable(user_id, webroot=None, webuser=None):
    """
    Disable a user.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.user_disable admin

    user_id
        User ID of the user to disable.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [user_id]

    out = occ("user:disable", args, json=False, webroot=webroot, webuser=webuser)

    return out["stdout"] or True


def user_enable(user_id, webroot=None, webuser=None):
    """
    Enable a user.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.user_enable admin

    user_id
        User ID of the user to disable.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [user_id]

    out = occ("user:enable", args, json=False, webroot=webroot, webuser=webuser)

    return out["stdout"] or True


def user_exists(user_id, webroot=None, webuser=None):
    """
    Check if a user exists.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.user_exists admin

    user_id
        User ID to check.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    # user_list might not return all users on large installations
    out = occ(
        "user:info", [user_id], expect_error=True, webroot=webroot, webuser=webuser
    )

    if not out["retcode"]:
        return True

    if out["retcode"] and "user not found" in out["stdout"]:
        return False

    raise CommandExecutionError(
        "An unexpected error occurred while checking for existence of user '{}'. Output was:\n\nstdout:\n{}\n\nstderr:\n{}\n".format(
            user_id, out["stdout"], out["stderr"]
        )
    )


def user_info(user_id, webroot=None, webuser=None):
    """
    Show user info.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.user_info h4xx0r

    user_id
        User ID of the user to disable.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [user_id]

    out = occ("user:info", args, webroot=webroot, webuser=webuser)

    return out["parsed"]


def user_enabled(user_id, webroot=None, webuser=None):
    """
    Check whether a user account is enabled.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.user_enabled h4xx0r

    user_id
        User ID of the user to check.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    info = user_info(user_id, webroot=webroot, webuser=webuser)

    return info["enabled"]


def user_lastseen(user_id, webroot=None, webuser=None):
    """
    Show when the user was logged in last time.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.user_lastseen h4xx0r

    user_id
        User ID of the user to disable.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [user_id]

    out = occ("user:lastseen", args, json=False, webroot=webroot, webuser=webuser)

    return out["stdout"]


def user_list(limit=500, offset=0, info=False, webroot=None, webuser=None):
    """
    List configured users.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.user_list

    limit
        Maximum number of users to retrieve. Defaults to 500.
        0 actually means zero, not unlimited (SQL ``LIMIT``).

    offset
        Offset for retrieving groups. Defaults to 0.

    info
        Show detailed info for users. Defaults to False.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = []
    params = [
        ("limit", limit),
        ("offset", offset),
    ]

    if info:
        flags.append("info")

    out = occ(
        "user:list", parameters=params, flags=flags, webroot=webroot, webuser=webuser
    )

    return out["parsed"]


def user_report(count_dirs=None, webroot=None, webuser=None):
    """
    Show how many users have access.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.user_report

    count_dirs
        Also count the numer of user directories in the database.
        Could time out on huge installations. Therefore, default
        depends on number of users: user_count < 500

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    flags = []

    if count_dirs:
        flags.append("count-dirs")

    # does not support json output
    out = occ("user:report", flags=flags, json=False, webroot=webroot, webuser=webuser)

    return out["stdout"]


def user_resetpassword(
    user_id, password=None, password_pillar=None, webroot=None, webuser=None
):
    """
    Reset a user's password.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.user_resetpassword admin hunter1

    user_id
        User ID to reset the password for.

    password
        The user's new password. Better use password_pillar to avoid logs/caches.
        ``password`` or ``password_pillar`` is required.

    password_pillar
        The pillar key where the user's new password can be looked up.
        ``password`` or ``password_pillar`` is required.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    if password is None and password_pillar is None:
        raise SaltInvocationError("Need to know which password to set.")

    args = [user_id]
    flags = ["password-from-env"]

    if password_pillar:
        password = __salt__["pillar.get"](password_pillar)

        if password is None:
            raise CommandExecutionError(
                "Specified password_pillar '{}' is not set.".format(password_pillar)
            )

    env = {"OC_PASS": password}

    out = occ(
        "user:resetpassword",
        args,
        flags=flags,
        env=env,
        json=False,
        webroot=webroot,
        webuser=webuser,
    )

    return out["stdout"] or True


def user_setting_delete(
    user_id, app, key, error_if_not_exists=False, webroot=None, webuser=None
):
    """
    Remove a user setting.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.user_setting_delete karen firstrunwizard show

    user_id
        User ID to delete the setting for.

    app
        Name of the app to delete the key for.

    key
        Name of the config to delete.

    error_if_not_exists
        Throw error if the config does not exit. Defaults to False.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    args = [user_id, app, key]
    flags = ["delete"]

    if error_if_not_exists:
        flags.append("error-if-not-exists")

    # claims to support json output, does not
    out = occ(
        "user:setting", args, flags=flags, json=False, webroot=webroot, webuser=webuser
    )

    return out["stdout"] or True


def user_setting_get(
    user_id, app=None, key=None, default=None, webroot=None, webuser=None
):
    """
    Get a user setting.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.user_setting_get core lang

    user_id
        User ID to get the setting(s) for.

    app
        Restrict the setting(s) to the given app. Empty to list all.

    key
        Setting key to get. Needs ``app`` set to work. Empty to list all.

    default
        Instead of raising an exception, return this default value.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    params = [user_id]
    # single string values are returned unquoted for some reason
    json = key is None

    if app:
        params.append(app)

        if key:
            params.append(key)

    out = occ(
        "user:setting",
        params,
        json=json,
        raise_error=False,
        webroot=webroot,
        webuser=webuser,
    )

    if not out["retcode"]:
        if json:
            return out["parsed"]
        return out["stdout"]
    if default is not None:
        return default

    raise CommandExecutionError(
        "Could not get user setting '{}' for user '{}'. Output was:\n{}".format(
            ":".join(params), user_id, out["stderr"]
        )
    )


def user_setting_set(
    user_id, app, key, value, update_only=False, webroot=None, webuser=None
):
    """
    Set a user setting.

    CLI Example:

    .. code-block:: bash

        salt '*' nextcloud_server.user_setting_set chad core lang en_NZ

    user_id
        User ID to set the setting for.

    app
        Name of the app to set the key for.

    key
        Name of the config to set.

    value
        The config value to set. Make sure it's in the correct format,
        especially booleans are tricky.

    update_only
        Only update existing values, do not add new ones.
        Defaults to False.

    webroot
        The path where Nextcloud is installed. Defaults to
        minion config value ``nextcloud_server.webroot``
        or ``/var/www/nextcloud``.

    webuser
        The web user account running Nextcloud, usually ``www-data``, ``apache``.
        Defaults to minion config value ``nextcloud_server.user`` or ``www-data``.
    """

    # I could find 'yes', true and 1, depending on the app

    # if isinstance(value, bool):
    #     value = 'yes' if value else 'no'

    args = [user_id, app, key, value]
    flags = []

    if update_only:
        flags.append("update-only")

    # claims to provide json output, does not
    out = occ(
        "user:setting", args, flags=flags, json=False, webroot=webroot, webuser=webuser
    )

    return out["stdout"] or True


def _php(script, json=True, webroot=None, webuser=None, ensure_apc=None):
    cmd = ["php"]

    if webroot is None:
        webroot = web_root
    if webuser is None:
        webuser = web_user
    if ensure_apc is None:
        ensure_apc = ensure_apc_global
    if ensure_apc:
        cmd += ["--define", "apc.enable_cli=1"]

    cmd += ["-r", script]
    out = __salt__["cmd.run_all"](
        shlex.join(cmd),
        cwd=webroot,
        runas=webuser,
    )
    if out["retcode"] == 0:
        if json:
            try:
                return salt.utils.json.loads(out["stdout"])
            except Exception as err:  # pylint: disable=broad-except
                raise CommandExecutionError(
                    f"Failed loading output: {err}\n\nOutput was:\n{out['stdout']}"
                )
        return out["stdout"]
    raise CommandExecutionError(
        "Failed running php script '{}'.\nstderr: {}\nstdout: {}".format(
            shlex.join(cmd), out["stderr"], out["stdout"]
        )
    )
