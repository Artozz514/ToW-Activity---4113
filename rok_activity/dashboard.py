"""Génère output/dashboard.html : un fichier HTML autonome (aucune dépendance externe),
consultable hors-ligne ou hébergeable tel quel (GitHub Pages, Netlify, Google Drive…)."""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

import pandas as pd

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "dashboard.html"


def _clean(v):
    if v is None or v is pd.NaT:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, (pd.Timestamp, dt.date)):
        return v.strftime("%Y-%m-%d")
    if hasattr(v, "item"):  # numpy scalars
        return _clean(v.item())
    if v is pd.NA:
        return None
    return v


def _records(df: pd.DataFrame, cols: list[str]) -> list[list]:
    return [[_clean(v) for v in row] for row in df[cols].itertuples(index=False, name=None)]


def build_payload(hist: pd.DataFrame, summary: pd.DataFrame, cfg: dict, log: list[str]) -> dict:
    """Arrivées/départs sont recalculés dans la page (par ID) pour n'importe quelle semaine."""
    kpis = cfg["kpis"]
    kpi_meta = []
    for key, spec in kpis.items():
        obj = spec.get("objectif", 0) or 0
        kpi_meta.append({
            "key": key, "libelle": spec["libelle"],
            "objectif": obj if not isinstance(obj, dict) else obj,
            "evalue": f"{key}_ok" in hist.columns,
            "poids": float(spec.get("poids", 0) or 0),
        })
    member_cols = ["semaine", "governor_id", "pseudo", "rang", "statut", "raisons", "score",
                   "kpis_manques", "semaines_consecutives_ko", "jours_sans_connexion", "nouveau",
                   "puissance", "puissance_evol", "kills_evol", "note", "anciens_pseudos", "action"]
    for key in kpis:
        member_cols += [f"{key}_semaine", f"{key}_objectif"]
    member_cols = [c for c in member_cols if c in hist.columns]
    summary_cols = list(summary.columns)
    return {
        "meta": {
            "alliance": cfg.get("alliance", ""),
            "royaume": cfg.get("royaume", ""),
            "genere_le": dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "kpis": kpi_meta,
            "regles": cfg["regles"],
            "journal": log,
        },
        "membres": {"cols": member_cols, "rows": _records(hist, member_cols)},
        "semaines": {"cols": summary_cols, "rows": _records(summary, summary_cols)},
    }


def write_dashboard(payload: dict, out: Path) -> Path:
    html = TEMPLATE.read_text(encoding="utf-8")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("/*__DATA__*/null", data)
    out.write_text(html, encoding="utf-8")
    return out
