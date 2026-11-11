"""Génère output/kingdom/dashboard.html : fichier HTML autonome (aucune dépendance externe).

La page reçoit les photos brutes de chaque semaine et calcule elle-même totaux, WoW,
arrivées/départs et tops, pour pouvoir basculer instantanément entre « tout le royaume »
et la vue Top N.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from rok_activity.dashboard import _clean

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "kingdom.html"
ROW_COLS = ["id", "pseudo", "ch", "power", "kp", "t4_kills", "t5_kills",
            "power_change", "kp_change", "t4_change", "t5_change", "pas_vu"]


def _ts(v) -> str | None:
    return None if v is None or pd.isna(v) else pd.Timestamp(v).strftime("%Y-%m-%d %H:%M")


def build_payload(df: pd.DataFrame, cfg: dict, log: list[str]) -> dict:
    """df : sortie de analyse.carry_forward (colonne pas_vu)."""
    weeks, data = [], {}
    for wk, g in df.groupby("semaine", sort=True):
        key = wk.strftime("%Y-%m-%d")
        g = g.sort_values("power", ascending=False).assign(pas_vu=lambda x: x["pas_vu"].astype(int))
        per = pd.to_numeric(g["periode_minutes"], errors="coerce")
        weeks.append({
            "semaine": key,
            "suivi_debut": _ts(g["suivi_debut"].iloc[0]),
            "suivi_fin": _ts(g["suivi_fin"].iloc[0]),
            "partielle": bool(g["semaine_partielle"].iloc[0]),
            "fichier": g["fichier"].iloc[0],
            "periode_jours": round(float(per.median()) / 1440, 1) if per.notna().any() else None,
        })
        data[key] = [[_clean(v) for v in row] for row in g[ROW_COLS].itertuples(index=False, name=None)]
    return {
        "meta": {
            "royaume": cfg.get("royaume", ""),
            "top_n": int(cfg.get("top_n", 400)),
            "genere_le": dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
            "journal": log,
        },
        "cols": ROW_COLS,
        "weeks": weeks,
        "data": data,
    }


def write_dashboard(payload: dict, out: Path) -> Path:
    html = TEMPLATE.read_text(encoding="utf-8")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html.replace("/*__DATA__*/null", data), encoding="utf-8")
    return out
