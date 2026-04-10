"""Entry point for the Nuke Template Manager.

This module handles the initialization of the tool, aggregating the 
configuration paths, running the initial template scan, and launching 
the PySide frontend within Nuke.
"""
import nuke
from . import settings
from .scanner import scan_templates, get_available_nodes
from .ui import TemplateManagerUI

def launch_ui():
    """Initializes the environment and launches the Template Manager UI.

    This function retrieves the configured search paths, scans the active Nuke 
    environment for available nodes (including proprietary tools like Stamps), 
    parses the template files, and instantiates the main PySide dialog. 

    Note:
        A global reference to the window (`tm_window`) is maintained to prevent 
        Nuke's Python garbage collector from destroying the UI immediately after launch.
    """
    paths: list[str] = settings.get_effective_template_paths()
    nodes: set[str] = get_available_nodes()
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
    tm_window = TemplateManagerUI(all_templates, has_stamps)
    tm_window.show()