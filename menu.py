import nuke
import main 

m = nuke.menu("Nuke")
tm = m.addMenu("Templates")
tm.addCommand("Paste first OK template", "main.paste_first_ok()")