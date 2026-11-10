"""Lecture des exports hebdomadaires déposés dans data/raw.

Règles :
- un fichier = une photo de l'alliance à un instant donné ;
- la date est lue dans le nom du fichier (…_activity_AAAAMMJJ_HHMMSS.csv/xlsx),
  à défaut la date de modification du fichier ;
- chaque photo est rattachée à la semaine lundi→dimanche qui la contient ;
- si plusieurs fichiers tombent dans la même semaine (ex. le csv ET le xlsx),
  seul le plus récent est gardé.
Les fichiers bruts ne sont jamais modifiés : tout l'historique est recalculé
à chaque exécution, il n'y a donc aucun état à corrompre.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pandas as pd

TS_RE = re.compile(r"(\d{8})_(\d{6})")


def snapshot_time(path: Path) -> dt.datetime:
    m = TS_RE.search(path.name)
    if m:
        return dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    return dt.datetime.fromtimestamp(path.stat().st_mtime)


def week_end(d: dt.date) -> dt.date:
    """La semaine de jeu va du lundi au dimanche : un export appartient à la semaine
    qui le contient (-> dimanche du jour même ou suivant). Un export pris en cours de
    semaine est remplacé par celui du dimanche, plus récent."""
    return d + dt.timedelta(days=6 - d.weekday())  # lundi=0 … dimanche=6


def read_export(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig")
    return pd.read_excel(path, sheet_name=0)


def required_columns(cfg: dict) -> dict[str, str]:
    """Colonnes obligatoires {clé interne: nom dans l'export} : ID, pseudo et KPI évalués."""
    cols = {"governor_id": cfg["colonnes"]["id"], "pseudo": cfg["colonnes"]["pseudo"]}
    for key, spec in cfg.get("kpis", {}).items():
        cols[key] = spec["colonne"]
    return cols


def optional_columns(cfg: dict) -> dict[str, str]:
    """Colonnes facultatives : absentes des semaines importées du legacy (laissées vides)."""
    cols = {"derniere_connexion": cfg["colonnes"]["derniere_connexion"], "rang_export": "Rank"}
    for key, spec in cfg.get("contexte", {}).items():
        cols[key] = spec["colonne"]
    return cols


def load_exports(cfg: dict, root: Path) -> tuple[pd.DataFrame, list[str]]:
    """Retourne (données longues : 1 ligne = membre × semaine, journal)."""
    raw_dir = root / cfg["dossiers"]["exports"]
    log: list[str] = []
    files = sorted(
        p for p in raw_dir.rglob("*")  # inclut data/raw/legacy/
        if p.suffix.lower() in (".csv", ".xlsx") and not p.name.startswith("~$")
    )
    if not files:
        raise SystemExit(f"Aucun export trouvé dans {raw_dir}. Déposez le fichier de la semaine puis relancez.")

    # garder le fichier le plus récent de chaque semaine
    per_week: dict[dt.date, tuple[dt.datetime, Path]] = {}
    for p in files:
        ts = snapshot_time(p)
        wk = week_end(ts.date())
        if wk not in per_week or ts > per_week[wk][0]:
            if wk in per_week:
                log.append(f"Week ending {wk}: {per_week[wk][1].name} skipped (replaced by newer {p.name}).")
            per_week[wk] = (ts, p)
        else:
            log.append(f"Week ending {wk}: {p.name} skipped (older duplicate).")

    cols = required_columns(cfg)
    opt = optional_columns(cfg)
    frames = []
    for wk, (ts, p) in sorted(per_week.items()):
        df = read_export(p)
        missing = [c for c in cols.values() if c not in df.columns]
        if missing:
            raise SystemExit(
                f"{p.name} : colonnes introuvables {missing}.\n"
                f"Le format de l'export a peut-être changé : mettez à jour 'colonne:' dans config.yaml."
            )
        for c in opt.values():
            if c not in df.columns:
                df[c] = pd.NA
        allc = {**cols, **opt}
        df = df[list(allc.values())].rename(columns={v: k for k, v in allc.items()})
        df["governor_id"] = pd.to_numeric(df["governor_id"], errors="coerce").astype("Int64")
        n0 = len(df)
        df = df.dropna(subset=["governor_id"]).drop_duplicates("governor_id", keep="first")
        if len(df) != n0:
            log.append(f"{p.name}: {n0 - len(df)} row(s) without ID or duplicated removed.")
        df["derniere_connexion"] = pd.to_datetime(df["derniere_connexion"], utc=True, errors="coerce")
        for k in opt:
            if k not in ("derniere_connexion", "rang_export"):
                df[k] = pd.to_numeric(df[k], errors="coerce").astype(float)
        df["rang_export"] = df["rang_export"].astype("string")
        df["semaine"] = pd.Timestamp(wk)
        df["fichier"] = p.name
        df["source"] = "legacy" if p.parent.name == "legacy" else "export"
        df["horodatage_export"] = ts
        frames.append(df)
        log.append(f"Week ending {wk:%Y-%m-%d}: {p.name} ({len(df)} members, snapshot {ts:%a %Y-%m-%d %H:%M}).")

    return pd.concat(frames, ignore_index=True), log
