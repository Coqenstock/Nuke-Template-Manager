# Nuke Template Manager
[![Documentation Status](https://readthedocs.org/projects/nuke-template-manager/badge/?version=latest)](https://nuke-template-manager.readthedocs.io/en/latest/)

A template manager for Nuke that organizes scripts using folders and tags. It automatically detects and warns you if any required nodes or plugins are missing before importing a template.

## Installation

1. Download or clone this repository.
2. Inside the downloaded folder, locate the `Template_Manager` directory.
3. Copy the `Template_Manager` directory directly into your `~/.nuke/` folder.
4. Add the following single line to your `~/.nuke/menu.py` file to load the tool and create the UI shortcut (`Ctrl+T`):

```python
import Template_Manager

nuke.menu("Nuke").addMenu("Pipeline Tools").addCommand("Template Manager", launch_ui, "ctrl+t")
```
## Documentation

This tool includes a fully searchable, automated Sphinx manual detailing the core logic, classes, and parsing algorithms.

**[Click here to read the official documentation](https://nuke-template-manager.readthedocs.io/)**