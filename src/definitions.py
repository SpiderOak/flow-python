"""
definitions.py

Main definitions and platform specific functionality.
"""

import os
import sys


# Sane default definitions
DEFAULT_SERVER_HOST = "flow.spideroak.com"
DEFAULT_SERVER_PORT = "443"
DEFAULT_KEY_SERVER_HOST = "flow.spideroak.com"
DEFAULT_KEY_SERVER_PORT = "443"
DEFAULT_USE_TLS = "true"
DEFAULT_URI = "flow.spideroak.com"
DEFAULT_AUTO_UPDATE_PK = "zm5MU5d4M+an/ndE1dHrtbLfpNj1BJUBNEcJJpUWi70="

_CONFIG_DIR_NAME = "flow-python"

# OS specifics defaults
_CONFIG_OS_PATH_MAP = {
    "darwin": "Library/Application Support",
    "linux2": ".config",
    "win32": r"AppData\Local",
}

# Needed for Python 3.5
_CONFIG_OS_PATH_MAP['linux'] = _CONFIG_OS_PATH_MAP['linux2']

_DEFAULT_APP_OSX_PATH = "/Applications/Semaphor.app/Contents/Resources/app"
_DEFAULT_APP_LINUX_RPM_PATH = "/opt/Semaphor-linux-x64/resources/app"
_DEFAULT_APP_LINUX_DEB_PATH = "/usr/share/semaphor/resources/app"
_DEFAULT_APP_WINDOWS_PATH = r"Semaphor\resources\app"

# Default dirs and binaries
_DEFAULT_ATTACHMENT_DIR = "downloads"
_DEFAULT_SCHEMA_DIR = "schema"
_EXE_EXT = ".exe" if sys.platform == "win32" else ""
_DEFAULT_FLOWAPPGLUE_BINARY_DEV_NAME = "flowappglue%s" % _EXE_EXT
_DEFAULT_FLOWAPPGLUE_BINARY_PROD_NAME = "semaphor-backend%s" % _EXE_EXT


class AutoUpdatesError(Exception):
    """Automatic updates specific error."""
    pass


def auto_update_app_dir():
    """Return the relative resources/app directory
    depending on the platform.
    """
    if sys.platform == "darwin":
        return os.path.join("Contents", "Resources", "app")
    elif sys.platform in ("linux", "linux2", "win32"):
        return os.path.join("resources", "app")
    else:
        raise AutoUpdatesError("unknown platform: %s" % sys.platform)


def _osx_app_path():
    """Returns the default application directory for OSX."""
    return _DEFAULT_APP_OSX_PATH


def _linux_app_path():
    """Returns the default application directory for Linux
    depending on the packaging (deb or rpm).
    """
    # check if RPM first
    if os.path.exists(_DEFAULT_APP_LINUX_RPM_PATH):
        return _DEFAULT_APP_LINUX_RPM_PATH
    # otherwise return DEB
    return _DEFAULT_APP_LINUX_DEB_PATH


def _windows_app_path():
    """Returns the default application directory for Windows."""
    return os.path.join(os.environ["ProgramFiles"],
                        _DEFAULT_APP_WINDOWS_PATH)


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


def get_default_attachment_path():
    """Returns the default attachment directory depending on the platform.
    E.g. on OSX it would be:
    $HOME/Library/Application Support/flow-python/downloads.
    """
    return os.path.join(_get_config_path(), _DEFAULT_ATTACHMENT_DIR)


def get_app_path():
    """Returns the app path for the current platform."""
    return _APP_OS_PATH_MAP[sys.platform]()


def get_schema_path(app_path):
    """Returns the default schema directory depending on the platform.
    E.g. on OSX it would be:
    /Applications/Semaphor.app/Contents/Resources/app/schema.
    """
    return os.path.join(app_path, _DEFAULT_SCHEMA_DIR)


def get_flowappglue_path(app_path):
    """Returns a string with the absolute path for
    the flowappglue binary; the return value depends on the platform.
    """
    flowappglue_path = os.path.join(
        app_path,
        _DEFAULT_FLOWAPPGLUE_BINARY_PROD_NAME)
    if os.path.isfile(flowappglue_path):
        return flowappglue_path
    flowappglue_path = os.path.join(
        app_path,
        _DEFAULT_FLOWAPPGLUE_BINARY_DEV_NAME)
    return flowappglue_path
