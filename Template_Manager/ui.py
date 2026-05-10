"""PySide graphical user interface for the Nuke Template Manager.

This module builds every Qt dialog the plugin exposes to artists. It is
designed to work transparently against both PySide6 (newer Nuke
releases) and PySide2 (older releases) by attempting the PySide6 import
first and falling back if it is unavailable.

The module owns six widget classes:

* :class:`TemplateManagerUI` — the main browser window: a searchable,
  taggable, hierarchical view of every scanned template.
* :class:`SaveTemplateDialog` — the form used to choose a project,
  subfolder, name, and versioning behaviour for a new template save.
* :class:`BatchTagDialog` — the small dialog driving the right-click
  Batch Tag action on multiple selected templates.
* :class:`PlaceholderDialog` — the checklist that lets artists decide
  which Read nodes to swap with Placeholder NoOps during save or
  import.
* :class:`AutoTagRulesDialog` — the form-based editor for the
  auto-tagging rule set persisted by :mod:`saves`.
* :class:`RuleWidget` — a single editable row inside the rules dialog.

The free function :func:`get_nuke_main_window` provides the parent
widget every dialog uses so the windows float above Nuke rather than
the desktop.
"""

import os
import io
import re
from typing import TYPE_CHECKING
import nuke
from . import settings
from . import saves
if TYPE_CHECKING:
    from PySide6 import QtWidgets, QtCore, QtGui
else:
    try:
        from PySide6 import QtWidgets, QtCore, QtGui
    except ImportError:
        from PySide2 import QtWidgets, QtCore, QtGui
from .scanner import paste_template


def get_nuke_main_window():
    """Locate Nuke's main dock window so dialogs can parent themselves to it.

    Walks every top-level widget known to the running Qt application
    and returns the first one whose class name matches Nuke's internal
    dock-main-window class. Parenting plugin dialogs to this widget
    ensures they float on top of the host application and respect
    Nuke's window-stacking rules rather than the desktop's.

    Returns:
        QtWidgets.QMainWindow | None: The detected main window
        instance, or ``None`` if no widget matches (for example when
        running outside Nuke). Callers should tolerate the ``None``
        case by parenting their dialogs to ``None``, which produces a
        free-floating top-level window.
    """
    for obj in QtWidgets.QApplication.topLevelWidgets():
        if obj.inherits('QMainWindow') and obj.metaObject().className() == 'Foundry::UI::DockMainWindow':
            return obj
    return None


class SaveTemplateDialog(QtWidgets.QDialog):
    """A dialog for saving new templates from Nuke's node graph.

    The dialog gathers four pieces of information from the user:

    * The template's base name (used as the filename stem).
    * A project, either chosen from the dropdown of existing projects
      or created on the fly via the "[ + Create New Project ]" option.
    * An optional subfolder path within the project, selectable from a
      mini-tree of known subfolders or typed directly.
    * Whether to auto-version the saved file with a ``_v##`` suffix.

    Args:
        projects_dict (dict): Mapping of project display names to sets
            of known subfolder paths. Used to populate both the
            project dropdown and the per-project subfolder tree.
        project_raw_map (dict): Mapping of project display names to
            their raw on-disk folder names. The display name is the
            title-cased, space-separated form shown to the user; the
            raw name is the snake-cased folder name used on disk.
        detected_project (str | None): Project name to pre-select in
            the dropdown, typically derived from the active Nuke
            script's filename by :func:`main.launch_save_ui`. Pass
            ``None`` to leave the dropdown on its first entry.
        default_root (str): Filesystem path used as the base directory
            under which the new template will be written.
        parent (QWidget, optional): Parent widget for the dialog.
            Defaults to ``None``, producing a free-floating top-level
            window.
    """

    def __init__(self, projects_dict, project_raw_map, detected_project, default_root, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save Template")
        self.resize(500, 350)
        self.default_root = default_root
        self.projects_dict = projects_dict
        self.project_raw_map = project_raw_map

        layout = QtWidgets.QFormLayout(self)

        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("e.g. keying_core")
        layout.addRow("Template Name:", self.name_input)

        self.project_dropdown = QtWidgets.QComboBox()
        self.project_dropdown.addItem("My Templates (Root)")
        for proj in sorted(projects_dict.keys()):
            self.project_dropdown.addItem(proj)
        self.project_dropdown.addItem("[ + Create New Project ]")
        self.project_dropdown.currentIndexChanged.connect(self.on_project_changed)
        layout.addRow("Project:", self.project_dropdown)

        self.new_project_input = QtWidgets.QLineEdit()
        self.new_project_input.setPlaceholderText("e.g. Project XYZ")
        self.new_project_input.hide()
        layout.addRow("", self.new_project_input)

        tree_layout = QtWidgets.QVBoxLayout()
        self.subfolder_tree = QtWidgets.QTreeWidget()
        self.subfolder_tree.setHeaderHidden(True)
        self.subfolder_tree.setMaximumHeight(120)
        self.subfolder_tree.itemClicked.connect(self.on_tree_item_clicked)
        tree_layout.addWidget(self.subfolder_tree)

        self.subfolder_input = QtWidgets.QLineEdit()
        self.subfolder_input.setPlaceholderText("Select from tree, or type a new path (e.g. Sq01/Sh010)")
        tree_layout.addWidget(self.subfolder_input)
        layout.addRow("Subfolder:", tree_layout)

        self.auto_version_cb = QtWidgets.QCheckBox("Auto-Version (Append _v01)")
        self.auto_version_cb.setChecked(True)
        layout.addRow("", self.auto_version_cb)

        btn_layout = QtWidgets.QHBoxLayout()
        save_btn = QtWidgets.QPushButton("Save Template")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

        if detected_project:
            index = self.project_dropdown.findText(detected_project)
            if index >= 0:
                self.project_dropdown.setCurrentIndex(index)
                try:
                    script_path = nuke.scriptName().replace("\\", "/").lower()
                    best_sub = ""
                    for sub in projects_dict.get(detected_project, set()):
                        if sub.lower() in script_path:
                            if len(sub) > len(best_sub):
                                best_sub = sub
                    if best_sub:
                        self.subfolder_input.setText(best_sub)
                except Exception:
                    pass
        self.update_subfolder_tree()

    def on_project_changed(self):
        """Handle a change in the Project dropdown selection.

        Shows the new-project text input only when the user selects
        the synthetic ``[ + Create New Project ]`` entry, hiding it in
        every other case so the form stays compact. Triggers a rebuild
        of the subfolder tree to reflect the newly selected project's
        known subfolders.
        """
        if self.project_dropdown.currentText() == "[ + Create New Project ]":
            self.new_project_input.show()
        else:
            self.new_project_input.hide()
        self.update_subfolder_tree()

    def update_subfolder_tree(self):
        """Rebuild the subfolder mini-tree from the current project's data.

        Looks up the currently selected project in
        :attr:`projects_dict` and populates the tree widget with every
        known subfolder path beneath that project, splitting on
        forward slashes to build the hierarchical structure. When the
        special ``"My Templates (Root)"`` entry is selected the tree
        is disabled entirely because root-level templates have no
        subfolder. The tree is fully expanded after population so
        artists can see every known path at a glance.
        """
        self.subfolder_tree.clear()
        current_proj = self.project_dropdown.currentText()
        if current_proj == "My Templates (Root)":
            self.subfolder_tree.setDisabled(True)
            self.subfolder_input.setDisabled(True)
            self.subfolder_input.clear()
            return

        self.subfolder_tree.setDisabled(False)
        self.subfolder_input.setDisabled(False)
        subfolders = sorted(list(self.projects_dict.get(current_proj, set())))
        folder_nodes = {}
        for path in subfolders:
            if not path:
                continue
            parts = path.split("/")
            current_parent = self.subfolder_tree
            current_path = []
            for part in parts:
                current_path.append(part)
                path_key = tuple(current_path)
                if path_key not in folder_nodes:
                    item = QtWidgets.QTreeWidgetItem(current_parent)
                    item.setText(0, part)
                    item.setData(0, QtCore.Qt.UserRole, "/".join(current_path))
                    folder_nodes[path_key] = item
                current_parent = folder_nodes[path_key]
        self.subfolder_tree.expandAll()

    def on_tree_item_clicked(self, item, column):
        """Copy a clicked tree path into the subfolder text input.

        Reads the full subfolder path stored on the clicked tree node
        (as ``UserRole`` data) and writes it into the text input so
        the user can edit it further or accept it as-is.

        Args:
            item (QtWidgets.QTreeWidgetItem): The tree node the user
                clicked.
            column (int): The column index of the click. Unused; the
                path is stored on column 0 regardless.
        """
        folder_path = item.data(0, QtCore.Qt.UserRole)
        if folder_path:
            self.subfolder_input.setText(folder_path)

    def get_save_data(self):
        """Return the validated save parameters chosen by the user.

        Reads every input field, trims whitespace, replaces spaces
        with underscores in path-bound strings, normalises slashes
        for cross-platform safety, and assembles the absolute target
        directory. The returned ``base_name`` is the template's
        filename stem with no extension and no version suffix; the
        Save Template flow combines it with the path and the version
        suffix downstream via :func:`saves.get_save_path`.

        Returns:
            tuple: A 3-tuple ``(base_name, final_folder_path,
            do_version)``.

            * ``base_name`` (str) — the sanitised template filename
              stem.
            * ``final_folder_path`` (str) — the absolute directory the
              template should be written into, including the project
              and subfolder components.
            * ``do_version`` (bool) — ``True`` if auto-versioning is
              enabled, ``False`` if the user disabled it.
        """
        base_name = self.name_input.text().strip().replace(" ", "_")
        loc_text = self.project_dropdown.currentText()
        if loc_text == "My Templates (Root)":
            project_path = ""
        elif loc_text == "[ + Create New Project ]":
            project_path = self.new_project_input.text().strip().replace(" ", "_")
        else:
            project_path = self.project_raw_map.get(loc_text, loc_text.replace(" ", "_"))

        subfolder = self.subfolder_input.text().strip().replace("\\", "/")
        final_folder_path = os.path.join(self.default_root, project_path, subfolder).replace("\\", "/")
        do_version = self.auto_version_cb.isChecked()
        return base_name, final_folder_path, do_version


class TemplateManagerUI(QtWidgets.QDialog):
    """The main browser window for the Template Manager plugin.

    The window presents every scanned template as a row in a
    multi-column tree view, organised by project (via the dropdown)
    and by subfolder (as expandable tree nodes). Core features
    exposed through the UI include:

    * A live search bar supporting plain text matches against
      template names and ``@tag`` queries against tag metadata, with
      autocomplete suggestions drawn from the union of every tag in
      the library.
    * A Project Settings column summarising each template's frame
      rate, resolution, and colour management, with a one-click
      prompt to update the current Nuke script's project settings to
      match the template at import time.
    * Inline tag editing in the Tags column, plus right-click batch
      tagging and a Re-Evaluate Auto-Tags action that re-runs the
      rule engine against the current template contents.
    * Procedural per-tag colouring derived from the tag string,
      keeping similar tags visually consistent across sessions.
    * Smart auto-detection of the active Nuke script's project, with
      matching template rows pre-expanded and scrolled into view on
      launch.

    Args:
        templates (list[dict]): The master list of scanned template
            dictionaries produced by :func:`scanner.scan_templates`.
        has_stamps (bool): ``True`` if the Stamps plugin was found in
            the current Python environment. Reserved for future
            Stamps-aware UI behaviour; carried through from the
            scanner pass.
    """

    def __init__(self, templates, has_stamps):
        super().__init__()
        self.alltemplates = templates
        self.has_stamps = has_stamps
        self.base_template_paths = settings.get_effective_template_paths()
        self.setWindowTitle("Template Manager")
        self.resize(1100, 1000)
        self.layout = QtWidgets.QGridLayout(self)

        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Search templates...")
        self.search_bar.textChanged.connect(self.filter_current_project)

        unique_tags = {tag for t in self.alltemplates for tag in t.get("tags", [])}
        autocomplete_list = sorted(["@" + tag for tag in unique_tags])
        self.completer = QtWidgets.QCompleter(autocomplete_list)
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.search_bar.setCompleter(self.completer)
        self.layout.addWidget(self.search_bar, 0, 0, 1, 2)

        self.project_dropdown = QtWidgets.QComboBox()
        self.project_dropdown.currentIndexChanged.connect(self.refresh_tree)
        self.layout.addWidget(self.project_dropdown, 1, 0, 1, 2)

        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tree_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.tree_widget.setHeaderLabels(["Template Name", "Project Settings", "Status", "External Gizmos", "Tags"])
        self.tree_widget.setColumnCount(5)
        self.tree_widget.setColumnWidth(0, 300)
        self.tree_widget.setColumnWidth(1, 200)
        self.tree_widget.setColumnWidth(2, 200)
        self.tree_widget.setColumnWidth(3, 150)
        self.tree_widget.setColumnWidth(4, 200)

        self.tree_widget.itemDoubleClicked.connect(self.import_template)
        self.tree_widget.itemChanged.connect(self.save_inline_tags)
        self.tree_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.open_context_menu)
        self.layout.addWidget(self.tree_widget, 2, 0, 1, 2)

        self.tree_widget.setSortingEnabled(False)
        self.current_sort_col = 0
        self.current_sort_reverse = False
        self.tree_widget.header().setSectionsClickable(True)
        self.tree_widget.header().setSortIndicatorShown(True)
        self.tree_widget.header().setSortIndicator(0, QtCore.Qt.AscendingOrder)
        self.tree_widget.header().sectionClicked.connect(self.on_header_clicked)

        import_btn = QtWidgets.QPushButton("Import Selected")
        import_btn.clicked.connect(self.import_from_button)
        self.close_btn = QtWidgets.QPushButton("Close Manager")
        self.close_btn.clicked.connect(self.close)
        self.layout.addWidget(import_btn, 3, 0, 1, 1)
        self.layout.addWidget(self.close_btn, 3, 1, 1, 1)

        self.projects_dict = {}
        self.group_templates_by_project()

        self.project_dropdown.blockSignals(True)
        self.project_dropdown.addItems(sorted(self.projects_dict.keys()))
        self.auto_detect_project()
        self.project_dropdown.blockSignals(False)

        self.refresh_tree()

    def natural_sort_key(self, base_name, template_dict):
        """Generate a key for natural alphanumeric sorting (e.g., v2 comes before v20).

        Args:
            base_name (str): The display name of the template entry.
            template_dict (dict): The template metadata dictionary containing ``_hierarchy``.

        Returns:
            list: A mixed list of strings and ints suitable for use as a sort key.
        """
        hierarchy = template_dict.get("_hierarchy", [])
        full_path = "/".join(hierarchy) + "/" + base_name
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', full_path)]

    def on_header_clicked(self, logical_index):
        """Intercept header clicks to perform a safe Python sort instead of a destructive Qt sort.

        Args:
            logical_index (int): The column index that was clicked.
        """
        if self.current_sort_col == logical_index:
            self.current_sort_reverse = not self.current_sort_reverse
        else:
            self.current_sort_col = logical_index
            self.current_sort_reverse = False
        order = QtCore.Qt.DescendingOrder if self.current_sort_reverse else QtCore.Qt.AscendingOrder
        self.tree_widget.header().setSortIndicator(self.current_sort_col, order)
        self.refresh_tree()

    def parse_path_context(self, template_path):
        """Split a template path into Project Display name, Project Raw name, and Hierarchy.

        Args:
            template_path (str): The absolute filesystem path of the template file.

        Returns:
            tuple: A 3-tuple of ``(proj_display, proj_raw, hierarchy)`` where *hierarchy*
                is a list of sub-folder display names below the project root.
        """
        for root_path in self.base_template_paths:
            if template_path.startswith(root_path):
                rel_path = os.path.relpath(template_path, root_path)
                dir_path = os.path.dirname(rel_path)
                if not dir_path:
                    return "My Templates", "My Templates", []
                folders = dir_path.replace('\\', '/').split('/')
                proj_raw = folders[0]
                proj_display = proj_raw.replace("_", " ").title()
                if len(folders) > 1:
                    hierarchy = [f.replace("_", " ").title() for f in folders[1:]]
                else:
                    hierarchy = []
                return proj_display, proj_raw, hierarchy
        return "Uncategorized", "Uncategorized", []

    def group_templates_by_project(self):
        """Populate ``projects_dict`` by parsing every template's path context.

        Also stores ``_hierarchy`` back onto each template dict and builds
        ``project_raw_map`` for display-name-to-raw-folder lookups.
        """
        self.project_raw_map = {}
        for tpl in self.alltemplates:
            proj_display, proj_raw, hierarchy = self.parse_path_context(tpl["path"])
            self.project_raw_map[proj_display] = proj_raw
            tpl["_hierarchy"] = hierarchy
            if proj_display not in self.projects_dict:
                self.projects_dict[proj_display] = []
            self.projects_dict[proj_display].append(tpl)

    def auto_detect_project(self):
        """Attempt to guess the active project from the current Nuke script name.

        Uses three heuristics in descending priority:

        1. Exact template base-name match against the script filename.
        2. Filename prefix match against template prefixes in each project.
        3. Fallback folder-name match against the script path components.

        Sets ``auto_target_base_name`` and ``auto_expand_prefixes`` as instance
        attributes so ``refresh_tree`` can highlight and expand the relevant rows.
        """
        self.auto_target_base_name = None
        self.auto_expand_prefixes = []
        try:
            script_path = nuke.scriptName().replace("\\", "/").lower()
            if not script_path or script_path == "root":
                return
            script_parts = script_path.split("/")
            script_file = script_parts[-1]
            script_prefix = script_file.split("_")[0] if "_" in script_file else ""
            script_no_ext = script_file.replace(".nk", "")
            script_base_name = re.sub(r'_v\d+$', '', script_no_ext, flags=re.IGNORECASE)

            best_proj = None
            for proj_display, proj_templates in self.projects_dict.items():
                if proj_display == "My Templates":
                    continue
                for tpl in proj_templates:
                    tpl_base_name = re.sub(r'_v\d+$', '', tpl["name"], flags=re.IGNORECASE).lower()
                    if script_base_name == tpl_base_name:
                        best_proj = proj_display
                        self.auto_target_base_name = script_base_name
                        break
                if best_proj:
                    break

            if not best_proj and script_prefix:
                for proj_display, proj_templates in self.projects_dict.items():
                    if proj_display == "My Templates":
                        continue
                    for tpl in proj_templates:
                        tpl_file = tpl["name"].lower()
                        tpl_prefix = tpl_file.split("_")[0] if "_" in tpl_file else ""
                        if tpl_prefix == script_prefix:
                            best_proj = proj_display
                            self.auto_expand_prefixes.append(script_prefix)
                            break
                    if best_proj:
                        break

            if not best_proj:
                for proj_display, proj_raw in self.project_raw_map.items():
                    if proj_raw.lower() in script_parts or proj_raw.lower() in script_path:
                        best_proj = proj_display
                        break

            if best_proj:
                index = self.project_dropdown.findText(best_proj)
                if index >= 0:
                    self.project_dropdown.setCurrentIndex(index)
        except Exception:
            pass

    def refresh_tree(self):
        """Rebuild the tree widget based on the selected project and current search text.

        Preserves the expanded state of folder nodes across rebuilds, applies
        auto-detection highlights set by :meth:`auto_detect_project`, and
        performs a Python-side natural sort so Qt's built-in sort cannot
        destroy the folder hierarchy.
        """
        current_project = self.project_dropdown.currentText()
        if not current_project:
            return
        project_templates = self.projects_dict.get(current_project, [])

        search_term = self.search_bar.text().lower().split()
        names_queries = [q for q in search_term if not q.startswith("@")]
        tag_queries = [q[1:] for q in search_term if q.startswith("@")]

        filtered_templates = []
        for tpl in project_templates:
            name_match = all(q in tpl["name"].lower() for q in names_queries)
            tags = [tag.lower() for tag in tpl.get("tags", [])]
            tag_match = all(q in tags for q in tag_queries)
            if name_match and tag_match:
                filtered_templates.append(tpl)

        expanded_folders = set()
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree_widget)
        while iterator.value():
            item = iterator.value()
            if item.isExpanded() and not item.data(0, QtCore.Qt.UserRole):
                expanded_folders.add(item.text(0))
            iterator += 1

        self.tree_widget.blockSignals(True)
        self.tree_widget.clear()
        self.tree_widget.blockSignals(False)

        folder_nodes = {}
        grouped_templates = self.group_versions(filtered_templates)

        def custom_sort_key(b):
            latest_tpl = grouped_templates[b][0][1]
            if self.current_sort_col == 2:
                return (latest_tpl.get("has_gizmos", False), b)
            elif self.current_sort_col == 3:
                return (latest_tpl["status"], b)
            elif self.current_sort_col == 4:
                tags = latest_tpl.get("tags", [])
                tag_str = tags[0].lower() if tags else "zzzz"
                return (tag_str, b)
            else:
                return self.natural_sort_key(b, latest_tpl)

        sorted_base_names = sorted(
            grouped_templates.keys(),
            key=custom_sort_key,
            reverse=self.current_sort_reverse
        )

        for base_name in sorted_base_names:
            versions = grouped_templates[base_name]
            latest_v_num, latest_tpl = versions[0]

            current_parent = self.tree_widget
            current_path_tuple = []

            for folder_name in latest_tpl["_hierarchy"]:
                current_path_tuple.append(folder_name)
                path_key = tuple(current_path_tuple)
                if path_key not in folder_nodes:
                    folder_item = QtWidgets.QTreeWidgetItem()
                    folder_item.setText(0, folder_name)
                    font = folder_item.font(0)
                    font.setBold(True)
                    folder_item.setFont(0, font)
                    if isinstance(current_parent, QtWidgets.QTreeWidget):
                        current_parent.addTopLevelItem(folder_item)
                    else:
                        current_parent.addChild(folder_item)
                    folder_nodes[path_key] = folder_item
                    if search_term:
                        folder_item.setExpanded(True)
                current_parent = folder_nodes[path_key]

            item = QtWidgets.QTreeWidgetItem(current_parent)
            display_name = re.sub(r'_v\d+$', '', latest_tpl["name"], flags=re.IGNORECASE)
            item.setText(0, display_name)

            if latest_tpl["status"] == "OK":
                item.setText(2, "[OK]")
            elif latest_tpl["status"] == "MISSING_NODES":
                missing_str = ", ".join(latest_tpl["missing_nodes"])
                item.setText(2, "[MISSING]")
                item.setToolTip(2, "Missing Plugins:\n{0}".format(missing_str))
            elif latest_tpl["status"] == "FILE_TOO_LARGE":
                item.setText(2, "[TOO LARGE]")
                item.setForeground(2, QtGui.QBrush(QtGui.QColor(255, 170, 0)))
            else:
                item.setText(2, "[ERROR]")

            tags_str = ", ".join(latest_tpl.get("tags", []))
            if latest_tpl.get("tags"):
                color = self.get_tag_color(latest_tpl["tags"][0])
                item.setForeground(4, QtGui.QBrush(color))

            item.setText(4, tags_str)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)

            if latest_tpl.get("has_gizmos"):
                item.setText(3, "Yes")
                item.setForeground(3, QtGui.QBrush(QtGui.QColor(255, 170, 0)))
            else:
                item.setText(3, "No")
                item.setForeground(3, QtGui.QBrush(QtGui.QColor(150, 150, 150)))

            project_settings_mode = latest_tpl.get("project_settings_mode", "AGNOSTIC")
            resolution = latest_tpl.get("resolution")
            fps = latest_tpl.get("fps")
            clr = latest_tpl.get("colorspace")
            settings_chunks = []

            if project_settings_mode != "AGNOSTIC":
                if resolution:
                    settings_chunks.append(f"{resolution[0]}x{resolution[1]}")
                if fps:
                    settings_chunks.append(f"{fps:g}fps")
                if clr:
                    settings_chunks.append(str(clr))

            item.setText(1, " | ".join(settings_chunks))
            item.setForeground(1, QtGui.QBrush(QtGui.QColor(180, 180, 180)))

            if latest_tpl.get("is_stamps"):
                item.setForeground(0, QtGui.QBrush(QtGui.QColor(0, 170, 255)))

            item.setData(0, QtCore.Qt.UserRole, latest_tpl)

            target_base = getattr(self, "auto_target_base_name", None)
            display_base = re.sub(r'_v\d+$', '', latest_tpl["name"], flags=re.IGNORECASE).lower()
            if target_base and display_base == target_base:
                temp_parent = item.parent()
                while temp_parent:
                    temp_parent.setExpanded(True)
                    temp_parent = temp_parent.parent()
                item.setSelected(True)
                self.tree_widget.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)

            target_prefixes = getattr(self, "auto_expand_prefixes", [])
            if target_prefixes:
                item_prefix = display_base.split("_")[0] if "_" in display_base else display_base
                if item_prefix in target_prefixes:
                    temp_parent = item.parent()
                    while temp_parent:
                        temp_parent.setExpanded(True)
                        temp_parent = temp_parent.parent()

            if len(versions) > 1:
                for v_num, old_tpl in versions[1:]:
                    old_item = QtWidgets.QTreeWidgetItem(item)
                    old_item.setText(0, old_tpl['name'])

                    if old_tpl["status"] == "OK":
                        old_item.setText(2, "[OK]")
                    elif old_tpl["status"] == "MISSING_NODES":
                        old_item.setText(2, "[MISSING]")
                        old_item.setToolTip(2, "Missing Plugins:\n{0}".format(", ".join(old_tpl["missing_nodes"])))
                    elif old_tpl["status"] == "FILE_TOO_LARGE":
                        old_item.setText(2, "[TOO LARGE]")
                    else:
                        old_item.setText(2, "[ERROR]")

                    old_item.setForeground(0, QtGui.QBrush(QtGui.QColor(150, 150, 150)))
                    old_item.setForeground(2, QtGui.QBrush(QtGui.QColor(150, 150, 150)))

                    if old_tpl.get("has_gizmos"):
                        old_item.setText(3, "Yes")
                    else:
                        old_item.setText(3, "No")
                    old_item.setForeground(3, QtGui.QBrush(QtGui.QColor(150, 150, 150)))

                    old_item.setData(0, QtCore.Qt.UserRole, old_tpl)

        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree_widget)
        while iterator.value():
            item = iterator.value()
            if not item.data(0, QtCore.Qt.UserRole) and item.text(0) in expanded_folders:
                item.setExpanded(True)
            iterator += 1

        self.auto_target_base_name = None
        self.auto_expand_prefixes = []

    def filter_current_project(self):
        """Trigger a tree rebuild when the search bar text changes.

        Wired to the search bar's ``textChanged`` signal. Delegating
        to :meth:`refresh_tree` ensures the filter logic, sort logic,
        and folder-expansion-preservation logic stay in one place.
        """
        self.refresh_tree()

    def group_versions(self, template_list):
        """Group templates by base name and sort each group by version descending.

        Templates whose names end in ``_v##`` are clustered together under the
        un-versioned base name. Templates without a version suffix receive
        version number ``0`` and are keyed by their absolute file path to
        guarantee uniqueness — same-named templates in different subfolders
        will never collide. The display label is always read from
        ``tpl['name']``, not from the dict key.

        Args:
            template_list (list[dict]): A filtered list of template metadata dicts.

        Returns:
            dict: Mapping of ``base_name`` → sorted list of ``(version, tpl)`` tuples,
                highest version first.
        """
        grouped = {}
        version_pattern = re.compile(r'^(.*)_v(\d+)$', re.IGNORECASE)
        for tpl in template_list:
            match = version_pattern.match(tpl['name'])
            if match:
                base_name = match.group(1)
                version = int(match.group(2))
            else:
                base_name = tpl['path']
                version = 0
            if base_name not in grouped:
                grouped[base_name] = []
            grouped[base_name].append((version, tpl))
        for base in grouped:
            grouped[base].sort(key=lambda x: x[0], reverse=True)
        return grouped

    def import_template(self, item, column):
        """Import the template represented by a tree item into Nuke.

        Triggered by a double-click on the tree widget or by the
        Import Selected button. The behaviour depends on which
        column the user double-clicked and on the template's status:

        * Clicks on columns 0–3 trigger the import flow. Before the
          paste, the function compares the template's project
          settings (frame rate, resolution, colour management)
          against the current Nuke script and, if they differ, opens
          a three-way dialog letting the user update the project,
          import the template's nodes without touching the project
          settings, or cancel.
        * Clicks on column 4 (Tags) instead put the cell into edit
          mode so the user can change tags inline.
        * Templates with a ``MISSING_NODES`` status produce an
          additional confirmation prompt before the paste actually
          runs.
        * Templates with a ``READ_ERROR`` status are silently
          ignored.

        On a successful paste the manager window closes; on a user
        cancellation or paste failure it stays open so the user can
        try a different template.

        Args:
            item (QtWidgets.QTreeWidgetItem): The tree item the user
                clicked. Must carry a template dictionary on
                ``UserRole`` for column 0; folder rows are ignored.
            column (int): The column index of the click.
        """
        tpl = item.data(0, QtCore.Qt.UserRole)
        if not tpl:
            return

        if column in (0, 1, 2, 3):
            try:
                project_settings_mode = tpl.get("project_settings_mode", "AGNOSTIC")

                if project_settings_mode != "AGNOSTIC":
                    mismatches = []
                    tpl_fps = tpl.get("fps")
                    tpl_resolution = tpl.get("resolution")
                    tpl_clr = tpl.get("colorspace")

                    if tpl_fps:
                        curr_fps = nuke.root().knob("fps").value()
                        if float(tpl_fps) != curr_fps:
                            mismatches.append(f"FPS: {curr_fps:g} -> {float(tpl_fps):g}")

                    if tpl_resolution:
                        curr_format = nuke.root().knob("format").value()
                        curr_resolution = (curr_format.width(), curr_format.height())
                        if tuple(tpl_resolution) != curr_resolution:
                            mismatches.append(f"Resolution: {curr_resolution[0]}x{curr_resolution[1]} -> {tpl_resolution[0]}x{tpl_resolution[1]}")

                    if tpl_clr:
                        if nuke.root().knob("colorManagement").value() == "OCIO":
                            curr_clr = nuke.root().knob("OCIO_config").value()
                        else:
                            curr_clr = nuke.root().knob("colorManagement").value()
                        if tpl_clr != curr_clr:
                            mismatches.append(f"Colorspace: {curr_clr} -> {tpl_clr}")

                    if mismatches:
                        msg = QtWidgets.QMessageBox()
                        msg.setWindowTitle("Project Settings Mismatch")
                        msg.setText("This template was built with different project settings than your current Nuke script.\n\n" + "\n".join(mismatches) + "\n\nDo you want to update your Nuke Project Settings?")

                        btn_update = msg.addButton("Update Project", QtWidgets.QMessageBox.AcceptRole)
                        btn_import = msg.addButton("Just Import Nodes", QtWidgets.QMessageBox.NoRole)
                        btn_cancel = msg.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)

                        msg.exec_()
                        clicked_btn = msg.clickedButton()

                        if clicked_btn == btn_cancel or clicked_btn is None:
                            return

                        if clicked_btn == btn_update:
                            if tpl_fps:
                                nuke.root().knob('fps').setValue(float(tpl_fps))
                            if tpl_resolution:
                                try:
                                    nuke.root().knob('format').setValue(tpl_resolution)
                                except Exception:
                                    pass
                            if tpl_clr:
                                try:
                                    nuke.root().knob('colorManagement').setValue("OCIO")
                                    nuke.root().knob('OCIO_config').setValue(tpl_clr)
                                except Exception:
                                    pass
            except Exception as e:
                print("Settings check failed:", e)

            if tpl["status"] in ["OK", "FILE_TOO_LARGE"]:
                if self.execute_import(tpl["path"]):
                    self.close()
            elif tpl["status"] == "MISSING_NODES":
                missing = "\n".join(tpl["missing_nodes"])
                warning = "Warning: This template is missing the following plugins:\n\n{0}\n\nDo you want to force import it anyway?".format(missing)
                if nuke.ask(warning):
                    if self.execute_import(tpl["path"]):
                        self.close()

        elif column == 4:
            item.treeWidget().editItem(item, column)

    def save_inline_tags(self, item, column):
        """Update template metadata and sync memory state after inline tag editing.

        Called automatically by the ``itemChanged`` signal. Only processes
        changes to column 3 (the Tags column). Persists the new tags to disk
        via :func:`saves.save_metadata` and refreshes the autocomplete model.

        Args:
            item (QTreeWidgetItem): The item whose cell was edited.
            column (int): The column that changed.
        """
        if column == 4:
            tpl = item.data(0, QtCore.Qt.UserRole)
            if not tpl:
                return
            new_tags_str = item.text(4)
            new_tags = [t.strip() for t in new_tags_str.split(",") if t.strip()]
            for master_tpl in self.alltemplates:
                if master_tpl["path"] == tpl["path"]:
                    master_tpl["tags"] = new_tags
                    break
            tpl["tags"] = new_tags
            item.setData(0, QtCore.Qt.UserRole, tpl)
            filename = os.path.basename(tpl["path"])
            saves.save_metadata(filename, new_tags)
            if new_tags:
                color = self.get_tag_color(new_tags[0])
                item.setForeground(4, QtGui.QBrush(color))
            else:
                item.setForeground(4, QtGui.QBrush(QtGui.QColor(200, 200, 200)))
            self.update_autocomplete()

    def import_from_button(self):
        """Trigger the import flow from the Import Selected button.

        Validates that at least one tree item is selected, then
        delegates to :meth:`import_template` with column ``0`` as if
        the user had double-clicked the row directly. When the
        selection is empty, the user is informed via
        :func:`nuke.message` and no action is taken.
        """
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            nuke.message("Please select a template to import.")
            return
        item = selected_items[0]
        self.import_template(item, 0)

    def get_tag_color(self, tag_string):
        """Generate a procedural QColor derived from a tag string.

        The hue is computed by summing position-weighted character ordinals and
        then multiplying by a prime step to spread values across the 360-degree
        hue wheel. Saturation and value are fixed to keep colours vivid but
        consistent with the UI palette.

        Args:
            tag_string (str): The tag whose colour should be calculated.

        Returns:
            QtGui.QColor: An HSV colour unique to the given tag string.
        """
        tag_string = tag_string.strip().lower()
        hue = sum(ord(char) * (i + 1) for i, char in enumerate(tag_string))
        hue = (hue * 45) % 360
        return QtGui.QColor.fromHsv(hue, 150, 255)

    def update_autocomplete(self):
        """Refresh the search-bar QCompleter model with current tags.

        Recomputes the set of every tag attached to any template in
        :attr:`alltemplates`, prefixes each with ``@``, sorts the
        result, and installs it as the completer's data source so
        newly-added tags appear in autocomplete suggestions
        immediately after they are saved.
        """
        unique_tags = {tag for t in self.alltemplates for tag in t.get("tags", [])}
        autocomplete_list = sorted(["@" + tag for tag in unique_tags])
        model = QtCore.QStringListModel()
        model.setStringList(autocomplete_list)
        self.completer.setModel(model)

    def open_context_menu(self, position):
        """Show the right-click context menu and dispatch the chosen action.

        Builds a context menu offering two actions on the currently
        selected template rows: Batch Tag (opens
        :class:`BatchTagDialog` to apply or replace tags on every
        selected row at once) and Re-Evaluate Auto-Tags (re-parses
        each selected ``.nk`` file and replaces its tags with the
        output of the current auto-tag rule engine, prompting the
        user once for confirmation first).

        Folder rows that carry no template data are filtered out
        before the menu is built; if no real template rows are
        selected the menu does not appear.

        Args:
            position (QtCore.QPoint): The click position in tree
                viewport coordinates, used to anchor the popup menu.
        """
        selected_items = self.tree_widget.selectedItems()
        valid_items = [i for i in selected_items if i.data(0, QtCore.Qt.UserRole)]

        if not valid_items:
            return

        menu = QtWidgets.QMenu()
        batch_tag_action = menu.addAction("Batch Tag ({0} selected)".format(len(valid_items)))
        auto_tag_action = menu.addAction("Re-Evaluate Auto-Tags")

        action = menu.exec_(self.tree_widget.viewport().mapToGlobal(position))

        if action == batch_tag_action:
            dialog = BatchTagDialog(parent=self)
            if not dialog.exec_():
                return

            new_tags = dialog.tags
            mode = dialog.mode

            for item in valid_items:
                tpl = item.data(0, QtCore.Qt.UserRole)

                if mode == "append":
                    current_tags = tpl.get("tags", [])
                    final_tags = sorted(list(set(current_tags + new_tags)))
                else:
                    final_tags = new_tags

                for master_tpl in self.alltemplates:
                    if master_tpl["path"] == tpl["path"]:
                        master_tpl["tags"] = final_tags
                        break

                tpl["tags"] = final_tags
                item.setData(0, QtCore.Qt.UserRole, tpl)

                filename = os.path.basename(tpl["path"])
                saves.save_metadata(filename, final_tags)

                item.setText(4, ", ".join(final_tags))
                if final_tags:
                    color = self.get_tag_color(final_tags[0])
                    item.setForeground(4, QtGui.QBrush(color))
                else:
                    item.setForeground(4, QtGui.QBrush(QtGui.QColor(200, 200, 200)))

            self.update_autocomplete()

        elif action == auto_tag_action:
            if not nuke.ask("This will scan the selected templates and completely replace their tags with the current Auto-Tag Rules. Proceed?"):
                return

            from .scanner import NODE_FINDER, get_auto_tags

            for item in valid_items:
                tpl = item.data(0, QtCore.Qt.UserRole)

                try:
                    with io.open(tpl["path"], "r", encoding="utf-8", errors="replace") as f:
                        text = f.read()
                    found_matches = NODE_FINDER.findall(text)
                    found = [name for indent, name, extra in found_matches if indent == "" and (extra.strip() == "" or name.startswith("OFX"))]

                    auto_tags = get_auto_tags(found)
                    final_tags = sorted(list(set(auto_tags)))

                    for master_tpl in self.alltemplates:
                        if master_tpl["path"] == tpl["path"]:
                            master_tpl["tags"] = final_tags
                            break

                    tpl["tags"] = final_tags
                    item.setData(0, QtCore.Qt.UserRole, tpl)

                    filename = os.path.basename(tpl["path"])
                    saves.save_metadata(filename, final_tags)

                    item.setText(4, ", ".join(final_tags))
                    if final_tags:
                        color = self.get_tag_color(final_tags[0])
                        item.setForeground(4, QtGui.QBrush(color))
                    else:
                        item.setForeground(4, QtGui.QBrush(QtGui.QColor(200, 200, 200)))
                except Exception as e:
                    print(f"Failed to auto-tag {tpl['name']}: {e}")

            self.update_autocomplete()

    def save_new_template(self):
        """Run the in-UI Save Template flow against the current Nuke selection.

        Builds ``projects_dict`` (display name → set of known subfolder paths) and
        ``project_raw_map`` from the currently loaded templates, then opens
        :class:`SaveTemplateDialog`. On acceptance, resolves the final save path
        via :func:`saves.get_save_path`, optionally prompts for overwrite
        confirmation, and writes the nodes with ``nuke.nodeCopy``.
        It also intercepts Read nodes and prompts the user to convert them to Placeholders.

        Any Read-to-Placeholder swap performed during the save is
        reverted by an undo in the ``finally`` block so the artist's
        Nuke script is left exactly as it was before the save.
        """
        try:
            selected_nodes = nuke.selectedNodes()
            if not selected_nodes:
                nuke.message("Please select some nodes to save as a template.")
                return
        except Exception:
            print("Not running inside Nuke.")
            return

        read_nodes = [n for n in selected_nodes if n.Class() == "Read"]
        nodes_to_convert = []

        if read_nodes:
            dialog = PlaceholderDialog(read_nodes, parent=self)
            if dialog.exec_():
                nodes_to_convert = dialog.get_nodes_to_convert()
            else:
                return

        projects_for_dialog = {}
        for tpl in self.alltemplates:
            proj_display, _, hierarchy = self.parse_path_context(tpl["path"])
            if proj_display not in projects_for_dialog:
                projects_for_dialog[proj_display] = set()
            if hierarchy:
                projects_for_dialog[proj_display].add("/".join(hierarchy))

        default_root = self.base_template_paths[0] if self.base_template_paths else os.path.expanduser("~/.nuke/templates")
        current_project = self.project_dropdown.currentText()
        detected_project = current_project if current_project != "My Templates" else None

        dialog = SaveTemplateDialog(
            projects_for_dialog,
            self.project_raw_map,
            detected_project,
            default_root,
            parent=self,
        )

        if dialog.exec_():
            base_name, folder_path, do_version = dialog.get_save_data()
            if not base_name:
                nuke.message("Template Name cannot be empty.")
                return

            final_file_path = saves.get_save_path(folder_path, base_name, auto_version=do_version)
            if not do_version and os.path.exists(final_file_path):
                warning_msg = "A template named '{0}' already exists in this location.\n\nDo you want to update/overwrite it?".format(os.path.basename(final_file_path))
                if not nuke.ask(warning_msg):
                    return

            try:
                os.makedirs(folder_path, exist_ok=True)

                if nodes_to_convert:
                    nuke.Undo().begin("Template Save Placeholders")
                    for r in nodes_to_convert:
                        name = r.name()
                        file_path = r.knob('file').value()
                        base_file = os.path.basename(file_path) if file_path else "Plate"

                        p = nuke.nodes.NoOp(name="PLACEHOLDER_" + name)
                        p.knob('tile_color').setValue(0xff0000ff)
                        p.knob('label').setValue("REPLACE WITH:\n" + base_file)

                        for dep in r.dependent():
                            for i in range(dep.inputs()):
                                if dep.input(i) == r:
                                    dep.setInput(i, p)

                        r.setSelected(False)
                        p.setSelected(True)
                    nuke.Undo().end()

                nuke.nodeCopy(final_file_path)
                nuke.message("Template saved successfully as:\n" + os.path.basename(final_file_path))
                self.close()
            finally:
                if nodes_to_convert:
                    nuke.Undo().undo()

    def execute_import(self, filepath):
        """Import a template file, optionally swapping Read nodes to Placeholders.

        The function does not modify the on-disk template. Instead it
        reads the ``.nk`` source into memory, optionally rewrites the
        in-memory text to replace selected ``Read { ... }`` blocks
        with red-tile-coloured ``NoOp`` placeholders preserving the
        original node names and DAG positions, writes the modified
        text to a hidden temporary file under
        ``~/.nuke/Template_Manager/.temp_import.nk``, and pastes that
        temporary file via ``nuke.nodePaste``. The temporary file is
        always deleted before the function returns, even on paste
        failure.

        The user is prompted via :class:`PlaceholderDialog` to choose
        which Read nodes (if any) should be converted. Cancelling
        that dialog aborts the import.

        Args:
            filepath (str): Absolute path to the source ``.nk`` template
                file. Must be readable; failures during the initial
                read are logged but do not abort the import (the
                paste will simply use the original file).

        Returns:
            bool: ``True`` if the paste completed successfully,
            ``False`` if the user cancelled the placeholder dialog
            or the Nuke paste call raised an exception.
        """
        read_data = []

        try:
            with io.open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()

            read_blocks = re.findall(r'(^[ \t]*)Read\s*\{(.*?)^[ \t]*\}', text, re.MULTILINE | re.DOTALL)

            for indent, block_content in read_blocks:
                name_match = re.search(r'^[ \t]*name\s+([^\n]+)', block_content, re.MULTILINE)
                file_match = re.search(r'^[ \t]*file\s+([^\n]+)', block_content, re.MULTILINE)

                current_name = name_match.group(1).strip().strip('"') if name_match else "Read"
                current_file = file_match.group(1).strip().strip('"') if file_match else "Empty/No File"

                read_data.append((current_name, current_file))
        except Exception as e:
            print("Error parsing Read nodes:", e)

        names_to_convert = []
        if read_data:
            dialog = PlaceholderDialog(read_data, parent=self)
            if dialog.exec_():
                names_to_convert = dialog.get_nodes_to_convert()
            else:
                return False

        paste_path = filepath
        temp_filepath = None

        if names_to_convert:
            def replacer(match):
                """Substitute a Read block with a placeholder NoOp when its name is selected.

                Args:
                    match (re.Match): A regex match for one
                        ``Read { ... }`` block, with group 1 capturing
                        the leading indentation and group 2 capturing
                        the block body.

                Returns:
                    str: Either the original block text untouched (if
                    its node name is not in the user's conversion
                    list) or a NoOp declaration carrying the same
                    DAG coordinates, a red tile colour, and a label
                    pointing at the original filename.
                """
                indent = match.group(1)
                block_content = match.group(2)

                name_match = re.search(r'^[ \t]*name\s+([^\n]+)', block_content, re.MULTILINE)
                current_name = name_match.group(1).strip().strip('"') if name_match else ""

                if current_name in names_to_convert:
                    file_match = re.search(r'^[ \t]*file\s+([^\n]+)', block_content, re.MULTILINE)
                    current_file = file_match.group(1).strip().strip('"') if file_match else "Plate"
                    base_file = os.path.basename(current_file)

                    xpos_match = re.search(r'^[ \t]*xpos\s+([^\n]+)', block_content, re.MULTILINE)
                    ypos_match = re.search(r'^[ \t]*ypos\s+([^\n]+)', block_content, re.MULTILINE)

                    xpos = xpos_match.group(1).strip() if xpos_match else "0"
                    ypos = ypos_match.group(1).strip() if ypos_match else "0"

                    return (
                        f"{indent}NoOp {{\n"
                        f"{indent} inputs 0\n"
                        f"{indent} name PLACEHOLDER_{current_name}\n"
                        f"{indent} tile_color 0xff0000ff\n"
                        f"{indent} label \"REPLACE WITH:\\n{base_file}\"\n"
                        f"{indent} xpos {xpos}\n"
                        f"{indent} ypos {ypos}\n"
                        f"{indent}}}"
                    )
                return match.group(0)

            modified_text = re.sub(r'(^[ \t]*)Read\s*\{(.*?)^[ \t]*\}', replacer, text, flags=re.MULTILINE | re.DOTALL)

            temp_filepath = os.path.join(os.path.expanduser("~/.nuke/Template_Manager"), ".temp_import.nk").replace("\\", "/")
            try:
                with io.open(temp_filepath, 'w', encoding='utf-8') as tf:
                    tf.write(modified_text)
                paste_path = temp_filepath
            except Exception as e:
                print("Failed to write temp file:", e)

        nuke.Undo().begin("Import Template")
        paste_succeeded = True
        try:
            try:
                nuke.nodePaste(paste_path)
            except Exception as e:
                nuke.message(f"Failed to paste template:\n{e}")
                paste_succeeded = False
        finally:
            nuke.Undo().end()
            if temp_filepath and os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except Exception:
                    pass

        return paste_succeeded


class BatchTagDialog(QtWidgets.QDialog):
    """Modal dialog letting the user batch-tag multiple selected templates.

    Presents a single comma-separated tag input and two action buttons:

    * **Overwrite** replaces the tag list on every selected template
      with the typed tags, discarding whatever was there before.
    * **Append** merges the typed tags into each template's existing
      tag list, deduplicating the result.

    The chosen mode is stored in :attr:`mode` (either ``"append"`` or
    ``"overwrite"``) and the parsed tag list in :attr:`tags`, ready
    for the caller to consume after the dialog is accepted.

    Args:
        parent (QWidget, optional): Parent widget for the dialog.
            Defaults to ``None``.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Tag Templates")
        self.resize(350, 100)

        layout = QtWidgets.QVBoxLayout(self)

        layout.addWidget(QtWidgets.QLabel("Enter tags separated by commas:"))
        self.tag_input = QtWidgets.QLineEdit()
        self.tag_input.setPlaceholderText("e.g. Keying, Core, v02")
        layout.addWidget(self.tag_input)

        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_overwrite = QtWidgets.QPushButton("Overwrite")
        self.btn_append = QtWidgets.QPushButton("Append")
        self.btn_cancel = QtWidgets.QPushButton("Cancel")

        self.btn_append.clicked.connect(self.accept_append)
        self.btn_overwrite.clicked.connect(self.accept_overwrite)
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_overwrite)
        btn_layout.addWidget(self.btn_append)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

        self.mode = None
        self.tags = []

    def accept_append(self):
        """Set the mode to ``"append"`` and accept the dialog.

        Wired to the Append button. Records the chosen mode and
        delegates the actual tag parsing to :meth:`_process_tags`
        before the dialog closes.
        """
        self.mode = "append"
        self._process_tags()

    def accept_overwrite(self):
        """Set the mode to ``"overwrite"`` and accept the dialog.

        Wired to the Overwrite button. Records the chosen mode and
        delegates the actual tag parsing to :meth:`_process_tags`
        before the dialog closes.
        """
        self.mode = "overwrite"
        self._process_tags()

    def _process_tags(self):
        """Parse the tag input field and accept the dialog.

        Splits the raw input on commas, strips each fragment, and
        discards empty entries. The cleaned list is stored on
        :attr:`tags` for the caller to read after the dialog closes.
        Called by both :meth:`accept_append` and
        :meth:`accept_overwrite`.
        """
        raw = self.tag_input.text()
        self.tags = [t.strip() for t in raw.split(",") if t.strip()]
        self.accept()


class RuleWidget(QtWidgets.QWidget):
    """A single editable row inside the auto-tag rules dialog.

    Each row exposes four editable fields plus a delete button:

    * **Tag Name** — the tag that this rule emits when it matches.
    * **Type** — a dropdown choosing between OR (the JSON ``any``
      type), AND (``all``), and How Many (``count``).
    * **Threshold** — an integer spin box, visible only when the
      type is How Many, controlling the minimum match count.
    * **Nodes** — a comma-separated list of lowercase node class
      substrings to match against the templates being scanned.
    * **X** — a remove button that destroys this row.

    The widget translates between the rule dictionary schema used by
    :data:`saves.DEFAULT_TAG_RULES` and the UI controls
    transparently: :meth:`__init__` deserialises a rule into the
    widgets, and :meth:`get_data` serialises the widget state back
    into a rule.

    Args:
        tag_name (str): Initial tag name to display in the input
            field. Defaults to an empty string for new rules.
        rule_data (dict, optional): Initial rule dictionary, with
            the keys ``type``, ``nodes`` and (for count rules)
            ``threshold``. Defaults to ``None``, which is treated
            as an empty rule.
        parent (QWidget, optional): Parent widget. Defaults to
            ``None``.
    """

    def __init__(self, tag_name="", rule_data=None, parent=None):
        super().__init__(parent)
        if rule_data is None:
            rule_data = {}

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tag_input = QtWidgets.QLineEdit(tag_name)
        self.tag_input.setPlaceholderText("Tag Name (e.g. Keying)")
        self.tag_input.setFixedWidth(150)

        self.type_dropdown = QtWidgets.QComboBox()
        self.type_dropdown.addItems(["OR", "AND", "How Many"])
        self.type_dropdown.setFixedWidth(130)

        r_type = rule_data.get("type", "any")
        if r_type == "all":
            self.type_dropdown.setCurrentIndex(1)
        elif r_type == "count":
            self.type_dropdown.setCurrentIndex(2)
        else:
            self.type_dropdown.setCurrentIndex(0)

        self.threshold_spin = QtWidgets.QSpinBox()
        self.threshold_spin.setMinimum(1)
        self.threshold_spin.setValue(rule_data.get("threshold", 5))
        self.threshold_spin.setFixedWidth(50)
        self.threshold_spin.setVisible(r_type == "count")

        self.type_dropdown.currentIndexChanged.connect(self.on_type_changed)

        self.nodes_input = QtWidgets.QLineEdit()
        self.nodes_input.setPlaceholderText("primatte, keylight, ibkgizmo")
        nodes_list = rule_data.get("nodes", [])
        self.nodes_input.setText(", ".join(nodes_list))

        self.btn_remove = QtWidgets.QPushButton("X")
        self.btn_remove.setFixedWidth(30)

        layout.addWidget(self.tag_input)
        layout.addWidget(self.type_dropdown)
        layout.addWidget(self.threshold_spin)
        layout.addWidget(self.nodes_input)
        layout.addWidget(self.btn_remove)

    def on_type_changed(self, index):
        """Show or hide the threshold spinner when the rule type changes.

        The threshold value is only meaningful for the How Many
        (``count``) rule type, so the spin box stays hidden in
        every other mode to keep the row visually compact.

        Args:
            index (int): The newly selected index in the type
                dropdown. ``2`` corresponds to How Many; any other
                value hides the spinner.
        """
        self.threshold_spin.setVisible(index == 2)

    def get_data(self):
        """Serialise the row's UI state into a rule dictionary.

        Reads the four user-editable fields, sanitises them (stripping
        whitespace and splitting the comma-separated node list), and
        builds a rule dictionary in the schema consumed by
        :func:`scanner.get_auto_tags` and persisted by
        :func:`saves.save_auto_tag_rules`. Rows whose tag-name field
        is empty are treated as deletable and return a pair of
        ``None`` values so the caller can drop them.

        Returns:
            tuple: A 2-tuple ``(tag_name, rule_dict)``.

            * ``tag_name`` (str | None) — the cleaned tag string, or
              ``None`` when the row should be dropped because its
              tag name is empty.
            * ``rule_dict`` (dict | None) — a rule dictionary with
              the keys ``type`` (one of ``"any"``, ``"all"``,
              ``"count"``), ``nodes`` (list of substrings), and for
              the count type ``threshold`` (int). ``None`` when the
              row should be dropped.
        """
        tag_name = self.tag_input.text().strip()
        if not tag_name:
            return None, None

        idx = self.type_dropdown.currentIndex()
        r_type = "any"
        if idx == 1:
            r_type = "all"
        elif idx == 2:
            r_type = "count"

        nodes_raw = self.nodes_input.text()
        nodes = [n.strip() for n in nodes_raw.split(",") if n.strip()]

        data = {"type": r_type, "nodes": nodes}
        if r_type == "count":
            data["threshold"] = self.threshold_spin.value()

        return tag_name, data


class AutoTagRulesDialog(QtWidgets.QDialog):
    """A form-based editor for the auto-tagging rule set.

    Displays the current rule set as a scrollable list of
    :class:`RuleWidget` rows. The user can add new rules with the
    "+ Add New Rule" button, remove any existing rule with its row's
    X button, and persist the complete edited set with the Save
    button (which in turn calls :func:`saves.save_auto_tag_rules`).
    The Cancel button discards every change made since the dialog
    opened.

    Rule changes take effect on the next scan or on the next use of
    the Re-Evaluate Auto-Tags context menu action; already-loaded
    templates in an open browser window are unaffected.

    Args:
        parent (QWidget, optional): Parent widget for the dialog,
            typically Nuke's main window obtained via
            :func:`get_nuke_main_window`. Defaults to ``None``.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Tagging Rules")
        self.resize(750, 400)

        self.main_layout = QtWidgets.QVBoxLayout(self)

        info = QtWidgets.QLabel("Define automatic tags based on node contents. Separate multiple nodes with commas.")
        self.main_layout.addWidget(info)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QtWidgets.QWidget()
        self.rules_layout = QtWidgets.QVBoxLayout(self.scroll_widget)
        self.rules_layout.setAlignment(QtCore.Qt.AlignTop)
        self.scroll_area.setWidget(self.scroll_widget)

        self.main_layout.addWidget(self.scroll_area)

        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("+ Add New Rule")
        self.btn_save = QtWidgets.QPushButton("Save")
        btn_cancel = QtWidgets.QPushButton("Cancel")

        self.btn_add.clicked.connect(self.add_empty_rule)
        self.btn_save.clicked.connect(self.save_rules)
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(btn_cancel)

        self.main_layout.addLayout(btn_layout)

        self.rule_widgets = []
        self.load_rules()

    def load_rules(self):
        """Load the persisted rule set from disk and populate the dialog.

        Calls :func:`saves.load_auto_tag_rules` to read the current
        on-disk JSON, then creates one :class:`RuleWidget` row per
        rule entry by delegating to :meth:`add_rule_widget`. Invoked
        once during initialisation; never called again afterwards.
        """
        data = saves.load_auto_tag_rules()
        for tag_name, rule_data in data.items():
            self.add_rule_widget(tag_name, rule_data)

    def add_empty_rule(self):
        """Append a new blank rule row to the dialog.

        Wired to the "+ Add New Rule" button. The created row carries
        no initial tag name and an empty rule dictionary, ready for
        the user to fill in. The row is appended to the bottom of
        the scrollable list, never inserted in the middle.
        """
        self.add_rule_widget("", {})

    def add_rule_widget(self, tag_name, rule_data):
        """Create a single :class:`RuleWidget` and wire its delete button.

        Instantiates the row widget pre-populated with the supplied
        tag name and rule data, connects its X button to
        :meth:`remove_rule`, adds it to the scrollable rules layout,
        and records it in :attr:`rule_widgets` so :meth:`save_rules`
        can iterate over every active row later.

        Args:
            tag_name (str): Tag name to pre-fill in the row's tag
                input. Pass ``""`` for empty rows.
            rule_data (dict): Rule dictionary to pre-fill in the
                row's controls. Pass ``{}`` for empty rows.
        """
        rw = RuleWidget(tag_name, rule_data, self)
        rw.btn_remove.clicked.connect(lambda: self.remove_rule(rw))
        self.rules_layout.addWidget(rw)
        self.rule_widgets.append(rw)

    def remove_rule(self, rw):
        """Remove a row widget from the dialog and schedule its destruction.

        Wired to each :class:`RuleWidget`'s X button via the lambda
        in :meth:`add_rule_widget`. Detaches the widget from the
        layout, calls ``deleteLater`` to schedule its disposal on
        the next event-loop iteration, and removes the reference
        from :attr:`rule_widgets` so it cannot be re-saved.

        Args:
            rw (RuleWidget): The row to remove.
        """
        self.rules_layout.removeWidget(rw)
        rw.deleteLater()
        if rw in self.rule_widgets:
            self.rule_widgets.remove(rw)

    def save_rules(self):
        """Collect every row's data, persist it, and close the dialog.

        Iterates over every :class:`RuleWidget` in
        :attr:`rule_widgets`, calls :meth:`RuleWidget.get_data` on
        each, and assembles the results into a single dictionary
        suitable for :func:`saves.save_auto_tag_rules`. Rows whose
        tag name is empty are silently dropped (their ``get_data``
        return is ``(None, None)``). After the JSON has been written
        the user is informed via :func:`nuke.message` and the
        dialog accepts.
        """
        new_data = {}
        for rw in self.rule_widgets:
            tag_name, rule_data = rw.get_data()
            if tag_name and rule_data:
                new_data[tag_name] = rule_data

        saves.save_auto_tag_rules(new_data)

        nuke.message("Rules saved successfully!")
        self.accept()


class PlaceholderDialog(QtWidgets.QDialog):
    """Modal checklist for choosing which Read nodes to swap with Placeholders.

    Used by both the save flow (where the input list is a sequence
    of live :class:`nuke.Node` objects) and the import flow (where
    the input list is a sequence of ``(name, file_path)`` tuples
    harvested by parsing the template's raw text). The dialog
    transparently handles either input form, presenting each entry
    as a single check-box item showing the node name alongside its
    associated file's basename.

    Every entry starts in the checked state; the user unchecks any
    Read nodes that should be preserved as-is. The selected entries
    are returned by :meth:`get_nodes_to_convert` as a list of
    whichever object form was originally supplied (live nodes or
    name strings).

    Args:
        read_items (list): The Read nodes or ``(name, file_path)``
            tuples to display. The two forms can be mixed in a
            single dialog but typically are not.
        parent (QWidget, optional): Parent widget. Defaults to
            ``None``.
    """

    def __init__(self, read_items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Convert Read Nodes")
        self.resize(450, 300)

        layout = QtWidgets.QVBoxLayout(self)

        info = QtWidgets.QLabel(
            "Select the Read nodes you want to convert into Placeholders.\n"
            "(Unchecked nodes will be preserved as standard Read nodes)."
        )
        layout.addWidget(info)

        self.list_widget = QtWidgets.QListWidget()
        layout.addWidget(self.list_widget)

        self.node_data = []
        for item_data in read_items:
            if isinstance(item_data, tuple):
                node_name, file_path = item_data
                original_object = node_name
            else:
                node_name = item_data.name()
                file_path = item_data.knob('file').value()
                original_object = item_data

            base_name = os.path.basename(file_path) if file_path else "Empty/No File"
            display_text = f"{node_name}  ({base_name})"

            item = QtWidgets.QListWidgetItem(display_text)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked)

            self.list_widget.addItem(item)
            self.node_data.append((item, original_object))

        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_continue = QtWidgets.QPushButton("Continue")
        btn_cancel = QtWidgets.QPushButton("Cancel")

        self.btn_continue.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_continue)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def get_nodes_to_convert(self):
        """Return the original objects for every checked entry.

        Walks :attr:`node_data` and returns the second element of
        each pair (the original :class:`nuke.Node` or the node-name
        string, depending on which form was supplied at
        construction) for every list item still in the checked
        state.

        Returns:
            list: The subset of the originally-supplied objects
            that the user left checked, in the same order they were
            added to the dialog. The empty list is a valid return
            value and simply means the user unchecked everything.
        """
        return [obj for item, obj in self.node_data if item.checkState() == QtCore.Qt.Checked]