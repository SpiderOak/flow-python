"""
auto_updates.py

Automatic semaphor-backend updates source code.
"""

import os
import logging
import json
import errno

import semantic_version

from . import definitions


UPDATES_DIR = "updates"
BUILD_VERSION_FILE = "build-version.json"
LOG = logging.getLogger("flow")


def get_newest_backend(db_dir):
    """Returns the newest backend available on the system.
    It can be either the system installed or a downloaded auto-update.
    Arguments:
    db_dir : string, application data directory.
    It returns a tuple with:
    - semaphor-backend/flowappglue binary path.
    - schema directory path.
    - semaphor version string.
    """
    installed_app_path = definitions.get_app_path()
    installed_version = _build_version(installed_app_path)
    update = _get_newest_update(db_dir)
    app_path = None
    version_str = None
    if not update:
        LOG.debug(
            "no updates, using system "
            "installed semaphor: (%s,%s)",
            installed_app_path,
            installed_version,
        )
        app_path = installed_app_path
        version_str = str(installed_version)
    elif installed_version >= update[1]:
        LOG.debug(
            "system installed: (%s,%s) is newer than "
            "latest update: (%s,%s)",
            installed_app_path,
            installed_version,
            update[0],
            update[1],
        )
        app_path = installed_app_path
        version_str = str(installed_version)
    else:
        LOG.debug(
            "latest update: (%s,%s) is newer than "
            "system installed: (%s,%s)",
            update[0],
            update[1],
            installed_app_path,
            installed_version,
        )
        app_path = update[0]
        version_str = str(update[1])
    return (
        definitions.get_flowappglue_path(app_path),
        definitions.get_schema_path(app_path),
        version_str,
    )


def _get_newest_update(db_dir):
    """Returns the newest auto-update available on the updates application
    data directory.
    Arguments:
    db_dir : string, application data directory.
    Returns a tuple with:
    - resources/app data directory path.
    - semantic_version.Version object of the update.
    """
    updates_dir_path = os.path.join(db_dir, UPDATES_DIR)
    updates_dirs = []
    try:
        updates_dirs = os.listdir(updates_dir_path)
    except OSError as os_err:
        if os_err.errno != errno.ENOENT:
            raise
    updates = [
        (
            os.path.join(
                updates_dir_path,
                update_dir,
                definitions.auto_update_app_dir(),
            ),
            _update_dir_version(os.path.join(updates_dir_path, update_dir)),
        )
        for update_dir in updates_dirs
        if os.path.isdir(os.path.join(updates_dir_path, update_dir))
    ]
    updates.sort(key=lambda update: update[1])
    if updates:
        LOG.debug("auto-updates found: %s", updates)
        return updates[-1]
    else:
        LOG.debug("no auto-updates found")
        return None


def _update_dir_version(dir_path):
    """Returns the semantic_version.Version of the given
    auto-update directory path.
    Arguments:
    dir_path : string, root auto-update directory path.
    """
    app_subdir_path = os.path.join(
        dir_path,
        definitions.auto_update_app_dir(),
    )
    return _build_version(app_subdir_path)


def _build_version(app_path):
    """Given the resources/app path, it returns the corresponding
    semantic_version.Version.
    Arguments:
    app_path : string, resources/app directory of the Semaphor instance.
    """
    build_version_path = os.path.join(app_path, BUILD_VERSION_FILE)
    with open(build_version_path, "r") as bvf:
        build_version_map = json.load(bvf)
    bvs = "%s-%s" % (
        build_version_map["version"],
        build_version_map["build"],
    )
    return semantic_version.Version(bvs)
