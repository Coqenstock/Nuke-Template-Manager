import re
import os
from typing import TypedDict
NODE_FINDER: re.Pattern[str] = re.compile(r"^(\s*)([A-Z][A-Za-z0-9_\.]*)\s*\{([^\n]*)$", re.MULTILINE)

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
    ofxnames = {x.lower().replace(" ", "") for x in available_nodes} # type: ignore
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
            found_matches: list[tuple[str, str, str]] = NODE_FINDER.findall(text)
            found: list[str] = []
            for indent, name, extra_text in found_matches:
                if indent == "":
                    if extra_text.strip() == "" or name.startswith("OFX"):
                        found.append(name)  # utiliser la fonction regex pour trouver les noms de noeuds
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
                if cls.startswith("OFX"):
                    core_name = cls.split('.')[-1].lower()
                    core_name = core_name.split('_')[0]
                    while core_name and core_name[-1].isdigit():
                        core_name = core_name[:-1]
                    if any(core_name in node for node in ofxnames):
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
