"""Calculs hebdomadaires du royaume.

Méthode « semaine sur semaine » (WoW) :
- total : somme de la semaine − somme de la semaine précédente (D-7), sur le même
  périmètre (tout le royaume, ou les N plus gros power de CHAQUE semaine en vue Top N).
  Arrivées et départs sont donc inclus dans la variation ;
- par gouverneur : valeur de la semaine − valeur de la semaine précédente (même ID) ;
  un nouvel arrivant n'a pas de WoW ;
- 1re semaine suivie (ou semaine précédente manquante) : on retombe sur les deltas
  fournis par l'export (Power Change, Kill Points Change…), signalés comme tels.

Semaine en cours (export pris avant le dimanche) : l'outil ne liste que les gouverneurs
déjà scannés depuis lundi. Ceux de la semaine précédente pas encore revus sont reportés
à leur dernière valeur connue (colonne pas_vu = True) au lieu d'être comptés comme
départs ; les vrais départs ne sont tranchés qu'avec l'export complet du dimanche.

Le dashboard refait les calculs WoW dans la page (pour basculer Tous / Top N) ; ce module
sert au résumé console, au fichier resume_royaume.csv, et de contrôle croisé.
"""
from __future__ import annotations

import pandas as pd

FALLBACK = "export delta"
SNAPSHOT = "week-over-week"


def previous_week(weeks: list, i: int):
    """Semaine juste avant (D-7) ou None : une comparaison sur un trou serait trompeuse."""
    return weeks[i - 1] if i > 0 and (weeks[i] - weeks[i - 1]).days == 7 else None


def carry_forward(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute aux semaines en cours les gouverneurs de D-7 pas encore revus (pas_vu=True)."""
    df = df.assign(pas_vu=False)
    weeks = sorted(df["semaine"].unique())
    extra = []
    for i, wk in enumerate(weeks):
        cur = df[df["semaine"] == wk]
        prev_wk = previous_week(weeks, i)
        if not cur["semaine_partielle"].iloc[0] or prev_wk is None:
            continue
        prev = df[(df["semaine"] == prev_wk) & ~df["id"].isin(cur["id"])].copy()
        keep = {c: cur[c].iloc[0] for c in ("semaine", "suivi_debut", "suivi_fin", "semaine_partielle", "fichier")}
        prev = prev.assign(**keep, pas_vu=True,
                           power_change=pd.NA, kp_change=pd.NA, t4_change=pd.NA, t5_change=pd.NA, periode_minutes=pd.NA)
        extra.append(prev)
    return pd.concat([df, *extra], ignore_index=True) if extra else df


def _universe(week: pd.DataFrame, top_n: int | None) -> pd.DataFrame:
    w = week.sort_values("power", ascending=False)
    return w.head(top_n) if top_n else w


def weekly_summary(df: pd.DataFrame, top_n: int | None = None) -> pd.DataFrame:
    """df doit déjà être passé par carry_forward."""
    weeks = sorted(df["semaine"].unique())
    by_week = {w: df[df["semaine"] == w] for w in weeks}
    rows = []
    for i, wk in enumerate(weeks):
        cur_all = by_week[wk]
        cur = _universe(cur_all, top_n)
        prev_wk = previous_week(weeks, i)
        r = {"semaine": wk, "en_cours": bool(cur_all["semaine_partielle"].iloc[0]),
             "perimetre": f"top {top_n}" if top_n else "kingdom",
             "gouverneurs": len(cur), "pas_encore_vus": int(cur["pas_vu"].sum()),
             "power_total": cur["power"].sum(), "kp_total": cur["kp"].sum()}
        if prev_wk is not None:
            prev_all = by_week[prev_wk]
            prev = _universe(prev_all, top_n)
            r.update(methode=SNAPSHOT,
                     power_wow=r["power_total"] - prev["power"].sum(),
                     kp_wow=r["kp_total"] - prev["kp"].sum(),
                     arrivees=int((~cur["id"].isin(prev_all["id"])).sum()),
                     departs=int((~prev["id"].isin(cur_all["id"])).sum()))
        else:
            r.update(methode=FALLBACK, power_wow=cur["power_change"].sum(), kp_wow=cur["kp_change"].sum(),
                     arrivees=None, departs=None)
        rows.append(r)
    return pd.DataFrame(rows)
