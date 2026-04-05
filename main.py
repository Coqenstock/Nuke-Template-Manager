import nuke
from . import settings
from .scanner import scan_templates, get_available_nodes
from .ui import TemplateManagerUI

def launch_ui():
    paths = settings.get_effective_template_paths()
    nodes = get_available_nodes()
    
    all_templates = []
    for path in paths:
        all_templates.extend(scan_templates(path, nodes))
        
    global tm_window 
    tm_window = TemplateManagerUI(all_templates)
    tm_window.show()