"""Blacklist du royaume : data/kingdom/blacklist.csv (versionné).

Colonnes : governor_id, nom, power, vu_le, anciens_noms, raison, date_ajout.
Pour ajouter quelqu'un : une ligne avec governor_id, raison et date_ajout (le reste se remplit seul).

À chaque exécution, le fichier est complété à partir de TOUS les exports disponibles
(data/kingdom/raw, y compris les fichiers remplacés, et data/kingdom/analytics) :
  - nom / power / vu_le : dernier pseudo et dernier power connus, avec leur date ;
  - anciens_noms : tous les autres pseudos vus pour ce Governor ID (séparés par « | »).
Les anciens noms ne sont jamais retirés : même si les exports d'origine disparaissent,
ils restent dans le CSV.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

SEP = " | "
COLS = ["governor_id", "nom", "power", "vu_le", "anciens_noms", "raison", "date_ajout"]


def _sightings(root: Path, cfg: dict) -> pd.DataFrame:
    """(id, nom, power, date) pour chaque gouverneur de chaque export lisible."""
    c = cfg["colonnes"]
    out = []
    for p in sorted((root / cfg["dossiers"]["exports"]).rglob("*.csv")):
        if p.stat().st_size == 0:
            continue
        try:
            d = pd.read_csv(p, encoding="utf-8-sig")
        except pd.errors.EmptyDataError:
            continue
        date = pd.to_datetime(d.get(c["date_fin"]), errors="coerce", utc=True)
        out.append(pd.DataFrame({"id": d[c["id"]], "nom": d[c["pseudo"]], "power": d[c["power"]], "date": date}))
    for p in sorted((root / "data/kingdom/analytics").glob("*.xlsx")):
        m = re.search(r"(\d{8})_(\d{6})", p.name)
        date = pd.to_datetime(m.group(1) + m.group(2), format="%Y%m%d%H%M%S", utc=True) if m else pd.NaT
        d = pd.read_excel(p)
        out.append(pd.DataFrame({"id": d["Player ID"], "nom": d["Player Name"], "power": d["Power"], "date": date}))
    s = pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["id", "nom", "power", "date"])
    s["id"] = pd.to_numeric(s["id"], errors="coerce")
    s = s.dropna(subset=["id", "nom"])
    s["id"] = s["id"].astype("int64")
    s["nom"] = s["nom"].astype(str).str.strip()
    return s.sort_values("date", kind="stable")


def update_blacklist(path: Path, root: Path, cfg: dict, log: list[str]) -> list[dict]:
    if not path.exists():
        log.append(f"{path.name} not found: empty blacklist.")
        return []
    bl = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    for col in COLS:
        if col not in bl:
            bl[col] = ""
    seen = _sightings(root, cfg)
    for i, r in bl.iterrows():
        gid = int(r.governor_id)
        s = seen[seen["id"] == gid]
        names = [n for n in r.anciens_noms.split(SEP) if n] + ([r.nom] if r.nom else [])
        if len(s):
            last = s.iloc[-1]
            names += list(dict.fromkeys(s["nom"]))
            bl.at[i, "nom"] = last["nom"]
            bl.at[i, "power"] = str(int(last["power"]))
            bl.at[i, "vu_le"] = last["date"].strftime("%Y-%m-%d") if pd.notna(last["date"]) else r.vu_le
        else:
            log.append(f"Blacklist: governor {gid} not found in any export (kept as entered).")
        cur = bl.at[i, "nom"]
        bl.at[i, "anciens_noms"] = SEP.join(n for n in dict.fromkeys(names) if n != cur)
    bl[COLS].to_csv(path, index=False, encoding="utf-8-sig")
    return [{"id": int(r.governor_id), "nom": r.nom, "power": int(r.power) if r.power else None, "vu_le": r.vu_le,
             "anciens_noms": [n for n in r.anciens_noms.split(SEP) if n], "raison": r.raison, "date_ajout": r.date_ajout}
            for r in bl.itertuples()]
