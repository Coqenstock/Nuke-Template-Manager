import re
import os
NODE_FINDER = re.compile(r'^(\s*)([A-Z][A-Za-z0-9_]*)\s*\{', re.MULTILINE)
def list_nk_files(folder_path):
    if not os.path.isdir(folder_path):
        return []
    else:
        NK_FILES = [ 
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if f.lower().endswith(".nk")
        ]
        return NK_FILES
IGNORED_WORDS = {"Root"} #Variable qui contient le mot root
ERRORS = [] #Liste qui contient les erreurs
def scan_templates(folder_path, available_nodes):   
    templates = []
    for path in list_nk_files(folder_path): #Pour tous les éléments de NK_FILES
        filename = os.path.basename(path) #nom de fichier.nk
        display_name = os.path.splitext(filename)[0] #nom de fichier sans le .nk
        tpl = {"name": display_name, "path": path, "missing_nodes": [], "errors":None, "status": None} #dans la liste y a le nom le chemin d'accès, si il y a des noeuds qui manquent ou si y a des erreurs genre si ça crash
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f: #ouvrir fichier puis fermer quand c'est fini
                text = f.read() #lire le texte
            found_pairs = NODE_FINDER.findall(text)
            found = [name for indent, name in found_pairs if indent == ""]#utiliser la fonction regex pour trouver les noms de noeuds
            found_unique = sorted(set([s.strip() for s in found]) - IGNORED_WORDS) #enlever root
            missing = []
            for cls in found_unique:
                if cls in available_nodes:
                    continue
                base = cls
                while base and base[-1].isdigit():
                    base = base[:-1]
                if base in available_nodes:
                    continue
                missing.append(cls)
            tpl["missing_nodes"] = sorted(missing) #ajouter le noeuds manquant dans errors
        except Exception as e:
            tpl["errors"] = f"{type(e).__name__}: {e}" #si ça merde
        if tpl["errors"]:
            tpl["status"] = "READ_ERROR"
        elif tpl["missing_nodes"]:
            tpl["status"] = "MISSING_NODES"
        else:
            tpl["status"] = "OK"
        templates.append(tpl)
    return templates
