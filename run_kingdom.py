"""Traitement hebdomadaire du dashboard ROYAUME — à lancer après avoir déposé le CSV du royaume.

    python run_kingdom.py

1. lit tous les exports de data/kingdom/raw (un par semaine)
2. écrit dans output/kingdom/ :
     - dashboard.html           -> le tableau de bord du royaume
     - historique_royaume.csv   -> base complète (1 ligne = gouverneur × semaine)
     - resume_royaume.csv       -> 1 ligne par semaine (royaume entier et Top N)
3. publie le dashboard sur GitHub Pages (docs/kingdom/index.html), si activé dans config_kingdom.yaml

    python run_kingdom.py --sans-publication   -> tout recalculer sans rien envoyer sur GitHub
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

from rok_activity.publish import publish
from rok_kingdom.blacklist import update_blacklist
from rok_kingdom.analyse import carry_forward, weekly_summary
from rok_kingdom.dashboard import build_payload, load_acceptes, write_dashboard
from rok_kingdom.ingest import load_snapshots

ROOT = Path(__file__).resolve().parent


def _b(v) -> str:
    return "n/a" if v is None or pd.isna(v) else f"{v / 1e9:+.2f} B" if abs(v) >= 1e9 else f"{v / 1e6:+.1f} M"


def main(config_path: str = "config_kingdom.yaml", publier: bool = True) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cfg = yaml.safe_load((ROOT / config_path).read_text(encoding="utf-8"))
    out = ROOT / cfg["dossiers"]["sortie"]
    out.mkdir(parents=True, exist_ok=True)
    top_n = int(cfg.get("top_n", 400))

    df, log = load_snapshots(cfg, ROOT)
    df = carry_forward(df)
    summary = pd.concat([weekly_summary(df), weekly_summary(df, top_n)], ignore_index=True)

    df.to_csv(out / "historique_royaume.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(out / "resume_royaume.csv", index=False, encoding="utf-8-sig")
    acceptes = load_acceptes(ROOT / cfg["dossiers"].get("migrants_acceptes", "data/kingdom/migrants_acceptes.csv"), log)
    illegaux = load_acceptes(ROOT / cfg["dossiers"].get("migrants_illegaux", "data/kingdom/migrants_illegaux.csv"), log)
    blacklist = update_blacklist(ROOT / cfg["dossiers"].get("blacklist", "data/kingdom/blacklist.csv"), ROOT, cfg, log)
    dash = write_dashboard(build_payload(df, cfg, log, acceptes, illegaux, blacklist), out / "dashboard.html")

    print("\n".join(log))
    last = summary["semaine"].max()
    for r in summary[summary["semaine"] == last].itertuples():
        print(f"\nSemaine du {last:%d/%m/%Y} — {r.perimetre} : {r.gouverneurs} gouverneurs · "
              f"power {r.power_total / 1e9:.2f} B ({_b(r.power_wow)}) · KP {r.kp_total / 1e9:.2f} B ({_b(r.kp_wow)})"
              f" · méthode : {r.methode}"
              + ("" if r.arrivees is None or pd.isna(r.arrivees) else f" · {int(r.arrivees)} arrivée(s), {int(r.departs)} départ(s)")
              + (f" · semaine en cours : {r.pas_encore_vus} pas encore revus (reportés)" if r.en_cours else ""))
    print(f"\nDashboard : {dash}")

    if publier:
        print(publish(ROOT, dash, cfg, f"Kingdom dashboard — week ending {last:%Y-%m-%d}"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Traitement hebdomadaire du dashboard royaume 4113")
    ap.add_argument("--config", default="config_kingdom.yaml")
    ap.add_argument("--sans-publication", action="store_true", help="ne rien envoyer sur GitHub")
    a = ap.parse_args()
    main(a.config, publier=not a.sans_publication)
