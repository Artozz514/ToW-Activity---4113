"""Calculs : roster, évolutions, objectifs, score, statut et flags.

Le score « objectif » remplace les 3 scores du fichier legacy (Activity / Weighted /
Flattened) qui étaient relatifs au meilleur joueur de la semaine. Ici chaque KPI
vaut  min(valeur / objectif, plafond)  -> 100 = objectif pile atteint, quelle que
soit la semaine. On peut donc comparer les semaines entre elles.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROSTER_COLS = ["governor_id", "pseudo", "rang", "exempte_jusqu_au", "note"]
# Statuts affichés tels quels dans le dashboard (anglais : alliance internationale)
OK, SURVEILLER, ALERTE, EXEMPTE, NOUVEAU = "OK", "Watch", "Alert", "Exempt", "New"
STATUS_KEY = {OK: "ok", SURVEILLER: "watch", ALERTE: "alert", EXEMPTE: "exempt", NOUVEAU: "new"}
NON_EVALUES = (EXEMPTE, NOUVEAU)  # jamais flaggés, exclus des % d'objectifs


# ---------------------------------------------------------------- roster
def sync_roster(df: pd.DataFrame, path: Path, log: list[str]) -> pd.DataFrame:
    """Charge roster.csv et y ajoute automatiquement les nouveaux IDs (rang à compléter)."""
    if path.exists():
        roster = pd.read_csv(path, dtype={"rang": str, "note": str, "exempte_jusqu_au": str}, encoding="utf-8-sig")
    else:
        roster = pd.DataFrame(columns=ROSTER_COLS)
    roster["governor_id"] = pd.to_numeric(roster["governor_id"], errors="coerce").astype("Int64")

    latest = df.sort_values("semaine").drop_duplicates("governor_id", keep="last")
    # seuls les membres du dernier export entrent au roster (pas les anciens du legacy,
    # ni les ID techniques négatifs des joueurs legacy sans Governor ID)
    current = latest[(latest["semaine"] == df["semaine"].max()) & (latest["governor_id"] > 0)]
    new = current[~current["governor_id"].isin(roster["governor_id"])]
    if len(new):
        add = pd.DataFrame({"governor_id": new["governor_id"], "pseudo": new["pseudo"],
                            "rang": "", "exempte_jusqu_au": "", "note": "new member — rank to fill in"})
        roster = pd.concat([roster, add], ignore_index=True)
        log.append(f"Roster: {len(new)} new member(s) added to roster.csv (rank to fill in).")
    # le pseudo du roster suit le pseudo le plus récent du jeu
    names = latest.set_index("governor_id")["pseudo"]
    roster["pseudo"] = roster["governor_id"].map(names).fillna(roster["pseudo"])
    roster[ROSTER_COLS].to_csv(path, index=False, encoding="utf-8-sig")

    sans_rang = roster["rang"].fillna("").str.strip().eq("").sum()
    if sans_rang:
        log.append(f"Roster: {sans_rang} member(s) without a rank in roster.csv.")
    return roster


# ---------------------------------------------------------------- helpers
def _target(spec: dict, rang: pd.Series) -> pd.Series:
    obj = spec.get("objectif", 0) or 0
    if isinstance(obj, dict):
        default = obj.get("defaut", 0)
        return rang.map(lambda r: obj.get(r, default)).astype(float)
    return pd.Series(float(obj), index=rang.index)


def _weekly_value(df: pd.DataFrame, key: str, mode: str) -> pd.Series:
    """Valeur de la semaine : brute (hebdo) ou différence avec la semaine précédente (cumul).
    En mode cumul, pas de différence s'il manque la semaine juste avant (trou dans l'historique)."""
    if mode == "cumul":
        return df.groupby("governor_id")[key].diff().where(df["suite"])
    return pd.to_numeric(df[key], errors="coerce").astype(float)


# ---------------------------------------------------------------- main
def compute(df: pd.DataFrame, roster: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    rules = cfg["regles"]
    kpis = cfg["kpis"]
    df = df.sort_values(["governor_id", "semaine"]).reset_index(drop=True)

    df = df.merge(roster[["governor_id", "rang", "exempte_jusqu_au", "note"]], on="governor_id", how="left")
    # rang : roster d'abord, sinon celui noté dans le fichier (semaines legacy), sinon « ? »
    rang_export = df["rang_export"].astype("string").fillna("") if "rang_export" in df else ""
    df["rang"] = df["rang"].fillna("").str.strip().replace("", np.nan).fillna(rang_export).replace("", "?")

    # semaine précédente du membre et de l'alliance : on ne relie deux semaines que si elles se suivent
    une_semaine = pd.Timedelta(days=7)
    df["suite"] = (df["semaine"] - df.groupby("governor_id")["semaine"].shift()) == une_semaine
    weeks = sorted(df["semaine"].unique())
    prev_alliance = {w: p for p, w in zip(weeks, weeks[1:])}
    df["semaine_prec_alliance"] = df["semaine"].map(prev_alliance)

    # contexte : valeur + évolution
    for key, spec in cfg.get("contexte", {}).items():
        df[key] = pd.to_numeric(df[key], errors="coerce")
        if spec.get("mode") == "cumul":
            df[f"{key}_evol"] = df.groupby("governor_id")[key].diff().where(df["suite"])

    # KPI évalués
    evaluated, weights = [], {}
    df["kpis_manques"] = 0
    df["kpis_manques_liste"] = [[] for _ in range(len(df))]
    for key, spec in kpis.items():
        df[f"{key}_semaine"] = _weekly_value(df, key, spec.get("mode", "hebdo"))
        tgt = _target(spec, df["rang"])
        df[f"{key}_objectif"] = tgt
        if (tgt > 0).any():
            evaluated.append(key)
            weights[key] = float(spec.get("poids", 1))
            ratio = (df[f"{key}_semaine"] / tgt.replace(0, np.nan)).clip(upper=rules["plafond_score"])
            df[f"{key}_ratio"] = ratio
            missed = (tgt > 0) & (df[f"{key}_semaine"].fillna(0) < tgt)
            df[f"{key}_ok"] = ~missed
            df["kpis_manques"] += missed.astype(int)
            for i in np.flatnonzero(missed.to_numpy()):
                df.at[i, "kpis_manques_liste"].append(spec["libelle"])

    # score objectif pondéré (100 = tous les objectifs pile atteints)
    if evaluated:
        wsum = sum(weights.values())
        df["score"] = sum(df[f"{k}_ratio"].fillna(0) * weights[k] for k in evaluated) / wsum * 100
    else:
        df["score"] = np.nan
    df["score"] = df["score"].round(1)

    # inactivité (référence = connexion la plus récente du fichier, insensible au fuseau horaire)
    ref = df.groupby("semaine")["derniere_connexion"].transform("max")
    df["jours_sans_connexion"] = ((ref - df["derniere_connexion"]).dt.total_seconds() / 86400).round(1)

    # arrivée en cours de semaine : l'ID n'était pas là la semaine d'avant, ET la semaine
    # d'avant est bien suivie (sinon on ne sait pas quand il est arrivé). Cette semaine ne compte pas.
    df["nouveau"] = df.groupby("governor_id").cumcount() == 0
    alliance_suivie = (df["semaine"] - df["semaine_prec_alliance"]) == une_semaine
    df["arrive_cette_semaine"] = (
        bool(rules.get("pas_de_flag_semaine_arrivee", True)) & alliance_suivie & ~df["suite"]
    )

    # semaines consécutives avec au moins un KPI raté (strikes calculés, plus de saisie manuelle)
    fail = (df["kpis_manques"] > 0) & ~df["arrive_cette_semaine"]
    streak = np.zeros(len(df), dtype=int)
    prev_id, run = None, 0
    for i, (gid, f, suite) in enumerate(zip(df["governor_id"], fail, df["suite"])):
        run = (run + 1 if f else 0) if (gid == prev_id and suite) else (1 if f else 0)
        streak[i], prev_id = run, gid
    df["semaines_consecutives_ko"] = streak

    # baisse forte vs moyenne des 4 semaines précédentes
    # (uniquement sur des semaines consécutives : un trou dans l'historique redémarre la moyenne)
    segment = (~df["suite"]).groupby(df["governor_id"]).cumsum()
    prev_mean = df.groupby([df["governor_id"], segment])["score"].transform(
        lambda s: s.shift(1).rolling(4, min_periods=1).mean())
    df["score_moy_4s"] = prev_mean.round(1)
    df["baisse_forte"] = prev_mean.notna() & (prev_mean > 0) & (df["score"] < prev_mean * (1 - rules["baisse_forte_pct"] / 100))

    # exemptions
    exempt_until = pd.to_datetime(df["exempte_jusqu_au"], errors="coerce", dayfirst=True)
    df["exempte"] = df["rang"].isin(rules.get("rangs_exemptes", [])) | (exempt_until.notna() & (exempt_until >= df["semaine"]))

    # statut + raisons
    statuts, raisons = [], []
    for r in df.itertuples(index=False):
        why = []
        if r.jours_sans_connexion is not None and r.jours_sans_connexion > rules["inactivite_jours"]:
            why.append(f"Inactive for {r.jours_sans_connexion:.0f} days")
        if r.kpis_manques:
            why.append("Below target: " + ", ".join(r.kpis_manques_liste))
        if r.semaines_consecutives_ko >= 2:
            why.append(f"{r.semaines_consecutives_ko} weeks in a row below target")
        if r.baisse_forte:
            why.append(f"Sharp score drop ({r.score:.0f} vs 4-week avg {r.score_moy_4s:.0f})")
        alerte = (
            (r.jours_sans_connexion or 0) > rules["inactivite_jours"]
            or r.kpis_manques >= rules["alerte_si_kpis_manques"]
            or r.semaines_consecutives_ko >= rules["alerte_si_semaines_consecutives"]
        )
        if r.arrive_cette_semaine:
            statuts.append(NOUVEAU)
            why = ["Joined during the week — no flags until their first full week"]
        elif r.exempte:
            statuts.append(EXEMPTE)
        elif alerte:
            statuts.append(ALERTE)
        elif why:
            statuts.append(SURVEILLER)
        else:
            statuts.append(OK)
        raisons.append(" · ".join(why))
    df["statut"] = statuts
    df["raisons"] = raisons

    # anciens pseudos : l'ID est la seule clé, le pseudo n'est qu'un libellé qui peut changer
    anciens = []
    seen: dict = {}
    for gid, name in zip(df["governor_id"], df["pseudo"]):
        prev = seen.setdefault(gid, [])
        anciens.append(" / ".join(n for n in prev if n != name))
        if name not in prev:
            prev.append(name)
    df["anciens_pseudos"] = anciens
    return df.drop(columns=["kpis_manques_liste"])


def alliance_summary(hist: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Une ligne par semaine : effectif, totaux, médianes, % objectifs, répartition des statuts."""
    rows = []
    weeks = sorted(hist["semaine"].unique())
    prev_ids: set = set()
    prev_wk = None
    for wk in weeks:
        w = hist[hist["semaine"] == wk]
        ids = set(w["governor_id"])
        export_le = pd.Timestamp(w["horodatage_export"].iloc[0])
        consecutive = prev_wk is not None and (pd.Timestamp(wk) - pd.Timestamp(prev_wk)) == pd.Timedelta(days=7)
        row = {"semaine": pd.Timestamp(wk), "membres": len(w),
               "export_le": export_le,
               "semaine_partielle": bool(export_le.normalize() < pd.Timestamp(wk)),
               "source": w["source"].iloc[0] if "source" in w else "export",
               "semaine_precedente": pd.Timestamp(prev_wk) if prev_wk is not None else pd.NaT,
               "sans_governor_id": int((w["governor_id"] < 0).sum()),
               # comparés par ID, uniquement si la semaine juste avant (J-7) est suivie ; sinon vide
               "arrivees": len(ids - prev_ids) if consecutive else np.nan,
               "departs": len(prev_ids - ids) if consecutive else np.nan}
        evaluables = w[~w["statut"].isin(NON_EVALUES)]
        for key in cfg["kpis"]:
            row[f"{key}_total"] = w[f"{key}_semaine"].sum()
            row[f"{key}_mediane"] = w[f"{key}_semaine"].median()
            if f"{key}_ok" in w:
                row[f"{key}_pct_ok"] = round(100 * evaluables[f"{key}_ok"].mean(), 1) if len(evaluables) else np.nan
        row["puissance_totale"] = w["puissance"].sum() if "puissance" in w else np.nan
        row["pct_tous_objectifs"] = round(100 * (evaluables["kpis_manques"] == 0).mean(), 1) if len(evaluables) else np.nan
        row["score_median"] = w["score"].median()
        for s in (OK, SURVEILLER, ALERTE, EXEMPTE, NOUVEAU):
            row[f"n_{STATUS_KEY[s]}"] = int((w["statut"] == s).sum())
        rows.append(row)
        prev_ids, prev_wk = ids, wk
    return pd.DataFrame(rows)


def renames(hist: pd.DataFrame) -> list[str]:
    """Changements de pseudo détectés pendant la dernière semaine (même ID, autre nom)."""
    weeks = sorted(hist["semaine"].unique())
    if len(weeks) < 2:
        return []
    if pd.Timestamp(weeks[-1]) - pd.Timestamp(weeks[-2]) != pd.Timedelta(days=7):
        return []
    prev = hist[hist["semaine"] == weeks[-2]].set_index("governor_id")["pseudo"]
    last = hist[hist["semaine"] == weeks[-1]].set_index("governor_id")["pseudo"]
    both = prev.index.intersection(last.index)
    return [f"Renamed: {prev[g]} → {last[g]} (ID {g})" for g in both if prev[g] != last[g]]


def movements(hist: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(départs, arrivées) entre l'avant-dernière et la dernière semaine, comparés par ID."""
    cols = ["governor_id", "pseudo", "rang", "puissance"]
    weeks = sorted(hist["semaine"].unique())
    if len(weeks) < 2:
        return hist.iloc[0:0][cols], hist.iloc[0:0][cols]
    last, prev = weeks[-1], weeks[-2]
    if pd.Timestamp(last) - pd.Timestamp(prev) != pd.Timedelta(days=7):  # semaine d'avant non suivie
        return hist.iloc[0:0][cols], hist.iloc[0:0][cols]
    ids_prev = set(hist.loc[hist["semaine"] == prev, "governor_id"])
    ids_last = set(hist.loc[hist["semaine"] == last, "governor_id"])
    gone = hist[(hist["semaine"] == prev) & hist["governor_id"].isin(ids_prev - ids_last)][cols]
    new = hist[(hist["semaine"] == last) & hist["governor_id"].isin(ids_last - ids_prev)][cols]
    return gone, new
