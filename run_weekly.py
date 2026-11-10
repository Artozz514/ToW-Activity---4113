"""Traitement hebdomadaire — à lancer chaque dimanche après avoir déposé l'export.

    python run_weekly.py

1. lit tous les exports de data/raw (un par semaine)
2. met à jour roster.csv (nouveaux membres ajoutés automatiquement)
3. calcule scores, statuts et flags pour chaque semaine
4. écrit dans output/ :
     - dashboard.html          -> le tableau de bord à partager
     - historique.csv          -> base complète (1 ligne = membre × semaine)
     - resume_alliance.csv     -> 1 ligne par semaine
     - report_AAAA-MM-JJ.xlsx  -> la semaine en cours (en anglais), prêt à partager
5. publie le dashboard sur GitHub Pages (docs/index.html), si activé dans config.yaml

    python run_weekly.py --sans-publication   -> tout recalculer sans rien envoyer sur GitHub
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from rok_activity.analyse import ALERTE, SURVEILLER, alliance_summary, compute, leadership_changes, movements, record_ranks, renames, sync_roster
from rok_activity.dashboard import build_payload, write_dashboard
from rok_activity.ingest import load_exports
from rok_activity.publish import publish

ROOT = Path(__file__).resolve().parent


def main(config_path: str = "config.yaml", publier: bool = True) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cfg = yaml.safe_load((ROOT / config_path).read_text(encoding="utf-8"))
    out = ROOT / cfg["dossiers"]["sortie"]
    out.mkdir(exist_ok=True)

    raw, log = load_exports(cfg, ROOT)
    roster = sync_roster(raw, ROOT / cfg["dossiers"]["roster"], log)
    ranks = record_ranks(raw, roster, ROOT / "data" / "rangs_historique.csv", log)
    hist = compute(raw, roster, cfg, ranks)
    r4 = leadership_changes(hist)
    log.extend(f"{c.changement}: {c.pseudo} ({c.rang_avant} → {c.rang}, ID {c.governor_id})" for c in r4.itertuples())
    summary = alliance_summary(hist, cfg)
    gone, arrived = movements(hist)
    log.extend(renames(hist))

    # --- exports fichiers
    hist.to_csv(out / "historique.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(out / "resume_alliance.csv", index=False, encoding="utf-8-sig")

    last = hist["semaine"].max()
    week = hist[hist["semaine"] == last].sort_values("score")
    # rapport Excel en anglais (destiné aux leaders de l'alliance)
    kpi_cols = {f"{k}_semaine": v["libelle"] for k, v in cfg["kpis"].items()}
    report_cols = {"pseudo": "Player", "governor_id": "Governor ID", "rang": "Rank", "statut": "Status",
                   "raisons": "Reasons", "score": "Score", **kpi_cols, "puissance": "Power",
                   "puissance_evol": "Power change", "jours_sans_connexion": "Days since login",
                   "semaines_consecutives_ko": "Weeks below target"}
    sheet = week[list(report_cols)].rename(columns=report_cols)
    rapport = out / f"report_{last:%Y-%m-%d}.xlsx"
    try:
        import pandas as pd
        with pd.ExcelWriter(rapport) as xw:
            sheet[sheet["Status"].isin([ALERTE, SURVEILLER])].to_excel(xw, sheet_name="Flags", index=False)
            sheet.to_excel(xw, sheet_name="Members", index=False)
            summary.to_excel(xw, sheet_name="Alliance", index=False)
            mv = {"pseudo": "Player", "governor_id": "Governor ID", "rang": "Rank", "puissance": "Power"}
            gone.rename(columns=mv).to_excel(xw, sheet_name="Departures", index=False)
            arrived.rename(columns=mv).to_excel(xw, sheet_name="Arrivals", index=False)
            r4.rename(columns={**mv, "rang_avant": "Previous rank", "changement": "Change"}).to_excel(
                xw, sheet_name="R4 changes", index=False)
    except PermissionError:
        log.append(f"{rapport.name} is open in Excel: report not rewritten.")

    write_dashboard(build_payload(hist, summary, cfg, log), out / "dashboard.html")

    # --- résumé console
    w = summary.iloc[-1]
    print("\n".join(log))
    print(f"\nSemaine du {last:%d/%m/%Y} : {int(w['membres'])} membres · "
          f"{int(w['n_alert'])} en alerte · {int(w['n_watch'])} à surveiller · "
          f"{w['pct_tous_objectifs']:.0f} % à tous les objectifs")
    print(f"Dashboard : {out / 'dashboard.html'}")

    # --- publication GitHub Pages
    if publier:
        print(publish(ROOT, out / "dashboard.html", cfg, f"Week ending {last:%Y-%m-%d}"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Traitement hebdomadaire du suivi d'activité ToW")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--sans-publication", action="store_true", help="ne rien envoyer sur GitHub")
    a = ap.parse_args()
    main(a.config, publier=not a.sans_publication)
