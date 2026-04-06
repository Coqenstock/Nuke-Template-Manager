import os
import json

STUDIO_ENV_VAR = "STUDIO_TEMPLATE_CONFIG"
LOCAL_CONFIG_PATH = os.path.expanduser("~/.nuke/Template_Manager/templatemanager.json")
DEFAULT_TEMPLATE_PATH = os.path.expanduser("~/.nuke/templates")
METADATA_PATH = os.path.expanduser("~/.nuke/Template_Manager/template_metadata.json")

def get_config_path() -> str:
    studio_path = os.getenv(STUDIO_ENV_VAR)
    if studio_path and os.path.exists(studio_path):
        return studio_path
    os.makedirs(os.path.dirname(LOCAL_CONFIG_PATH), exist_ok=True)
    return LOCAL_CONFIG_PATH

def load_config_data() -> dict:
    config_path = get_config_path()
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            # FIX: Added a print statement so this block is no longer empty!
            print(f"Error reading config: {e}")
            
    # FIX: A clean catch-all return if the file doesn't exist or crashes
    return {}

def get_effective_template_paths() -> list[str]:
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
    # FIX: Indented this entire block by 4 spaces!
    if os.path.exists(METADATA_PATH):
        try:
            with open(METADATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading metadata: {e}")
    return {}

def save_metadata(filename: str, tags: list[str]):
    data = load_metadata()
    data[filename] = tags
    try:
        with open(METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving metadata: {e}")

def get_tags() -> list[str]:
    config = load_config_data()
    return config.get("tags", [])

def use_folder_categories() -> bool:
    return load_config_data().get("use_folder_categories", True)