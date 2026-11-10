"""Publication du dashboard sur GitHub Pages.

Copie output/dashboard.html vers docs/index.html (dossier servi par GitHub Pages),
puis enregistre et envoie les changements sur GitHub (git add / commit / push).
Le lien public ne change jamais : https://<compte>.github.io/<dépôt>/

Prérequis (une seule fois) : le dossier est un dépôt git relié à GitHub, et Pages est
activé sur la branche main, dossier /docs (Settings → Pages).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8")


def publish(root: Path, dashboard: Path, cfg: dict, message: str) -> str:
    pub = cfg.get("publication", {}) or {}
    if not pub.get("activer", False):
        return "Publication désactivée (config.yaml → publication.activer)."

    docs = root / pub.get("dossier", "docs")
    docs.mkdir(exist_ok=True)
    shutil.copyfile(dashboard, docs / "index.html")
    (docs / ".nojekyll").touch()  # GitHub sert le fichier tel quel, sans le retraiter

    if shutil.which("git") is None:
        return "git introuvable : dashboard copié dans docs/ mais non envoyé. Installez Git for Windows."
    if _git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        return "Ce dossier n'est pas un dépôt git : dashboard copié dans docs/ mais non envoyé (voir README)."

    _git(root, "add", "-A")
    if _git(root, "diff", "--cached", "--quiet").returncode == 0:
        return "Publication : rien de nouveau à envoyer."
    commit = _git(root, "commit", "-m", message)
    if commit.returncode != 0:
        return f"Publication : échec du commit.\n{commit.stderr.strip()}"
    push = _git(root, "push", "origin", pub.get("branche", "main"))
    if push.returncode != 0:
        return (f"Publication : échec de l'envoi sur GitHub (connexion internet ou identifiants ?).\n"
                f"{push.stderr.strip()}\nRelancez simplement le script une fois le problème réglé.")
    url = pub.get("url")
    return f"Publié sur GitHub. En ligne d'ici 1 à 2 minutes{' : ' + url if url else ''}."
