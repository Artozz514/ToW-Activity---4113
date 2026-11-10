# Audit red-team du fichier legacy « ToW Activity Sheet 7_27-9_6.xlsx »

Audit du 09/11/2026. Tous les constats ont été vérifiés dans le fichier (formules et valeurs).

## Ce qu'il contient

| Onglet | Rôle |
|---|---|
| `ToW Confirmed Memberlist` | 177 joueurs : #, pseudo, Governor ID, statut (ToW / Left / Kicked / ->TwW…), rang R0–R5, + une liste « Leadership » en double |
| `727-82` … `831-96` (6 onglets) | Une feuille par semaine : Power, Tech, Helps, Forts, Build Time, 3 scores, 4 cases à cocher, commentaires, compteur d'« offenses » |
| `Imported Data` | Collage brut des classements in-game, 4 semaines côte à côte (85 colonnes) |

Minimums hebdo affichés : Tech 50 000 · Aides 500 · Forts 80 · Build 0.
Poids du score pondéré : Tech 25 % · Aides 20 % · Forts 35 % · Build 20 %.

## À garder ✅

1. **Les 4 KPI d'activité** (tech, aides, forts, construction) : bon choix, ce sont des actions hebdomadaires qui dépendent de la présence du joueur, pas de sa taille de compte. Repris tels quels.
2. **Des minimums hebdomadaires explicites** et un **score pondéré à poids visibles**. Repris (dans `config.yaml`).
3. **L'idée du score percentile** (« Flattened ») : il résiste mieux aux valeurs extrêmes que le max.
4. **Le roster séparé avec statut et rang**, y compris R0 et les migrations (->TwW…). Repris dans `roster.csv`.
5. **Le système d'avertissements** (offenses) : utile pour responsabiliser. Il est maintenant **calculé automatiquement**.
6. **La recherche par identifiant (XLOOKUP) plutôt que par pseudo** : bon principe, mal appliqué (voir n° 2 ci-dessous).

## Ce qui n'est pas optimisé ❌ (par gravité)

### Bugs qui faussent les résultats
1. **Les plages de formules ne suivent pas le nombre de lignes.** `817-823` et `831-96` vont jusqu'à la ligne 164, mais MAX/PERCENTRANK s'arrêtent à `$127`. Les lignes 128-164 ne sont pas comptées. Ici ce ne sont que des R0, donc c'est sans effet pour l'instant, mais le jour où un membre actif est trié en bas, son score devient faux sans prévenir.
2. **L'ID utilisé est le n° de ligne du roster (`#`), pas le Governor ID.** Insérer ou trier une ligne dans le roster décale tout l'historique. 51 lignes du roster n'ont même pas de Governor ID.
3. **XLOOKUP renvoie 0 si le membre est introuvable.** « Absent de l'export » devient « 0 activité », donc le joueur est flaggé à tort. Ça pèse aussi sur les moyennes : la moyenne de tech de la semaine 24-30/08 vaut 47 401 en comptant 50 lignes à zéro, contre **66 063** pour les membres réellement présents (−28 %).
4. **`831-96` est entièrement vide** : 163 lignes à 0 et des scores en `#DIV/0!`. Le bloc de données de cette semaine n'a jamais été collé.
5. **Le format du collage change d'une semaine à l'autre** : dans le bloc 24-30/08 d'`Imported Data`, la colonne « Rank » contient des pseudos au lieu du classement.
6. **Le compteur d'offenses n'est pas cumulatif** : il est ressaisi à la main chaque semaine. 21 joueurs voient leur compteur *baisser* d'une semaine à l'autre, et 41 membres actifs ratent au moins un minimum avec 0 offense.

### Problèmes de conception
7. **Les scores sont relatifs au meilleur joueur de la semaine** (valeur ÷ MAX). Un seul joueur à 8 821 aides écrase tout le monde, et si toute l'alliance baisse de 30 %, les scores ne bougent pas. On ne peut **pas comparer deux semaines**.
8. **Trois scores** (Activity, Weighted, Flattened) : on ne sait pas lequel fait foi.
9. **Le minimum de construction est à 0** : le critère existe mais ne sert à rien. La 4ᵉ case à cocher (colonne O) est fausse partout.
10. **Aucune vue dans le temps** : ni courbe par membre, ni total de l'alliance par semaine. Les semaines 27/07 et 03/08 ont été saisies en dur et les blocs importés de ces semaines n'existent plus.
11. **Le rang est saisi deux fois** (roster + chaque feuille hebdo) : 23 écarts entre les deux dans la semaine en cours.
12. **Un onglet copié-collé par semaine** + 1 000 lignes vides formatées : le fichier grossit, chaque copie peut casser une plage, et la passation demande de connaître toutes ces astuces.
13. **Colonnes mortes** : « Comments » vide partout, « Offense Reason » toujours le même gabarit vide, liste « Leadership » en double.
14. **Noms de semaine ambigus** (`83-89`, sans année) et une note « mise à jour jeudi & dimanche » qui ne colle pas avec des feuilles hebdomadaires.

## Correspondance avec le nouvel export

| Legacy | Nouvel export | Usage dans la nouvelle solution |
|---|---|---|
| Tech Score | `Technology points` | KPI évalué |
| Times Helped | `Alliance helps` | KPI évalué |
| Forts Destroyed | `Forts destroyed` | KPI évalué |
| Build Time | `Building time (seconds)` | KPI suivi, sans objectif par défaut |
| Power Level | `Power` | Contexte + évolution hebdo |
| — | `Kill points` | Contexte (évolution hebdo, utile en KvK) |
| — | `Last login` | **Nouveau** : détection d'inactivité |
| — | `Armory points`, `Activity points`, `Goals` | Contexte / historique |
| — | `Gifts`, `Gift Score` | Ignorés : 0 pour 100 % des membres |
| — | `Resource assistance` | Ignoré : non nul pour 3 membres seulement |
| Rank | *(absent de l'export)* | Tenu dans `roster.csv` |

⚠ **Les ordres de grandeur ont changé** : médiane tech 9 300 aujourd'hui contre 64 300 dans le legacy, et aides 91 contre 515. Les anciens minimums (50 000 / 500 / 80) flaggeraient presque toute l'alliance. **Les objectifs doivent être redéfinis.**

⚠ Seuls 51 des 136 membres actuels figurent dans le roster legacy. Leurs rangs ont été repris pour démarrer, mais ils datent et sont à vérifier.

⚠ `Building time` vaut exactement 20 000 pour 27 membres et 0 pour 84 : à vérifier côté outil d'export (plafond ? arrondi ?).
