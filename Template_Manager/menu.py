import nuke
from .main import launch_ui

def setup_menu():
    nuke.menu("Nuke").addMenu("Template Manager").addCommand("Start Template Manager", launch_ui, "ctrl+t")

setup_menu()
