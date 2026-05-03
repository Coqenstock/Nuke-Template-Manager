"""PySide graphical user interface for the Nuke Template Manager.

This module builds the interactive Qt dialog used by artists to browse, 
search, tag, and import Nuke scripts. It handles dynamic UI generation, 
memory synchronization between disk and RAM, and dependency interception.
"""

import os
import nuke
from . import settings
try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
from .scanner import paste_template

class TemplateManagerUI(QtWidgets.QDialog):
    """The main user interface dialog for the Template Manager.

    This class builds a tabbed UI organized by directory, featuring predictive 
    search filtering, inline editable tagging, and a procedural color-hashing system.

    Args:
        templates (list[dict]): The master list of scanned template dictionaries.
        has_stamps (bool): True if the local environment successfully loaded the Stamps plugin.
    """
    def __init__(self, templates, has_stamps,):
        super().__init__()
        self.alltemplates = templates
        self.has_stamps = has_stamps
        self.setWindowTitle("Template Manager")
        self.resize(1000, 1000)
        self.layout = QtWidgets.QGridLayout(self)
        
        # Search Bar Setup
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Search templates...")
        self.search_bar.textChanged.connect(self.filter_templates)
        self.layout.addWidget(self.search_bar, 0, 0, 1, 2)
        
        # Autocomplete Setup
        unique_tags = {tag for t in self.alltemplates for tag in t.get("tags", [])}
        autocomplete_list = sorted([f"@{tag}" for tag in unique_tags])
        self.completer = QtWidgets.QCompleter(autocomplete_list)
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.search_bar.setCompleter(self.completer)
        
        # UI Layout Setup
        self.tabs = QtWidgets.QTabWidget()
        self.category_lists = {}
        self.build_tabs()
        self.layout.addWidget(self.tabs, 1, 0, 1, 2)
        
        # Buttons
        self.close_btn = QtWidgets.QPushButton("Close Manager")
        self.close_btn.clicked.connect(self.close)
        import_btn = QtWidgets.QPushButton("Import Selected")
        import_btn.clicked.connect(self.import_from_button)
        self.layout.addWidget(self.close_btn, 2, 0, 1, 1)
        self.layout.addWidget(import_btn, 2, 1, 1, 1)
        
        # Initial Population
        self.populate_lists(self.alltemplates)

    def get_category(self, path):
        """Extracts a human-readable category name from a file path.

        Args:
            path (str): The absolute file path to the template.

        Returns:
            str: The title-cased name of the parent folder.
        """
        folder_name = os.path.basename(os.path.dirname(path))
        return folder_name.replace("_", " ").title()

    def build_tabs(self):
        """Dynamically generates QTreeWidgets grouped by folder categories."""
        categories = set(self.get_category(t["path"]) for t in self.alltemplates)
        for cat in sorted(categories):
            tree_widget = QtWidgets.QTreeWidget()
            tree_widget.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            tree_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
            tree_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu) 
            tree_widget.customContextMenuRequested.connect(self.open_context_menu) 
            tree_widget.itemChanged.connect(self.save_inline_tags)
            tree_widget.setHeaderLabels(["Template Name", "Status", "Tags"])
            tree_widget.setColumnCount(3)
            tree_widget.setColumnWidth(0, 300)
            tree_widget.setColumnWidth(1, 150)
            tree_widget.itemDoubleClicked.connect(self.import_template)
            self.tabs.addTab(tree_widget, cat)
            self.category_lists[cat] = tree_widget

    def populate_lists(self, list_of_templates):
        """Populates the QTreeWidgets with items from a given template list.

        This method applies custom visual styling based on template status, 
        including missing node warnings, procedural tag colors, and blue 
        text formatting for templates utilizing proprietary tools (e.g., Stamps).

        Args:
            list_of_templates (list[dict]): The templates to display.
        """
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
        """Filters the displayed templates based on the search bar input.
        
        This method parses the search string for standard text queries 
        as well as '@' prefix tags, updating the UI to show only matches.
        """
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
        """Handles the double-click event to import a template into Nuke.

        If the template has nodes missing from the current Nuke environment, this intercepts the standard 
        Nuke paste operation and displays a forced-acknowledgment warning 
        dialog to prevent silent pipeline errors.

        Args:
            item (QtWidgets.QTreeWidgetItem): The UI item that was clicked.
            column (int): The index of the clicked column.
        """
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
        """Updates metadata and syncs memory state after inline editing.

        This method solves a UI desynchronization issue by updating the modified 
        tags in three distinct places simultaneously: the physical JSON file, 
        the master Python memory list (`self.alltemplates`), and the Qt Item data.

        Args:
            item (QtWidgets.QTreeWidgetItem): The UI item being edited.
            column (int): The index of the edited column.
        """
        if column == 2: 
            tpl = item.data(0, QtCore.Qt.UserRole)
            new_tags_str = item.text(2)
            new_tags = [t.strip() for t in new_tags_str.split(",") if t.strip()]
            for master_tpl in self.alltemplates:
                if master_tpl["path"] == tpl["path"]:
                    master_tpl["tags"] = new_tags
                    break
            tpl["tags"] = new_tags
            item.setData(0, QtCore.Qt.UserRole, tpl)
            filename = os.path.basename(tpl["path"])
            settings.save_metadata(filename, new_tags)
            if new_tags:
                first_tag = new_tags[0]
                color = self.get_tag_color(first_tag) 
                item.setForeground(2, QtGui.QBrush(color))
            else:
                item.setForeground(2, QtGui.QBrush(QtGui.QColor(200, 200, 200)))
            self.update_autocomplete()
    def import_from_button(self):
        """Wrapper method that triggers the import logic from the UI button."""
        current_tab = self.tabs.currentWidget()
        selected_items = current_tab.selectedItems()
        if not selected_items:
            nuke.message("Please select a template to import.")
            return
        item = selected_items[0]
        self.import_template(item, 0)
    def get_tag_color (self, tag_string):
        """Generates a procedural QColor based on the string's characters.

        This function uses a positional-weighting algorithm to prevent 
        hash collisions between tags with the same ASCII sum.

        Args:
            tag_string (str): The raw tag text to be converted (e.g., "@cg").

        Returns:
            QtGui.QColor: A procedural color mapped to the 360 HSV wheel.
        """
        tag_string = tag_string.strip().lower()
        hue = sum(ord(char) * (i + 1) for i, char in enumerate(tag_string))
        hue = (hue * 45) % 360
        return QtGui.QColor.fromHsv(hue, 150, 255)
    def update_autocomplete(self):
        """Refreshes the QCompleter model to include newly added tags."""
        unique_tags = {tag for t in self.alltemplates for tag in t.get("tags", [])}
        autocomplete_list = sorted([f"@{tag}" for tag in unique_tags])
        model = QtCore.QStringListModel()
        model.setStringList(autocomplete_list)
        self.completer.setModel(model)
    def open_context_menu(self, position):
        """Spawns a right-click context menu for batch-tagging multiple templates.

        Args:
            position (QtCore.QPoint): The local cursor coordinates for the menu.
        """
        current_tab = self.tabs.currentWidget()
        selected_items = current_tab.selectedItems()
        if not selected_items:
            return
        menu = QtWidgets.QMenu()
        batch_tag_action = menu.addAction(f"Batch Tag ({len(selected_items)} selected)")
        action = menu.exec_(current_tab.viewport().mapToGlobal(position))
        if action == batch_tag_action:
            new_tags_str = nuke.getInput("Enter tags separated by commas):", "")
            if new_tags_str is None:
                return
            new_tags = [t.strip() for t in new_tags_str.split(",") if t.strip()]
            for item in selected_items:
                tpl = item.data(0, QtCore.Qt.UserRole)
                for master_tpl in self.alltemplates:
                    if master_tpl["path"] == tpl["path"]:
                        master_tpl["tags"] = new_tags
                        break
                tpl["tags"] = new_tags
                item.setData(0, QtCore.Qt.UserRole, tpl)
                filename = os.path.basename(tpl["path"])
                settings.save_metadata(filename, new_tags)
                item.setText(2, ", ".join(new_tags))
                if new_tags:
                    color = self.get_tag_color(new_tags[0])
                    item.setForeground(2, QtGui.QBrush(color))
                else:
                    item.setForeground(2, QtGui.QBrush(QtGui.QColor(200, 200, 200)))
            self.update_autocomplete()
        