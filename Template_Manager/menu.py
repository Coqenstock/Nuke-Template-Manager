import nuke
from .main import launch_ui

def setup_menu():
    nuke.menu("Nuke").addMenu("Pipeline Tools").addCommand("Template Manager", launch_ui, "ctrl+t")

setup_menu()
