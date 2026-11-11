"""Plan de baisse de power du top 400 (royaume 4113) — page publiée pour les leaders.

    python run_plan.py

Lit :
  - le dernier export Analytics dans data/kingdom/analytics/ (power, KP, alliance de chaque gouverneur) ;
  - data/kingdom/migrants_illegaux.csv (Governor IDs signalés illégaux) ;
  - les exports hebdomadaires data/kingdom/raw/ (date d'arrivée de chaque gouverneur).
Écrit output/kingdom/plan.html et docs/kingdom/plan/index.html (GitHub Pages : …/kingdom/plan/).

Leviers (calculés dans la page, sur le power total du top 400) :
  1. illégaux : −2 M chacun ;
  2. migration forcée : > 20 M de power, < 40 M de KP, présents depuis plus de 2 semaines, hors ToW ;
     compte en net (power qui sort − power des suivants qui entrent dans le top 400) ;
  3. sièges : −400 k pour chacun des 400 premiers.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

from rok_kingdom.ingest import load_snapshots

ROOT = Path(__file__).resolve().parent
PARAMS = {"PER_ILLEGAL": 2e6, "SEAT_POWER": 4e5, "SEATS": 400, "MIN_POWER": 20e6, "MAX_KP": 40e6,
          "SPARED_ALLIANCE": "ToW~"}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    exports = sorted((ROOT / "data/kingdom/analytics").glob("*.xlsx"))
    if not exports:
        raise SystemExit("Aucun export Analytics dans data/kingdom/analytics/.")
    src = exports[-1]
    a = pd.read_excel(src)
    ill = set(pd.read_csv(ROOT / "data/kingdom/migrants_illegaux.csv", encoding="utf-8-sig").governor_id.astype(int))

    # date d'arrivée : première semaine où l'ID apparaît dans les exports hebdo
    cfg = yaml.safe_load((ROOT / "config_kingdom.yaml").read_text(encoding="utf-8"))
    weekly, _ = load_snapshots(cfg, ROOT)
    weekly = weekly[~weekly.get("pas_vu", False)] if "pas_vu" in weekly else weekly
    first = weekly.groupby("id").semaine.min()
    cutoff = weekly.semaine.max() - pd.Timedelta(days=14)          # présent depuis plus de 2 semaines

    g = pd.DataFrame({"id": a["Player ID"].astype(int), "name": a["Player Name"].astype(str), "power": a["Power"].astype(int),
                      "kp": a["Kill Points"].astype(int),
                      "alliance": a["Alliance Tag"].astype(str).replace("No Alliance", "No alliance")})
    g["illegal"] = g.id.isin(ill)
    g["criteria"] = (g.power > PARAMS["MIN_POWER"]) & (g.kp < PARAMS["MAX_KP"]) & (g.id.map(first) <= cutoff)
    g["forced"] = g.criteria & (g.alliance != PARAMS["SPARED_ALLIANCE"])
    g = g.sort_values("power", ascending=False)

    cols = ["id", "name", "power", "kp", "alliance", "illegal", "criteria", "forced"]
    payload = {
        "meta": {"source": src.name, "generated": dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
                 "cutoff": cutoff.strftime("%d %b %Y")},
        "params": PARAMS, "cols": cols,
        "rows": [[(bool(v) if isinstance(v, (bool,)) or type(v).__name__ == "bool_" else (int(v) if hasattr(v, "item") else v))
                  for v in r] for r in g[cols].itertuples(index=False, name=None)],
    }
    html = (ROOT / "templates/plan_power.html").read_text(encoding="utf-8")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("/*__DATA__*/null", data)
    for out in (ROOT / "output/kingdom/plan.html", ROOT / "docs/kingdom/plan/index.html"):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
    print(f"{len(g)} gouverneurs · {int(g.illegal.sum())} illégaux · {int(g.forced.sum())} en migration forcée "
          f"({int((g.criteria & ~g.forced).sum())} {PARAMS['SPARED_ALLIANCE']} épargnés) · présence requise depuis le {cutoff:%d/%m/%Y}")
    print("Page : docs/kingdom/plan/index.html")


if __name__ == "__main__":
    main()
