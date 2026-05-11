"""Entry point for the Nuke Template Manager.

This module wires together the configuration layer, the scanner, and
the PySide frontend to provide the three top-level commands exposed to
artists through the Nuke menu:

* :func:`launch_ui` — open the main Template Manager browser.
* :func:`launch_save_ui` — save the currently-selected nodes as a new
  template, with smart fast-track behaviour for re-saves.
* :func:`launch_rules_editor` — open the auto-tag rule editor.

Every function in this module is designed to be invoked directly from a
Nuke menu callback and assumes a live Nuke session.
"""

import os
import re
import importlib.util
from typing import TYPE_CHECKING, List, Set
import nuke
from . import settings
from . import saves
from .scanner import scan_templates, get_available_nodes
from .ui import TemplateManagerUI
if TYPE_CHECKING:
    from PySide6 import QtCore
else:
    try:
        from PySide6 import QtCore
    except ImportError:
        from PySide2 import QtCore


def launch_ui() -> None:
    """Initialise the environment and open the Template Manager browser.

    The function performs the full startup sequence required to show
    the main UI:

    1. Resolve the effective list of template root directories via
       :func:`settings.get_effective_template_paths`.
    2. Build the set of node classes available in the current Nuke
       session via :func:`scanner.get_available_nodes`.
    3. Probe for the optional Stamps plugin by Adrian Pueyo, storing
       the result so the UI can offer Stamps-aware shortcuts.
    4. Run :func:`scanner.scan_templates` against every configured
       root, accumulating the parsed template records.
    5. Instantiate :class:`ui.TemplateManagerUI` with the scan results
       and show it as a non-modal dialog.

    Note:
        A global module-level reference (``tm_window``) is retained to
        prevent Nuke's Python garbage collector from destroying the
        window immediately after the function returns. Replacing this
        reference will close the previous window without animation.
    """
    paths: List[str] = settings.get_effective_template_paths()
    nodes: Set[str] = get_available_nodes()
    has_stamps = importlib.util.find_spec("stamps") is not None

    all_templates = []
    for path in paths:
        all_templates.extend(scan_templates(path, nodes))

    global tm_window
    tm_window = TemplateManagerUI(all_templates, has_stamps)  # type: ignore[reportCallIssue]
    tm_window.show()


def launch_save_ui() -> None:
    """Save the current Nuke selection as a template, with fast-track logic.

    The function is the standalone counterpart of the in-UI Save
    action: it can be triggered directly from the Nuke menu without
    first opening the Template Manager browser. The full flow is:

    1. Verify that at least one node is selected in the DAG, aborting
       with a user-facing message otherwise.
    2. Capture the current script's root settings (format, fps,
       colorManagement, OCIO_config) into a ``template_context``
       dict. If the settings match the agnostic defaults
       (2048x1556, 24fps, "Nuke" colorManagement) the context is
       set to ``None`` and no root injection will occur later.
    3. Walk the first configured template root to build two
       structures: ``projects_dict`` mapping display project names to
       known subfolder paths, and ``fast_track_db`` mapping lowercase
       template base names to their highest-version on-disk location.
    4. Inspect the active Nuke script name. If its base name (after
       version-suffix stripping) appears in ``fast_track_db``, present
       a streamlined "Template Match Found" dialog offering quick
       options to version-up, overwrite the matched version, save as
       the script's own version, or open the full save menu.
    5. If the user chooses a fast-track option the template is written
       directly via ``nuke.nodeCopy``. Because ``nuke.nodeCopy`` only
       copies nodes and not project-level settings, a ``Root { ... }``
       block built from ``template_context`` is then prepended to the
       saved ``.nk`` file (skipped if the context is ``None``), and
       the function returns.
    6. Otherwise the full :class:`ui.SaveTemplateDialog` is shown so
       the user can pick a project, subfolder, name, and versioning
       behaviour.
    7. When the save dialog accepts, any selected Read nodes are
       optionally swapped to Placeholder NoOps via
       :class:`ui.PlaceholderDialog`, the template is copied to disk,
       the same ``Root { ... }`` block is injected when a non-agnostic
       context was captured, and the Read swap is reverted with an
       undo so the artist's script is left untouched.

    All transient Nuke graph modifications performed during the swap
    step are bracketed by ``nuke.Undo()`` calls and reverted in the
    ``finally`` block, so a user exception or paste failure cannot
    leave the artist's session in a corrupted state.

    Note:
        This function uses only message-box dialogs from PySide; it
        does not require the main :class:`ui.TemplateManagerUI`
        window to be open.
    """
    try:    
        selected_nodes = nuke.selectedNodes()
        if not selected_nodes:
            nuke.message("Please select some nodes to save as a template.")
            return
        try:
            root_format = nuke.root()['format'].value()
            current_w = root_format.width()
            current_h = root_format.height()
            current_fps = nuke.root()['fps'].value()

            try:
                current_cm = nuke.root()['colorManagement'].value()
            except Exception:
                current_cm = "Nuke"
                
            try:
                current_ocio = nuke.root()['OCIO_config'].value()
            except Exception:
                current_ocio = ""
            
            DEFAULT_W = 2048
            DEFAULT_H = 1556
            DEFAULT_FPS = 24.0
            DEFAULT_CM = "Nuke"
            if (current_w == DEFAULT_W and current_h == DEFAULT_H and 
                current_fps == DEFAULT_FPS and current_cm == DEFAULT_CM):
                template_context = None  # It's Agnostic!
            else:
                template_context = {
                    "w": current_w, 
                    "h": current_h, 
                    "fps": current_fps,
                    "cm": current_cm,
                    "ocio": current_ocio
                }
        except Exception:
            template_context = None
    except Exception:
        return

    try:
        from PySide6 import QtWidgets
    except ImportError:
        from PySide2 import QtWidgets

    paths = settings.get_effective_template_paths()
    if not paths:
        nuke.message("No template directory configured.")
        return
    default_root = paths[0]

    project_raw_map = {}
    projects_dict = {}

    fast_track_db = {}

    for root_folder, _dirs, files in os.walk(default_root):
        rel_path = os.path.relpath(root_folder, default_root)
        if rel_path == ".":
            continue

        folders = rel_path.replace("\\", "/").split('/')
        proj_raw = folders[0]
        proj_display = proj_raw.replace("_", " ").title()

        project_raw_map[proj_display] = proj_raw

        if proj_display not in projects_dict:
            projects_dict[proj_display] = set()

        if len(folders) > 1:
            projects_dict[proj_display].add("/".join(folders[1:]))

        for f in files:
            if f.endswith(".nk"):
                f_no_ext = f.replace(".nk", "")
                match = re.search(r'_v(\d+)$', f_no_ext, re.IGNORECASE)
                if match:
                    base_name = f_no_ext[:match.start()].lower()
                    version = int(match.group(1))
                else:
                    base_name = f_no_ext.lower()
                    version = 0

                if base_name not in fast_track_db or version > fast_track_db[base_name]["max_v"]:
                    fast_track_db[base_name] = {
                        "folder_path": root_folder.replace("\\", "/"),
                        "max_v": version,
                        "original_name": f_no_ext[:match.start()] if match else f_no_ext
                    }

    best_proj = None
    exact_match_data = None
    script_v = 0

    try:
        script_path = nuke.scriptName().replace("\\", "/").lower()
        if script_path and script_path != "root":
            script_parts = script_path.split("/")
            script_file = script_parts[-1]

            match = re.search(r'_v(\d+)\.nk$', script_file, re.IGNORECASE)
            if match:
                script_base_name = script_file[:match.start()].lower()
                script_v = int(match.group(1))
            else:
                script_base_name = script_file.replace(".nk", "").lower()

            if script_base_name in fast_track_db:
                exact_match_data = fast_track_db[script_base_name]

            for proj_display, proj_raw in project_raw_map.items():
                proj_lower = proj_raw.lower()

                if proj_lower in script_parts:
                    best_proj = proj_display
                    break
                elif exact_match_data and proj_raw in exact_match_data["folder_path"]:
                    best_proj = proj_display
                    break
                elif proj_lower in script_path:
                    best_proj = proj_display
                    break
    except RuntimeError:
        pass
    except Exception:
        pass

    if exact_match_data:
        db_max_v = exact_match_data["max_v"]
        orig_name = exact_match_data["original_name"]
        folder_path = exact_match_data["folder_path"]

        next_v = max(script_v, db_max_v + 1)

        msg = QtWidgets.QMessageBox()
        msg.setWindowTitle("Template Match Found")

        if script_v > db_max_v:
            msg.setText("Your script is a newer version of the '{0}' template.\n\nDatabase: v{1:02d}\nYour Script: v{2:02d}".format(orig_name, db_max_v, script_v))
            msg.addButton("Save as v{0:02d}".format(script_v), QtWidgets.QMessageBox.AcceptRole)
            btn_overwrite = None
        else:
            msg.setText("The template '{0}' already exists in the database at v{1:02d}.".format(orig_name, db_max_v))
            msg.addButton("Version Up (v{0:02d})".format(next_v), QtWidgets.QMessageBox.AcceptRole)
            btn_overwrite = msg.addButton("Overwrite v{0:02d}".format(db_max_v), QtWidgets.QMessageBox.DestructiveRole)

        btn_menu = msg.addButton("Open Full Menu", QtWidgets.QMessageBox.ActionRole)
        btn_cancel = msg.addButton("Cancel", QtWidgets.QMessageBox.RejectRole)

        msg.setWindowFlags(msg.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        msg.exec_()

        clicked = msg.clickedButton()

        if clicked == btn_cancel:
            return

        elif clicked != btn_menu:
            if btn_overwrite and clicked == btn_overwrite:
                final_file = os.path.join(folder_path, "{0}_v{1:02d}.nk".format(orig_name, db_max_v)).replace("\\", "/")
            else:
                target_v = script_v if script_v > db_max_v else next_v
                final_file = os.path.join(folder_path, "{0}_v{1:02d}.nk".format(orig_name, target_v)).replace("\\", "/")

            nuke.nodeCopy(final_file)
            if template_context:
                root_lines = [
                    "Root {",
                    f' fps {template_context["fps"]}',
                    f' format "{template_context["w"]} {template_context["h"]}"'
                ]

                if template_context["cm"]:
                    root_lines.append(f' colorManagement {template_context["cm"]}')
                if template_context["ocio"]:
                    root_lines.append(f' OCIO_config {template_context["ocio"]}')
                    
                root_lines.append("}\n")
                root_string = "\n".join(root_lines)
                
                try:
                    target_file = final_file 
                    
                    with open(target_file, 'r') as f:
                        original_script = f.read()
                    
                    with open(target_file, 'w') as f:
                        f.write(root_string + original_script)
                except Exception as e:
                    print("Failed to inject Root block:", e)
            nuke.message("Template Fast-Saved successfully as:\n" + os.path.basename(final_file))
            return

    from .ui import SaveTemplateDialog
    dialog = SaveTemplateDialog(projects_dict, project_raw_map, best_proj, default_root)

    if dialog.exec_():
        base_name, folder_path, do_version = dialog.get_save_data()

        if not base_name:
            nuke.message("Template Name cannot be empty.")
            return

        final_file_path = saves.get_save_path(folder_path, base_name, auto_version=do_version)

        if not do_version and os.path.exists(final_file_path):
            warning_msg = "A template named '{0}' already exists.\n\nOverwrite it?".format(os.path.basename(final_file_path))
            if not nuke.ask(warning_msg):
                return

        os.makedirs(folder_path, exist_ok=True)

        read_nodes = [n for n in selected_nodes if n.Class() == "Read"]
        nodes_to_convert = []

        if read_nodes:
            from .ui import PlaceholderDialog, get_nuke_main_window
            nuke_win = get_nuke_main_window()
            ph_dialog = PlaceholderDialog(read_nodes, parent=nuke_win)

            if ph_dialog.exec_():
                nodes_to_convert = ph_dialog.get_nodes_to_convert()
            else:
                return

        try:
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
            if template_context:
                root_lines = [
                    "Root {",
                    f' fps {template_context["fps"]}',
                    f' format "{template_context["w"]} {template_context["h"]}"'
                ]
                
                if template_context["cm"]:
                    root_lines.append(f' colorManagement {template_context["cm"]}')
                if template_context["ocio"]:
                    root_lines.append(f' OCIO_config {template_context["ocio"]}')
                    
                root_lines.append("}\n")
                root_string = "\n".join(root_lines)
                
                try:
                    target_file = final_file_path 
                    
                    with open(target_file, 'r') as f:
                        original_script = f.read()
                    
                    with open(target_file, 'w') as f:
                        f.write(root_string + original_script)
                except Exception as e:
                    print("Failed to inject Root block:", e)
            nuke.message("Template saved successfully as:\n" + os.path.basename(final_file_path))

        finally:
            if nodes_to_convert:
                nuke.Undo().undo()


def launch_rules_editor() -> None:
    """Open the auto-tag rules editor as a modal dialog.

    Instantiates :class:`ui.AutoTagRulesDialog` parented to Nuke's
    main window (located via :func:`ui.get_nuke_main_window`) so the
    dialog floats correctly above the application rather than the
    desktop. The dialog reads its initial rule set from disk via
    :func:`saves.load_auto_tag_rules` and writes any changes back via
    :func:`saves.save_auto_tag_rules` when the user clicks Save.

    The function blocks until the dialog is dismissed. Rule changes
    take effect on the next scan; templates already loaded in an open
    Template Manager window are unaffected until the user re-runs
    the Re-Evaluate Auto-Tags context-menu action.
    """
    from .ui import AutoTagRulesDialog, get_nuke_main_window

    nuke_window = get_nuke_main_window()
    dialog = AutoTagRulesDialog(parent=nuke_window)
    dialog.exec_()