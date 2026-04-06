import os
import nuke
from . import settings
try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
from .scanner import paste_template

class TemplateManagerUI(QtWidgets.QDialog):
    def __init__(self, templates, has_stamps,):
        super().__init__()
        self.alltemplates = templates
        self.has_stamps = has_stamps
        self.setWindowTitle("Template Manager")
        self.resize(1000, 1000)
        self.layout = QtWidgets.QGridLayout(self)
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Search templates...")
        self.search_bar.textChanged.connect(self.filter_templates)
        self.layout.addWidget(self.search_bar, 0, 0, 1, 2)
        unique_tags = {tag for t in self.alltemplates for tag in t.get("tags", [])}
        autocomplete_list = sorted([f"@{tag}" for tag in unique_tags])
        completer = QtWidgets.QCompleter(autocomplete_list)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.search_bar.setCompleter(completer)
        self.tabs = QtWidgets.QTabWidget()
        self.category_lists = {}
        self.build_tabs()
        self.layout.addWidget(self.tabs, 1, 0, 1, 2)
        self.close_btn = QtWidgets.QPushButton("Close Manager")
        self.close_btn.clicked.connect(self.close)
        import_btn = QtWidgets.QPushButton("Import Selected")
        import_btn.clicked.connect(self.import_from_button)
        self.layout.addWidget(self.close_btn, 2, 0, 1, 1)
        self.layout.addWidget(import_btn, 2, 1, 1, 1)
        self.populate_lists(self.alltemplates)
    def get_category(self, path):
        folder_name = os.path.basename(os.path.dirname(path))
        return folder_name.replace("_", " ").title()

    def build_tabs(self):
        categories = set(self.get_category(t["path"]) for t in self.alltemplates)
        for cat in sorted(categories):
            tree_widget = QtWidgets.QTreeWidget()
            tree_widget.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            tree_widget.itemChanged.connect(self.save_inline_tags)
            tree_widget.setHeaderLabels(["Template Name", "Status", "Tags"])
            tree_widget.setColumnCount(3)
            tree_widget.setColumnWidth(0, 300)
            tree_widget.setColumnWidth(1, 150)
            tree_widget.itemDoubleClicked.connect(self.import_template)
            self.tabs.addTab(tree_widget, cat)
            self.category_lists[cat] = tree_widget

    def populate_lists(self, list_of_templates):
        for list_widget in self.category_lists.values():
            list_widget.blockSignals(True)
            list_widget.clear()
            
        for t in list_of_templates:
            cat = self.get_category(t["path"])
            item = QtWidgets.QTreeWidgetItem()
            item.setText(0, t['name'])
            if t["status"] == "OK":
                item.setText(1, "[OK]")
            elif t["status"] == "MISSING_NODES":
                missing_str = ", ".join(t["missing_nodes"])
                item.setText(1, f"[MISSING]")
                item.setToolTip(1, f"Missing Plugins:\n{missing_str}")
            else:
                item.setText(1, "[ERROR]")
            tags_str = ", ".join(t.get("tags", []))
            if t.get("tags"):
                first_tag = t["tags"][0]
                color = self.get_tag_color(first_tag)
                item.setForeground(2, QtGui.QBrush(color))
            item.setText(2, tags_str)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
            if t.get("is_stamps"):
                item.setForeground(0, QtGui.QBrush(QtGui.QColor(0, 170, 255)))
                item.setToolTip(0, "This template uses Stamps.")
            else:
                item.setToolTip(0, t["path"])
            item.setData(0, QtCore.Qt.UserRole, t)
            self.category_lists[cat].addTopLevelItem(item)
        for tree in self.category_lists.values():
            tree.blockSignals(False)

    def filter_templates(self): 
        search_term = self.search_bar.text().lower().split()
        names_queries = []
        tag_queries = []
        for t in search_term:
            if t.startswith("@"):
                tag_queries.append(t[1:])
            else:
                names_queries.append(t)
        filtered = []
        for tpl in self.alltemplates:
            name_match = all(q in tpl["name"].lower() for q in names_queries)
            tags = [tag.lower() for tag in tpl.get("tags", [])]
            tag_match = all(q in tags for q in tag_queries)
            if name_match and tag_match:
                filtered.append(tpl)
        self.populate_lists(filtered)

    def import_template(self, item, column):
        tpl = item.data(0, QtCore.Qt.UserRole)
        if column == 0:
            if tpl["status"] == "OK":
                paste_template(tpl)
                self.close()
                
            elif tpl["status"] == "MISSING_NODES":
                missing = "\n".join(tpl["missing_nodes"])
                warning = f"Warning: This template is missing the following plugins:\n\n{missing}\n\nDo you want to force import it anyway?"
                
                if nuke.ask(warning):
                    nuke.nodePaste(tpl["path"])
                    self.close()
        elif column == 2:
            item.treeWidget().editItem(item, column)

    def save_inline_tags(self, item, column):
        if column == 2: 
            tpl = item.data(0, QtCore.Qt.UserRole)
            new_tags_str = item.text(2)
            new_tags = [t.strip() for t in new_tags_str.split(",") if t.strip()]
            tpl["tags"] = new_tags
            item.setData(0, QtCore.Qt.UserRole, tpl)
            filename = os.path.basename(tpl["path"])
            settings.save_metadata(filename, new_tags)
    def import_from_button(self):
        current_tab = self.tabs.currentWidget()
        selected_items = current_tab.selectedItems()
        if not selected_items:
            nuke.message("Please select a template to import.")
            return
        item = selected_items[0]
        self.import_template(item, 0)
    def get_tag_color (self, tag_string):
        hue = sum(ord(char) for char in tag_string) * 45 % 360
        return QtGui.QColor.fromHsv(hue, 150, 255)
        