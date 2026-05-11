"""Configuration and metadata management for the Template Manager.

This module handles disk I/O for JSON configuration files. It establishes
a hierarchy for locating the main config file (prioritizing a studio-wide
environment variable before falling back to the local user directory) and
manages the reading/writing of custom template metadata.

Module-level constants in this file define the on-disk locations of every
database file the plugin uses, as well as fallback defaults used by the
scanner when project metadata cannot be parsed from a ``.nk`` file.

Attributes:
    STUDIO_ENV_VAR (str): Name of the environment variable consulted first
        for the location of the configuration file. Setting this to an
        existing path lets a studio override every artist's local
        configuration with a centrally managed file.
    CONFIG_ROOT (str): Absolute path to the directory where Template Manager
        stores its per-user configuration and database files. Defaults to
        ``~/.nuke/Template_Manager``.
    LOCAL_CONFIG_PATH (str): Absolute path to the local configuration JSON
        file used when ``STUDIO_ENV_VAR`` is unset or points to a missing
        file.
    DEFAULT_TEMPLATE_PATH (str): Hardcoded fallback directory used to
        resolve template paths when no path is configured. Defaults to
        ``~/.nuke/templates``.
    CACHE_PATH (str): Absolute path to the scanner cache JSON file, used by
        :mod:`saves` to memoize parsed node data between launches.
    METADATA_PATH (str): Absolute path to the manual user tag database JSON
        file, used by :mod:`saves` to persist per-template tag overrides.
    AUTO_TAGS_PATH (str): Absolute path to the auto-tagging rules JSON file,
        loaded and saved by :mod:`saves` and edited via the
        :class:`ui.AutoTagRulesDialog` UI.
    MAX_FILE_SIZE_BYTES (int): Hard limit (in bytes) above which the scanner
        refuses to parse a ``.nk`` file. Files exceeding this threshold are
        flagged with the ``FILE_TOO_LARGE`` status and skipped.
    DEFAULT_PROJECT_FPS (float): Fallback frames-per-second value used when
        a template's ``Root`` block contains no ``fps`` entry.
    DEFAULT_PROJECT_RESOLUTION (tuple[int, int]): Fallback ``(width, height)``
        used when a template's ``Root`` block contains no ``format`` entry.
    DEFAULT_PROJECT_COLORSPACE (str): Fallback colour management value used
        when a template's ``Root`` block contains neither ``OCIO_config``
        nor ``colorManagement`` entries.
"""

import os
import json
from typing import List

STUDIO_ENV_VAR = "STUDIO_TEMPLATE_CONFIG"
CONFIG_ROOT = os.path.expanduser("~/.nuke/Template_Manager")
LOCAL_CONFIG_PATH = os.path.join(CONFIG_ROOT, "templatemanager.json")
DEFAULT_TEMPLATE_PATH = os.path.expanduser("~/.nuke/templates")

CACHE_PATH = os.path.join(CONFIG_ROOT, "scanner_cache.json")
METADATA_PATH = os.path.join(CONFIG_ROOT, "template_metadata.json")
AUTO_TAGS_PATH = os.path.join(CONFIG_ROOT, "auto_tags.json")

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024
DEFAULT_PROJECT_FPS = 24.0
DEFAULT_PROJECT_RESOLUTION = (2048, 1556)
DEFAULT_PROJECT_COLORSPACE = "Nuke"


def get_config_path() -> str:
    """Determine the absolute path to the active configuration file.

    The function consults two sources, in order of priority:

    1. The environment variable named by :data:`STUDIO_ENV_VAR`. If that
       variable is set and points to a path that exists on disk, the
       function returns it unchanged. This allows a studio pipeline to
       deploy a centrally managed config file to every artist without
       touching their local home directory.
    2. The local path :data:`LOCAL_CONFIG_PATH` under the user's home
       directory. If the parent directory does not yet exist it is created
       (along with any missing intermediates) so subsequent writes succeed.

    Returns:
        str: Absolute path to the JSON configuration file the plugin
        should read from and write to for this session. The returned
        path may not yet exist on disk; callers must handle missing
        files themselves.
    """
    studio_path = os.getenv(STUDIO_ENV_VAR)
    if studio_path and os.path.exists(studio_path):
        return studio_path
    os.makedirs(os.path.dirname(LOCAL_CONFIG_PATH), exist_ok=True)
    return LOCAL_CONFIG_PATH


def load_config_data() -> dict:
    """Load and parse the main configuration JSON file.

    Resolves the active config path via :func:`get_config_path` and reads
    it as UTF-8 encoded JSON. Any error during file access or JSON
    decoding is caught and logged to standard output; the function then
    returns an empty dictionary so the rest of the plugin can continue
    with default behaviour rather than crashing.

    Returns:
        dict: The parsed top-level JSON object from the configuration
        file, or an empty dictionary if the file does not exist, cannot
        be read, or contains invalid JSON.
    """
    config_path = get_config_path()
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            print(f"Error reading config: {e}")
    return {}


def get_effective_template_paths() -> List[str]:
    """Retrieve every existing directory the scanner should index.

    The function reads the configuration file via :func:`load_config_data`
    and resolves the effective list of template root directories using
    the following fallback chain:

    1. The ``template_paths`` key, expected to be a list of strings.
    2. The legacy ``template_path`` key, expected to be a single string;
       wrapped in a one-element list for backward compatibility with
       configurations produced by earlier plugin versions.
    3. If neither key is present or yields any valid directory,
       :data:`DEFAULT_TEMPLATE_PATH` is created on disk (if it does
       not already exist) and returned as the sole fallback.

    All candidate paths are filtered through :func:`os.path.isdir`, so
    stale entries pointing at deleted directories are silently dropped
    rather than producing errors during scanning.

    Returns:
        list[str]: A list of absolute directory paths that currently
        exist on disk and should be scanned for ``.nk`` templates.
        Always contains at least one entry, since
        :data:`DEFAULT_TEMPLATE_PATH` is created and returned when no
        configured path resolves.
    """
    data = load_config_data()
    paths = data.get("template_paths", [])
    if not paths:
        legacy_path = data.get("template_path")
        if isinstance(legacy_path, str):
            paths = [legacy_path]

    valid_paths = [p for p in paths if os.path.isdir(p)]

    if not valid_paths:
        os.makedirs(DEFAULT_TEMPLATE_PATH, exist_ok=True)
        return [DEFAULT_TEMPLATE_PATH]
    return valid_paths


def get_tags() -> List[str]:
    """Retrieve the globally configured list of available tag strings.

    Reads the ``tags`` key from the main configuration file. The returned
    list is intended to serve as the master vocabulary shown in the UI's
    tag autocomplete and batch-tagging dialogs. It is independent of the
    per-template manual tags stored in the metadata database.

    Returns:
        list[str]: The list of predefined tag strings, in the order they
        appear in the configuration file. Returns an empty list if the
        configuration file is missing or contains no ``tags`` entry.
    """
    config = load_config_data()
    return config.get("tags", [])


def use_folder_categories() -> bool:
    """Check whether the UI should group templates by parent folder.

    When this setting is enabled, the main Template Manager dialog
    organises templates into a hierarchical tree mirroring their
    on-disk folder structure. When disabled, templates are presented
    in a flat list.

    Returns:
        bool: ``True`` if folder-based categorisation is enabled
        (the default when the key is absent), ``False`` if the user
        has explicitly opted out via the configuration file.
    """
    return load_config_data().get("use_folder_categories", True)