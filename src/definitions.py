"""
definitions.py
"""

import os
import sys


# Sane default definitions
DEFAULT_SERVER = "flow.spideroak.com"
DEFAULT_PORT = "443"
DEFAULT_USE_TLS = "true"
DEFAULT_URI = "flow.spideroak.com"

_CONFIG_DIR_NAME = "flow-python"

# OS specifics defaults
_CONFIG_OS_PATH_MAP = {
    "darwin": "Library/Application Support",
    "linux2": ".config",
    "win32": r"AppData\Local",
}

# Needed for Python 3.5
_CONFIG_OS_PATH_MAP['linux'] = _CONFIG_OS_PATH_MAP['linux2']

# We add '%s' to support auto-updates new packaging
_DEFAULT_APP_OSX_PATH = "/Applications/Semaphor.app/%sContents/Resources/app"
_DEFAULT_APP_LINUX_RPM_PATH = "/opt/Semaphor-linux-x64/%sresources/app"
_DEFAULT_APP_LINUX_DEB_PATH = "/usr/share/semaphor/%sresources/app"
_DEFAULT_APP_WINDOWS_PATH = r"Semaphor\%sresources\app"

# Default dirs and binaries
_DEFAULT_ATTACHMENT_DIR = "downloads"
_DEFAULT_SCHEMA_DIR = "schema"
_EXE_EXT = ".exe" if sys.platform == "win32" else ""
_DEFAULT_FLOWAPPGLUE_BINARY_DEV_NAME = "flowappglue%s" % _EXE_EXT
_DEFAULT_FLOWAPPGLUE_BINARY_PROD_NAME = "semaphor-backend%s" % _EXE_EXT


def _update_replace(path, update, update_part):
    """Formats the 'path' with 'update_part' if 'update' is True.
    If 'update' is False, then the '%s' is replaced by an empty string.
    """
    return path % (update_part if update else "")


def _osx_app_path(update=False):
    """Returns the default application directory for OSX."""
    return _update_replace(
        _DEFAULT_APP_OSX_PATH,
        update,
        "Contents/Resources/",
    )


def _linux_app_path(update=False):
    """Returns the default application directory for Linux
    depending on the packaging (deb or rpm).
    """
    # check if RPM first
    rpm_path = _update_replace(
        _DEFAULT_APP_LINUX_RPM_PATH,
        update,
        "resources/",
    )
    if os.path.exists(rpm_path):
        return rpm_path
    # otherwise return DEB
    return _update_replace(
        _DEFAULT_APP_LINUX_DEB_PATH,
        update,
        "resources/",
    )


def _windows_app_path(update=False):
    """Returns the default application directory for Windows."""
    return os.path.join(
        os.environ["ProgramFiles"],
        _update_replace(
            _DEFAULT_APP_WINDOWS_PATH,
            update,
            "resources\\",
        ),
    )


def _get_home_directory():
    """Returns a string with the home directory of the current user.
    Returns $HOME for Linux/OSX and %USERPROFILE% for Windows.
    """
    return os.path.expanduser("~")


def _get_config_path():
    """Returns the default semaphor config path."""
    return os.path.join(
        _get_home_directory(),
        _CONFIG_OS_PATH_MAP[sys.platform],
        _CONFIG_DIR_NAME,
    )


_APP_OS_PATH_MAP = {
    "darwin": _osx_app_path,
    "linux2": _linux_app_path,
    "win32": _windows_app_path,
}

# Needed for Python3.5
_APP_OS_PATH_MAP['linux'] = _APP_OS_PATH_MAP['linux2']


def get_default_db_path():
    """Returns the default db path depending on the platform,
    which in all platforms is the config path.
    E.g. on OSX it would be:
    $HOME/Library/Application Support/flow-python.
    """
    return _get_config_path()


def _get_app_path():
    """Returns the app path depending on the platform.
    It checks if the auto-updates version of Semaphor is installed.
    Otherwise, it returns the default app path.
    """
    app_path_func = _APP_OS_PATH_MAP[sys.platform]
    app_path = app_path_func(update=True)
    if not os.path.exists(app_path):
        app_path = app_path_func(update=False)
    return app_path


def get_default_schema_path():
    """Returns the default schema directory depending on the platform.
    E.g. on OSX it would be:
    /Applications/Semaphor.app/Contents/Resources/app/schema.
    """
    app_path = _get_app_path()
    return os.path.join(
        app_path,
        _DEFAULT_SCHEMA_DIR,
    )


def get_default_attachment_path():
    """Returns the default attachment directory depending on the platform.
    E.g. on OSX it would be:
    $HOME/Library/Application Support/flow-python/downloads.
    """
    return os.path.join(_get_config_path(), _DEFAULT_ATTACHMENT_DIR)


def get_default_flowappglue_path():
    """Returns a string with the absolute path for
    the flowappglue binary; the return value depends on the platform.
    """
    app_path = _get_app_path()
    flowappglue_path = os.path.join(
        app_path,
        _DEFAULT_FLOWAPPGLUE_BINARY_PROD_NAME,
    )
    if os.path.isfile(flowappglue_path):
        return flowappglue_path
    flowappglue_path = os.path.join(
        app_path,
        _DEFAULT_FLOWAPPGLUE_BINARY_DEV_NAME,
    )
    return flowappglue_path
