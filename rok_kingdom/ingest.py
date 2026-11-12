"""Lecture des exports hebdomadaires du royaume déposés dans data/kingdom/raw.

Règles :
- un fichier = une semaine de jeu (lundi → dimanche) ;
- la semaine est lue DANS le fichier (dates « From Date » des gouverneurs), pas dans
  son nom : on peut ainsi déposer d'un coup tout un historique exporté le même jour ;
  à défaut de dates, on prend celle du nom (…_AAAAMMJJ_HHMMSS.csv) ;
- une semaine dont le suivi s'arrête avant le dimanche est marquée « en cours » ;
- plusieurs fichiers pour la même semaine : on garde celui qui couvre le plus loin
  (puis le plus récemment exporté) ; les autres sont ignorés ;
- « instantané » : un fichier qui ne couvre que quelques jours (< 4) — le snapshot du
  dernier jour fourni chaque fin de semaine. C'est la liste de référence du royaume :
  un gouverneur absent du snapshot est parti (pas de report, voir analyse.carry_forward) ;
- les fichiers vides sont ignorés (signalés dans le journal).
Les fichiers bruts ne sont jamais modifiés ; tout est recalculé à chaque exécution.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from rok_activity.ingest import snapshot_time, week_end

REQUIRED = ["id", "pseudo", "power", "kp"]
SNAPSHOT_MAX_DAYS = 4   # fenêtre de suivi en dessous de laquelle un fichier est un « instantané »
NUMERIC = ["ch", "power", "kp", "t4_kills", "t5_kills", "periode_minutes",
           "power_change", "kp_change", "t4_change", "t5_change"]


def _read(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig")
    return pd.read_excel(path, sheet_name=0)


def _dates(df: pd.DataFrame, col: str | None) -> pd.Series:
    if not col or col not in df.columns:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(df[col], errors="coerce", utc=True).dt.tz_localize(None).dropna()


def _period(df: pd.DataFrame, cols: dict, path: Path) -> tuple:
    """(dimanche de la semaine, début du suivi, fin du suivi) d'après le contenu du fichier."""
    debut, fin = _dates(df, cols.get("date_debut")), _dates(df, cols.get("date_fin"))
    if len(debut):
        ref = debut.median()
        return week_end(ref.date()), debut.min(), (fin.max() if len(fin) else debut.max())
    ts = snapshot_time(path)
    return week_end(ts.date()), None, pd.Timestamp(ts)


def load_snapshots(cfg: dict, root: Path) -> tuple[pd.DataFrame, list[str]]:
    """Retourne (données longues : 1 ligne = gouverneur × semaine, journal)."""
    raw_dir = root / cfg["dossiers"]["exports"]
    log: list[str] = []
    files = sorted(p for p in raw_dir.rglob("*")
                   if p.suffix.lower() in (".csv", ".xlsx") and not p.name.startswith("~$"))
    if not files:
        raise SystemExit(f"Aucun export trouvé dans {raw_dir}. Déposez le CSV de la semaine puis relancez.")

    cols = cfg["colonnes"]
    per_week: dict = {}
    for p in files:
        if p.stat().st_size == 0:
            log.append(f"{p.name}: empty file, ignored (re-export it).")
            continue
        try:
            df = _read(p)
        except pd.errors.EmptyDataError:
            log.append(f"{p.name}: empty file, ignored (re-export it).")
            continue
        if df.empty:
            log.append(f"{p.name}: no rows, ignored.")
            continue
        wk, debut, fin = _period(df, cols, p)
        per_week.setdefault(wk, []).append(((fin, snapshot_time(p)), p, df, debut, fin))

    frames = []
    for wk, items in sorted(per_week.items()):
        items.sort(key=lambda x: x[0])            # le fichier qui couvre le plus loin en dernier
        _, last, df, debut, fin = items[-1]
        out = _normalise(df, cols, last, log)
        for _, p, *_ in items[:-1]:
            log.append(f"Week ending {wk}: {p.name} skipped (superseded by {last.name}).")
        instantane = debut is not None and (fin - debut) < pd.Timedelta(days=SNAPSHOT_MAX_DAYS)
        partielle = fin is not None and fin.date() < wk
        out.insert(0, "semaine", pd.Timestamp(wk))
        out.insert(1, "suivi_debut", debut)
        out.insert(2, "suivi_fin", fin)
        out.insert(3, "semaine_partielle", partielle)
        out.insert(4, "instantane", instantane)
        out.insert(5, "fichier", last.name)
        frames.append(out)
        log.append(f"Week ending {wk}: {last.name} ({len(out)} governors"
                   f"{', snapshot' if instantane else ''}{', week in progress' if partielle else ''}).")
    if not frames:
        raise SystemExit("Aucun export exploitable (fichiers vides ?).")
    return pd.concat(frames, ignore_index=True), log


def _normalise(df: pd.DataFrame, cols: dict, p: Path, log: list[str]) -> pd.DataFrame:
    missing = [cols[k] for k in REQUIRED if cols[k] not in df.columns]
    if missing:
        raise SystemExit(f"{p.name} : colonnes introuvables {missing}. Vérifiez l'export ou config_kingdom.yaml.")
    keys = [k for k in cols if k not in ("date_debut", "date_fin")]
    out = pd.DataFrame({k: df[cols[k]] if cols[k] in df.columns else pd.NA for k in keys})
    for k in NUMERIC:
        out[k] = pd.to_numeric(out[k], errors="coerce")
    out["id"] = pd.to_numeric(out["id"], errors="coerce")
    n0 = len(out)
    out = out.dropna(subset=["id", "power"])
    if len(out) < n0:
        log.append(f"{p.name}: {n0 - len(out)} row(s) without governor ID or power ignored.")
    out["id"] = out["id"].astype("int64")
    if out["id"].duplicated().any():
        log.append(f"{p.name}: duplicated governor IDs, highest-power row kept.")
        out = out.sort_values("power", ascending=False).drop_duplicates("id")
    out["pseudo"] = out["pseudo"].astype(str).str.strip()
    return out
