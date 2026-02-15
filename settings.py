import os
import json

CONFIG_PATH = os.path.expanduser("~/.nuke/templatemanager.json")

def  get_config_path():
    folder = os.path.dirname(CONFIG_PATH)
    os.makedirs(folder, exist_ok=True)
    return CONFIG_PATH

def load_user_template_path():
    if os.path.exists(get_config_path()):
        try:
            with open (get_config_path()) as f:
                content = f.read()
                data = json.loads(content)
                template_path = data ["template_path"]
                if isinstance(template_path, str):
                    return template_path
                else:
                    return None
        except Exception:
            return None
    else: 
      return None

def get_effective_template_path():
    user_path = load_user_template_path()
    if user_path is None:
        return os.path.expanduser("~/.nuke/templates")
    else:
        if os.path.isdir(user_path):
            return user_path
        else:
            return os.path.expanduser("~/.nuke/templates")
