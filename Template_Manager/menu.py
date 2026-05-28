import nuke
 
try:
    import Template_Manager.main
    tm_menu = nuke.menu("Nuke").addMenu("Template Manager")
    tm_menu.addCommand("Browser", "Template_Manager.main.launch_ui()", "Ctrl+T")
    tm_menu.addCommand("Save Template", "Template_Manager.main.launch_save_ui()", "Ctrl+Shift+T")
    tm_menu.addSeparator()
    tm_menu.addCommand("Edit Tagging Rules", "Template_Manager.main.launch_rules_editor()")
    tm_menu.addCommand("About", "Template_Manager.main.launch_about_dialog()")
 
except Exception as e:
    print("Template Manager failed to load:", e)