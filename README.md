# Nuke Template Manager
[![Documentation Status](https://readthedocs.org/projects/nuke-template-manager/badge/?version=latest)](https://nuke-template-manager.readthedocs.io/en/latest/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A template manager for Nuke that organizes scripts using folders and tags. It automatically detects and warns you if any required nodes or plugins are missing before importing a template.

## Installation

1. Go to the [Releases Page](https://github.com/Coqenstock/Nuke-Template-Manager/releases/latest) and download the latest **`Nuke_Template_Manager.zip`** file from the Assets section. *(Note: Do not download the raw Source code zip).*
2. Extract the downloaded file and locate the `Template_Manager` directory inside.
3. Copy the `Template_Manager` directory directly into your `~/.nuke/` folder.
4. Add the following code to your `~/.nuke/menu.py` file to load the tool and create the UI shortcut (`Ctrl+T`):

```python
import Template_Manager
```

## User Guide

For detailed instructions on configuring local/studio pipeline paths, tagging, and utilizing the health-check scanner, please read the **[User Guide](USER_GUIDE.md)**.

## Documentation

This tool includes a fully searchable, automated Sphinx manual detailing the core logic, classes, and parsing algorithms.

**[Click here to read the official documentation](https://nuke-template-manager.readthedocs.io/)**