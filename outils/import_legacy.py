"""Import ponctuel des semaines de l'ancien Google Sheet (« ToW Activity Sheet 7_27-9_6.xlsx »).

Convertit chaque onglet hebdomadaire en un CSV au format de l'export actuel, déposé dans
data/raw/legacy/. Le pipeline normal les lit ensuite comme n'importe quelle semaine.

    python outils/import_legacy.py "Copie de ToW Activity Sheet 7_27-9_6.xlsx"

Rapprochement des joueurs (toujours par ID, jamais par pseudo quand c'est possible) :
- onglets avec colonne « # » : # -> Governor ID via l'onglet « ToW Confirmed Memberlist » ;
- premier onglet (sans « # ») ou # sans Governor ID : pseudo exact -> Governor ID du memberlist ;
- joueurs sans Governor ID connu : ID technique négatif et stable (ex. -57). Ils comptent dans
  les totaux d'alliance mais ne peuvent pas être reliés aux exports actuels.
Les lignes R0 (« Not in alliance when updated ») et les lignes sans puissance (joueur absent
de l'import ce jour-là) sont ignorées. L'onglet sans données (831-96) est ignoré.

Hypothèses : année 2026 (le 27/07/2026 est un lundi, ce qui colle avec des semaines
lundi -> dimanche) ; photo prise le dimanche à 22:30 UTC (note du fichier legacy).
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "legacy"
ANNEE = 2026

# onglet -> (dimanche de fin de semaine, onglet avec colonne « # » ?)
ONGLETS = {
    "727-82": (dt.date(ANNEE, 8, 2), False),
    "83-89": (dt.date(ANNEE, 8, 9), True),
    "810-816": (dt.date(ANNEE, 8, 16), True),
    "817-823": (dt.date(ANNEE, 8, 23), True),
    "Current 824-830": (dt.date(ANNEE, 8, 30), True),
    "831-96": (dt.date(ANNEE, 9, 6), True),
}


def main(path: str) -> None:
    wb = openpyxl.load_workbook(path, data_only=True)
    ml = wb["ToW Confirmed Memberlist"]
    members = [(ml.cell(r, 1).value, ml.cell(r, 2).value, ml.cell(r, 3).value) for r in range(2, ml.max_row + 1)
               if ml.cell(r, 2).value]
    num_to_gid = {int(n): int(g) for n, _, g in members if n and g}
    num_to_name = {int(n): name for n, name, _ in members if n}
    name_to_gid = {name: int(g) for _, name, g in members if g}
    name_to_num = {name: int(n) for n, name, _ in members if n}
    # pseudos vus dans les onglets hebdo avec « # » (le memberlist a parfois été renommé depuis)
    for sheet, (_, has_num) in ONGLETS.items():
        ws = wb[sheet]
        for r in range(2, ws.max_row + 1):
            n, p = ws.cell(r, 1).value, ws.cell(r, 2).value
            if has_num and p and isinstance(n, (int, float)):
                name_to_num.setdefault(p, int(n))
    name_to_gid.update({p: num_to_gid[n] for p, n in name_to_num.items() if n in num_to_gid and p not in name_to_gid})

    OUT.mkdir(parents=True, exist_ok=True)
    synthetic: dict[str, int] = {}

    for sheet, (sunday, has_num) in ONGLETS.items():
        ws = wb[sheet]
        off = 1 if has_num else 0
        rows = []
        for r in range(2, ws.max_row + 1):
            player = ws.cell(r, 1 + off).value
            if not player:
                continue
            num = ws.cell(r, 1).value if has_num else None
            rank = ws.cell(r, 2 + off).value
            vals = [ws.cell(r, c + off).value for c in range(3, 8)]  # power, tech, helps, forts, build
            vals = [v if isinstance(v, (int, float)) else 0 for v in vals]
            if rank == "R0" or vals[0] <= 0:
                continue
            gid = num_to_gid.get(int(num)) if num else None
            gid = gid or name_to_gid.get(player)
            if gid is None:  # ID technique stable : n° du memberlist, sinon par pseudo
                n = int(num) if num else name_to_num.get(player)
                key = f"n{n}" if n else f"p{player}"
                gid = synthetic.setdefault(key, -(n if n else 10000 + len(synthetic)))
            rows.append({"Player": player, "ID": gid, "Rank": rank, "Power": vals[0],
                         "Technology points": vals[1], "Alliance helps": vals[2],
                         "Forts destroyed": vals[3], "Building time (seconds)": vals[4]})
        if not rows:
            print(f"{sheet} : aucune donnée, ignoré.")
            continue
        df = pd.DataFrame(rows).drop_duplicates("ID")
        f = OUT / f"legacy_activity_{sunday:%Y%m%d}_223000.csv"
        df.to_csv(f, index=False, encoding="utf-8-sig")
        linked = (df["ID"] > 0).sum()
        print(f"{sheet} -> {f.name} : {len(df)} membres, {linked} reliés à un Governor ID, {len(df) - linked} sans ID.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "Copie de ToW Activity Sheet 7_27-9_6.xlsx"))
