"""Storage and file I/O management for the Template Manager.

This module owns every read and write performed against the plugin's
on-disk JSON databases:

* The scanner cache (:data:`settings.CACHE_PATH`), which memoizes parsed
  node lists by file modification time so repeat launches do not re-parse
  unchanged ``.nk`` files.
* The manual metadata store (:data:`settings.METADATA_PATH`), which holds
  the per-file tags an artist has assigned by hand.
* The auto-tag rule store (:data:`settings.AUTO_TAGS_PATH`), which holds
  the user-editable rules consumed by :func:`scanner.get_auto_tags`.

The module also exposes :func:`get_save_path`, a helper used by the Save
Template flows in :mod:`main` and :mod:`ui` to compute the final on-disk
location of a newly-saved template, optionally with auto-versioning.

Attributes:
    DEFAULT_TAG_RULES (dict): The factory-default auto-tagging rule set
        written to disk the first time the user launches the plugin. Each
        key is a tag name, and each value is a dictionary describing a
        matching rule with the keys ``type`` (one of ``"any"``, ``"all"``,
        ``"count"``), ``nodes`` (a list of lowercase substrings to match
        against script node class names) and, for the ``"count"`` type,
        a ``threshold`` integer.
"""

import os
import json
import re
from typing import List
from . import settings

DEFAULT_TAG_RULES = {
    "Keying": {
        "type": "any",
        "nodes": ["primatte", "keylight", "ibkgizmo"]
    },
    "Denoise": {
        "type": "any",
        "nodes": ["reducenoise", "denoise", "neatvideo"]
    },
    "CG Rebuild": {
        "type": "count",
        "nodes": ["shuffle"],
        "threshold": 6
    },
    "Projection": {
        "type": "all",
        "nodes": ["card", "scanlinerender"]
    }
}


def load_cache() -> dict:
    """Load the scanner cache from disk.

    The cache is a JSON document keyed by absolute template path. Each
    entry records the modification time of the source ``.nk`` file along
    with the parsed node list and metadata, allowing the scanner to skip
    re-parsing files whose ``mtime`` has not changed since the last run.

    The function is tolerant of a missing or corrupted cache: in either
    case it returns an empty dictionary so the scanner falls back to a
    full parse rather than raising an exception.

    Returns:
        dict: The cache mapping ``{path: cache_entry}``, or an empty
        dictionary if the cache file does not exist or cannot be parsed
        as JSON.
    """
    if not os.path.exists(settings.CACHE_PATH):
        return {}
    try:
        with open(settings.CACHE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(data: dict) -> None:
    """Serialize the scanner cache to disk.

    Writes the supplied dictionary to :data:`settings.CACHE_PATH` as
    pretty-printed UTF-8 JSON, creating the parent directory if it does
    not already exist. The full cache is rewritten on every call;
    incremental updates are the caller's responsibility.

    Args:
        data: The full cache mapping ``{path: cache_entry}`` to persist.
            The structure is opaque to this function; the scanner is the
            sole producer and consumer of its contents.
    """
    os.makedirs(os.path.dirname(settings.CACHE_PATH), exist_ok=True)
    with open(settings.CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


def load_metadata() -> dict:
    """Load the manual user tag database from disk.

    The metadata file holds an artist's per-template tag overrides as a
    JSON object keyed by template filename (basename, not absolute path).
    Each value is a list of tag strings. The function tolerates a missing
    or corrupted file by returning an empty dictionary, so launching the
    plugin for the first time on a fresh machine does not error.

    Returns:
        dict: Mapping ``{filename: [tags]}`` of every template that has
        had manual tags assigned, or an empty dictionary if the file
        does not exist or is invalid.
    """
    if not os.path.exists(settings.METADATA_PATH):
        return {}
    try:
        with open(settings.METADATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_metadata(filename: str, tags: List[str]) -> None:
    """Update the tags for a single template and persist the database.

    Reads the existing metadata database, replaces the entry for the
    given filename with the supplied tag list, and writes the entire
    database back to disk. The parent directory is created if missing.

    The read-modify-write cycle is performed on every call: callers
    issuing many updates in tight succession will incur one full disk
    round-trip per call. Batch operations should accumulate changes in
    memory and write once if performance is a concern.

    Args:
        filename: The basename of the template ``.nk`` file (no
            directory component, no extension stripping). Used as the
            key in the metadata dictionary.
        tags: The complete list of tag strings to associate with the
            template. The previous tag list for this filename, if any,
            is replaced wholesale.
    """
    data = load_metadata()
    data[filename] = tags
    os.makedirs(os.path.dirname(settings.METADATA_PATH), exist_ok=True)
    with open(settings.METADATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


def load_auto_tag_rules() -> dict:
    """Load the auto-tagging rule set from disk, seeding defaults if absent.

    On first launch, when the rules file does not yet exist, the
    function writes :data:`DEFAULT_TAG_RULES` to disk and returns it,
    so subsequent calls see a populated rule set. If the file exists but
    cannot be parsed as JSON the function logs a warning and falls back
    to the defaults without overwriting the corrupted file, allowing the
    user to inspect and recover their custom rules manually.

    Returns:
        dict: Mapping ``{tag_name: rule_dict}`` describing every
        automatic tagging rule. See :data:`DEFAULT_TAG_RULES` for the
        expected schema of each rule.
    """
    if not os.path.exists(settings.AUTO_TAGS_PATH):
        os.makedirs(os.path.dirname(settings.AUTO_TAGS_PATH), exist_ok=True)
        with open(settings.AUTO_TAGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_TAG_RULES, f, indent=4)
        return DEFAULT_TAG_RULES

    try:
        with open(settings.AUTO_TAGS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        print("Warning: auto_tags.json is corrupted. Using default rules.")
        return DEFAULT_TAG_RULES


def save_auto_tag_rules(rules_dict: dict) -> None:
    """Persist a modified auto-tagging rule set to disk.

    Writes the supplied dictionary to :data:`settings.AUTO_TAGS_PATH` as
    pretty-printed UTF-8 JSON, creating the parent directory if needed.
    Validation of the rule schema is the caller's responsibility; this
    function blindly serialises whatever it is given.

    Args:
        rules_dict: The complete rule set to persist. Each key is a tag
            name and each value is a rule dictionary matching the schema
            described in :data:`DEFAULT_TAG_RULES`.
    """
    os.makedirs(os.path.dirname(settings.AUTO_TAGS_PATH), exist_ok=True)
    with open(settings.AUTO_TAGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(rules_dict, f, indent=4)


def get_save_path(folder_path: str, base_name: str, auto_version: bool = True) -> str:
    """Compute the final on-disk path for a template about to be saved.

    Behaviour depends on the ``auto_version`` flag:

    * When ``auto_version`` is ``False`` the function returns
      ``{folder_path}/{base_name}.nk`` with forward-slash normalisation
      but no further processing. Overwrite checks are left to the caller.
    * When ``auto_version`` is ``True`` the function scans
      ``folder_path`` for any existing file matching the pattern
      ``{base_name}_v##.nk`` (case-insensitive), determines the highest
      version number found, and returns a path one greater, zero-padded
      to two digits (for example ``base_v07.nk`` after seeing ``v06``).
      If no matching files exist the returned version is ``v01``.

    The function does not create any directories or files; it only
    computes the path string. The caller is responsible for ensuring
    the target directory exists before writing.

    Args:
        folder_path: The absolute directory where the template will be
            written. Need not exist yet; non-existent folders simply
            yield a version count of zero.
        base_name: The template stem with no extension and no version
            suffix (for example ``"keying_core"``, not
            ``"keying_core_v03.nk"``).
        auto_version: If ``True`` (the default), append the next free
            ``_v##`` suffix. If ``False``, return the un-versioned path
            and leave overwrite handling to the caller.

    Returns:
        str: The absolute path the template should be written to, with
        backslashes normalised to forward slashes for Nuke compatibility.
    """
    if not auto_version:
        return os.path.join(folder_path, f"{base_name}.nk").replace("\\", "/")

    max_v = 0
    version_pattern = re.compile(rf"^{re.escape(base_name)}_v(\d+)\.nk$", re.IGNORECASE)

    if os.path.exists(folder_path):
        for f in os.listdir(folder_path):
            match = version_pattern.match(f)
            if match:
                max_v = max(max_v, int(match.group(1)))

    return os.path.join(folder_path, f"{base_name}_v{max_v + 1:02d}.nk").replace("\\", "/")