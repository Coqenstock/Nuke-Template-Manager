import re
import os
from typing import TypedDict


def list_nk_files(folder_path: str) -> list[str]:
    return (
        [
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if f.lower().endswith(".nk")
        ]
        if os.path.isdir(folder_path)
        else []
    )


IGNORED_WORDS: set[str] = {"Root"}  # Variable qui contient le mot root

class Template(TypedDict):
    name: str
    path: str
    missing_nodes: list[str]
    errors: str | None
    status: str | None


def scan_templates(
    folder_path: str, available_nodes: set[str], ignored_words: set[str] = IGNORED_WORDS
) -> list[Template]:
    templates: list[Template] = []
    for path in list_nk_files(folder_path):  # Pour tous les éléments de NK_FILES
        filename: str = os.path.basename(path)  # nom de fichier.nk
        display_name: str = os.path.splitext(filename)[0]  # nom de fichier sans le .nk
        tpl: Template = {
            "name": display_name,
            "path": path,
            "missing_nodes": [],
            "errors": None,
            "status": None,
        }  # dans la liste y a le nom le chemin d'accès, si il y a des noeuds qui manquent ou si y a des erreurs genre si ça crash
        try:
            with open(
                path, "r", encoding="utf-8", errors="replace"
            ) as f:  # ouvrir fichier puis fermer quand c'est fini
                text = f.read()  # lire le texte
            NODE_FINDER: re.Pattern[str] = re.compile(r"^(\s*)([A-Z][A-Za-z0-9_]*)\s*\{", re.MULTILINE)
            found_pairs: list[tuple[str, str]] = NODE_FINDER.findall(text)
            found: list[str] = [
                name for indent, name in found_pairs if indent == ""
            ]  # utiliser la fonction regex pour trouver les noms de noeuds
            found_unique: list[str] = sorted(
                set([s.strip() for s in found]) - ignored_words
            )  # enlever root 
            missing: list[str] = []
            for cls in found_unique:
                if cls in available_nodes:
                    continue
                base: str = cls
                while base and base[-1].isdigit():
                    base = base[:-1]
                if base in available_nodes:
                    continue
                missing.append(cls)
            tpl["missing_nodes"] = sorted(
                missing
            )  # ajouter le noeuds manquant dans errors
        except Exception as e:
            tpl["errors"] = f"{type(e).__name__}: {e}"  # si ça merde
        if tpl["errors"]:
            tpl["status"] = "READ_ERROR"
        elif tpl["missing_nodes"]:
            tpl["status"] = "MISSING_NODES"
        else:
            tpl["status"] = "OK"
        templates.append(tpl)
    return templates
