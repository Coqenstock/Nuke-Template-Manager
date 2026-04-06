import nuke
from . import settings
from .scanner import scan_templates, get_available_nodes
from .ui import TemplateManagerUI

def launch_ui():
    paths: list[str] = settings.get_effective_template_paths()
    nodes: set[str] = get_available_nodes()
    tags: list[str] = settings.get_tags()
    has_stamps = False
    try:
        import stamps
        has_stamps = True
    except ImportError:
        pass

    all_templates = []
    for path in paths:
        all_templates.extend(scan_templates(path, nodes))
        
    global tm_window 
    tm_window = TemplateManagerUI(all_templates, tags, has_stamps)
    tm_window.show()