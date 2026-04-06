import os
import nuke
from . import settings
try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

from .scanner import paste_template

class TagEditorDialog(QtWidgets.QDialog):
    def __init__(self, available_tags, current_tags, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Tags")
        self.layout = QtWidgets.QVBoxLayout(self)
        self.checkboxes = []

        for tag in sorted(available_tags):
            cb = QtWidgets.QCheckBox(tag)
            if tag in current_tags:
                cb.setChecked(True)
            self.layout.addWidget(cb)
            self.checkboxes.append(cb)

        self.save_btn = QtWidgets.QPushButton("Save Tags")
        self.save_btn.clicked.connect(self.accept)
        self.layout.addWidget(self.save_btn)

    def get_selected_tags(self):
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]

class TemplateManagerUI(QtWidgets.QDialog):
    def __init__(self, templates, tags, has_stamps,):
        super().__init__()
        self.alltemplates = templates
        self.has_stamps = has_stamps
        self.available_tags = tags
        self.setWindowTitle("Template Manager")
        self.resize(1000, 1000)
        self.layout = QtWidgets.QGridLayout(self)
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Search templates...")
        self.search_bar.textChanged.connect(self.filter_templates)
        self.layout.addWidget(self.search_bar, 0, 0)
        self.tag_layout = QtWidgets.QHBoxLayout()
        self.tag_checkboxes = []
        for tag in sorted(tags):
            cb = QtWidgets.QCheckBox(tag)
            cb.toggled.connect(self.filter_templates)
            self.tag_layout.addWidget(cb)
            self.tag_checkboxes.append(cb)
        self.layout.addLayout(self.tag_layout, 0, 1)
        self.tabs = QtWidgets.QTabWidget()
        self.category_lists = {}
        self.build_tabs()
        self.layout.addWidget(self.tabs, 1, 0, 1, 2)
        self.close_btn = QtWidgets.QPushButton("Close Manager")
        self.close_btn.clicked.connect(self.close)
        self.layout.addWidget(self.close_btn, 2, 0, 1, 2)
        self.populate_lists(self.alltemplates)
    def get_selected_tags(self):
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]
    def get_category(self, path):
        folder_name = os.path.basename(os.path.dirname(path))
        return folder_name.replace("_", " ").title()

    def build_tabs(self):
        categories = set(self.get_category(t["path"]) for t in self.alltemplates)
        for cat in sorted(categories):
            list_widget = QtWidgets.QListWidget()
            list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            list_widget.customContextMenuRequested.connect(self.show_context_menu)
            list_widget.itemDoubleClicked.connect(self.import_template)
            self.tabs.addTab(list_widget, cat)
            self.category_lists[cat] = list_widget

    def populate_lists(self, list_of_templates):
        for list_widget in self.category_lists.values():
            list_widget.clear()
            
        for t in list_of_templates:
            cat = self.get_category(t["path"])
            if t.get("is_stamps") and not self.has_stamps:
                continue
            prefix = "🏷️ " if t.get("is_stamps") else ""
            if t["status"] == "OK":
                label_text = f"{prefix}{t['name']}  [OK]"
            elif t["status"] == "MISSING_NODES":
                missing_str = ", ".join(t["missing_nodes"])
                label_text = f"{prefix}{t['name']}  [MISSING: {missing_str}]"
            else:
                label_text = f"{prefix}{t['name']}  [ERROR]"
            item = QtWidgets.QListWidgetItem(label_text)
            item.setData(QtCore.Qt.UserRole, t)
            self.category_lists[cat].addItem(item)

    def filter_templates(self): 
        search_term = self.search_bar.text().lower()
        active_tags = [cb.text() for cb in self.tag_checkboxes if cb.isChecked()]
        filtered = [t for t in self.alltemplates if search_term in t["name"].lower()]
        if active_tags:
            filtered = [
                t for t in filtered 
                if all(tag in t.get("tags", []) for tag in active_tags)
            ]
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
    def show_context_menu(self, position):
        list_widget = self.sender()
        item = list_widget.itemAt(position)
        
        if not item:
            return 
        menu = QtWidgets.QMenu()
        edit_action = menu.addAction("Edit Tags...")
        action = menu.exec_(list_widget.mapToGlobal(position))
        
        if action == edit_action:
            tpl = item.data(QtCore.Qt.UserRole)
            self.open_tag_editor(tpl)

    def open_tag_editor(self, tpl):
        dialog = TagEditorDialog(self.available_tags, tpl.get("tags", []), self)
        if dialog.exec_():
            new_tags = dialog.get_selected_tags()
            tpl["tags"] = new_tags
            filename = os.path.basename(tpl["path"])
            settings.save_metadata(filename, new_tags)
            self.filter_templates()