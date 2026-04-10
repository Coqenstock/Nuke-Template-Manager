"""Configuration and metadata management for the Template Manager.

This module handles disk I/O for JSON configuration files. It establishes 
a hierarchy for locating the main config file (prioritizing a studio-wide 
environment variable before falling back to the local user directory) and 
manages the reading/writing of custom template metadata.
"""

import os
import json

STUDIO_ENV_VAR = "STUDIO_TEMPLATE_CONFIG"
LOCAL_CONFIG_PATH = os.path.expanduser("~/.nuke/Template_Manager/templatemanager.json")
DEFAULT_TEMPLATE_PATH = os.path.expanduser("~/.nuke/templates")
METADATA_PATH = os.path.expanduser("~/.nuke/Template_Manager/template_metadata.json")

def get_config_path() -> str:
    """Determines the absolute path to the active configuration file.

    Checks the system environment for `STUDIO_TEMPLATE_CONFIG` to allow for 
    centralized pipeline deployment. If not found, defaults to the local 
    `~/.nuke/` directory, creating the parent folders if they do not exist.

    Returns:
        str: The absolute path to the configuration JSON file.
    """
    studio_path = os.getenv(STUDIO_ENV_VAR)
    if studio_path and os.path.exists(studio_path):
        return studio_path
    os.makedirs(os.path.dirname(LOCAL_CONFIG_PATH), exist_ok=True)
    return LOCAL_CONFIG_PATH

def load_config_data() -> dict:
    """Loads and parses the main configuration JSON file.

    Returns:
        dict: The parsed JSON data, or an empty dictionary if the file 
        cannot be read or does not exist.
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

def get_effective_template_paths() -> list[str]:
    """Retrieves all valid directories to scan for Nuke templates.

    This function reads the configuration file and filters out any paths 
    that do not physically exist on disk. It also includes fallback logic 
    to support legacy configuration formats (`template_path` string) and 
    a hardcoded default directory.

    Returns:
        list[str]: A list of valid, existing directory paths.
    """
    data = load_config_data()
    paths = data.get("template_paths", [])
    if not paths:
        legacy_path = data.get("template_path")
        if isinstance(legacy_path, str):
            paths = [legacy_path]
    valid_paths = [p for p in paths if os.path.isdir(p)]
    if not valid_paths:
        if os.path.isdir(DEFAULT_TEMPLATE_PATH):
            return [DEFAULT_TEMPLATE_PATH]
        return []
        
    return valid_paths

def load_metadata() -> dict:
    """Loads the user-defined template metadata (tags).

    Returns:
        dict: A dictionary mapping template filenames to lists of custom tags.
    """
    if os.path.exists(METADATA_PATH):
        try:
            with open(METADATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading metadata: {e}")
    return {}

def save_metadata(filename: str, tags: list[str]):
    """Saves custom tag assignments back to the metadata JSON file.

    Args:
        filename (str): The name of the template file (e.g., 'comp_v01.nk').
        tags (list[str]): The updated list of tags assigned to this template.
    """
    data = load_metadata()
    data[filename] = tags
    try:
        with open(METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving metadata: {e}")

def get_tags() -> list[str]:
    """Retrieves the globally configured list of available tags.

    Returns:
        list[str]: A list of predefined tag strings from the config file.
    """
    config = load_config_data()
    return config.get("tags", [])

def use_folder_categories() -> bool:
    """Checks if the UI should organize templates by their parent folders.

    Returns:
        bool: True if folder categorization is enabled, False otherwise.
    """
    return load_config_data().get("use_folder_categories", True)