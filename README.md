# Nuke Template Manager
[![Documentation Status](https://readthedocs.org/projects/nuke-template-manager/badge/?version=latest)](https://nuke-template-manager.readthedocs.io/en/latest/)

A template manager for Nuke that organizes scripts using folders and tags. It automatically detects and warns you if any required nodes or plugins are missing before importing a template.

## Installation

1. Download this repository and rename the master folder to `Template_Manager`.
2. Place the `Template_Manager` folder directly into your `~/.nuke/` directory.
3. Add the following code to your `menu.py` file to create the UI shortcut:

```python
import nuke
from Template_Manager.main import launch_ui

nuke.menu("Nuke").addMenu("Pipeline Tools").addCommand("Template Manager", launch_ui, "ctrl+t")
```
## Documentation

This tool includes a fully searchable, automated Sphinx manual detailing the core logic, classes, and parsing algorithms.

**[Click here to read the official documentation](https://nuke-template-manager.readthedocs.io/)**