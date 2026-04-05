import os
import nuke
try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

from .scanner import paste_template

class TemplateManagerUI(QtWidgets.QDialog):
    def __init__(self, templates):
        super().__init__()
        self.alltemplates = templates
        self.setWindowTitle("Template Manager")
        self.resize(1000, 1000)
        self.layout = QtWidgets.QGridLayout(self)
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Search templates...")
        self.layout.addWidget(self.search_bar, 0, 0)
        self.tabs = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tabs, 1, 0)
        self.category_lists = {}
        self.build_tabs()
        self.close_btn = QtWidgets.QPushButton("Close Manager")
        self.close_btn.clicked.connect(self.close)
        self.layout.addWidget(self.close_btn, 2, 0)
        self.search_bar.textChanged.connect(self.filter_templates)
        self.populate_lists(self.alltemplates)
    def get_category(self, path):
        folder_name = os.path.basename(os.path.dirname(path))
        return folder_name.replace("_", " ").title()

    def build_tabs(self):
        categories = set(self.get_category(t["path"]) for t in self.alltemplates)
        for cat in sorted(categories):
            list_widget = QtWidgets.QListWidget()
            list_widget.itemDoubleClicked.connect(self.import_template)
            self.tabs.addTab(list_widget, cat)
            self.category_lists[cat] = list_widget

    def populate_lists(self, list_of_templates):
        for list_widget in self.category_lists.values():
            list_widget.clear()
        for t in list_of_templates:
            cat = self.get_category(t["path"])
            
            if t["status"] == "OK":
                label_text = f"{t['name']}  [OK]"
            elif t["status"] == "MISSING_NODES":
                missing_str = ", ".join(t["missing_nodes"])
                label_text = f"{t['name']}  [MISSING: {missing_str}]"
            else:
                label_text = f"{t['name']}  [ERROR]"

            item = QtWidgets.QListWidgetItem(label_text)
            item.setData(QtCore.Qt.UserRole, t)
            self.category_lists[cat].addItem(item)

    def filter_templates(self): 
        search_term = self.search_bar.text().lower()
        filtered = [t for t in self.alltemplates if search_term in t["name"].lower()]
        self.populate_lists(filtered)

    def import_template(self, item):
        tpl = item.data(QtCore.Qt.UserRole)
        
        if tpl["status"] == "OK":
            paste_template(tpl)
            self.close()
            
        elif tpl["status"] == "MISSING_NODES":
            missing = "\n".join(tpl["missing_nodes"])
            warning = f"Warning: This template is missing the following plugins:\n\n{missing}\n\nDo you want to force import it anyway?"
            
            if nuke.ask(warning):
                nuke.nodePaste(tpl["path"])
                self.close()