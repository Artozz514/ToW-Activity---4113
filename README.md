# Suivi d'activité — ToW (royaume 4113)

Ce dossier produit chaque semaine un **dashboard HTML en anglais** (alliance internationale) pour les leaders. Il montre l'activité des membres, l'évolution de l'alliance et les membres à flagger. Tout est recalculé à partir des exports bruts : pour passer la main, il suffit de transmettre ce dossier.

## Routine du dimanche (2 minutes)

1. Déposer l'export de la semaine **sans le renommer** dans `data/raw/` (csv ou xlsx, au choix).
2. Double-cliquer `lancer_semaine.bat`, ou lancer `python run_weekly.py`.
3. Si la console signale des « nouveaux membres », compléter leur rang dans `roster.csv`, puis relancer.
4. C'est tout : le dashboard est publié automatiquement sur le lien des leaders (voir « Mettre en ligne »).

## Ce qui est produit dans `output/`

Le dashboard contient : indicateurs clés, évolution de l'alliance, membres flaggés, % d'objectifs atteints par activité, départs, **Top 5 et Bottom 5 par activité**, et la liste complète des membres avec leur historique.


| Fichier | Contenu |
|---|---|
| `dashboard.html` | Le tableau de bord : un seul fichier, sans dépendance, qui marche hors-ligne |
| `report_AAAA-MM-JJ.xlsx` | La semaine en cours, en anglais : onglets Flags, Members, Alliance, Departures |
| `historique.csv` | Base complète : 1 ligne = 1 membre × 1 semaine |
| `resume_alliance.csv` | 1 ligne par semaine : effectifs, totaux, % d'objectifs atteints, nombre d'alertes |

## Ce qu'on modifie à la main (jamais le code)

- **`config.yaml`** : objectifs, poids, règles de flag, rangs exemptés. Un objectif peut dépendre du rang : `objectif: {defaut: 6000, R4: 8000}`.
- **`roster.csv`** : rang de chaque membre, exemption temporaire (`exempte_jusqu_au` = `30/11/2026`, pour des vacances par exemple), note libre. Les nouveaux IDs sont ajoutés tout seuls ; la colonne pseudo suit le pseudo en jeu.

## Rangs et changements de R4

- Le jeu n'exporte pas le rang : **c'est `roster.csv` qui fait foi**. À chaque exécution, les rangs du roster sont photographiés pour la semaine en cours dans `data/rangs_historique.csv`. Les semaines passées n'y sont jamais modifiées.
- ⚠ **Ce fichier ne peut pas être recalculé** (contrairement au reste) : ne pas le supprimer. Il est sauvegardé sur GitHub.
- **Pour qu'une promotion soit datée correctement**, il faut mettre à jour le rang dans `roster.csv` *avant* de lancer le traitement du dimanche.
- **« R4 changes since last week »** (dashboard, sous les arrivées) liste les membres qui entrent dans le groupe R4 (R1/R2/R3 → R4 ou R5) ou qui en sortent (R4/R5 → R1/R2/R3), par rapport à la semaine juste avant. Les permutations R4 ↔ R5 et les rangs inconnus (« ? ») sont ignorés. On retrouve la même liste dans l'onglet *R4 changes* du rapport Excel et dans le journal.
- Pour les semaines legacy, on utilise le rang noté dans l'ancien fichier.

## Comment un membre est classé

Objectifs officiels (fixes) : **50 000 tech**, **500 aides**, **80 forts** par semaine, pas de minimum pour la construction.

- **Score** = moyenne pondérée de `valeur ÷ objectif` pour chaque KPI, plafonnée à 150 %. **100 = tous les objectifs pile atteints.** Ce score est absolu : contrairement à l'ancien fichier, on peut comparer les semaines entre elles.
- **Alert** : inactif depuis plus de 3 jours, **ou** objectif **forts** raté (KPI critique, même la 1re fois), **ou** au moins 2 KPI ratés, **ou** au moins 2 semaines d'affilée sous l'objectif. Action : **rétrograder en R1** (R3 → R1).
- **Watch** : 1 KPI raté (une première fois, hors forts). Un membre qui atteint tous ses objectifs n'est jamais flaggé, même si son activité baisse par rapport à ses semaines précédentes. Action : **rester R3, ajouter un * au pseudo**.
- Les KPI critiques (`kpis_critiques`) et les textes d'action (`actions`) se règlent dans `config.yaml`.
- **Tableau « Flagged members »** : pseudo, Governor ID, statut (avec la raison), action à mener, case **Done**. La case est mémorisée par semaine et par membre **dans le navigateur de celui qui la coche** : les autres leaders ne la voient pas. L'onglet *Flags* du rapport Excel reprend le même tableau avec une colonne Done vide.
- **Exempt** : rang listé dans `rangs_exemptes`, ou date d'exemption pas encore passée.
- **New** : membre arrivé en cours de semaine (son ID apparaît pour la première fois). Il n'est jamais flaggé cette semaine-là, il est exclu des % d'objectifs et du Bottom 5, et sa série de semaines sous l'objectif ne démarre qu'à sa première semaine complète. Réglage : `pas_de_flag_semaine_arrivee` dans `config.yaml`.

Tous ces seuils sont réglables dans `config.yaml`.

## Règles sur les fichiers d'export

- La date est lue dans le nom du fichier (`…_activity_20261109_195827.csv`), d'où l'importance de ne pas le renommer.
- La semaine de jeu va du **lundi au dimanche**. Un export est rattaché à la semaine qui le contient (« week ending » = le dimanche).
- Deux fichiers dans la même semaine : seul le plus récent compte. Un export pris en cours de semaine est donc remplacé par celui du dimanche. En attendant, le dashboard affiche un bandeau « Week in progress ».
- Les libellés affichés (`libelle:` dans `config.yaml`) et les statuts (OK / Watch / Alert / Exempt) sont en anglais. Le code et cette doc restent en français.
- Les fichiers de `data/raw/` ne sont jamais modifiés. Supprimer `output/` ne fait rien perdre.
- Si l'outil d'export renomme une colonne, le script s'arrête et indique laquelle : il suffit de corriger `colonne:` dans `config.yaml`.
- Mode `hebdo` : la valeur de l'export est déjà celle de la semaine. Mode `cumul` : le script calcule la différence avec la semaine précédente. À vérifier pour chaque KPI dans l'outil d'export (voir « Points ouverts »).

## Mettre en ligne (GitHub Pages)

**Lien à partager aux leaders : https://artozz514.github.io/ToW-Activity---4113/**

⚠ Le lien contient le nom du compte GitHub et celui du dépôt : renommer l'un ou l'autre change le lien, et l'ancien ne redirige pas (erreur 404). Pour un lien stable, transférer le dépôt dans une organisation GitHub (ex. `tow-4113`).

- Chaque exécution de `run_weekly.py` copie le dashboard dans `docs/index.html`, puis l'envoie sur le dépôt GitHub `Artozz514/ToW-Activity---4113`. Le site est à jour 1 à 2 minutes plus tard.
- Pour tout recalculer sans rien publier : `python run_weekly.py --sans-publication`. Pour couper la publication : `publication.activer: false` dans `config.yaml`.
- La page est **publique** : quiconque a le lien la voit. Elle n'est pas indexée par Google (balise `noindex`). Ne rien mettre dans les notes du roster qu'on ne voudrait pas voir lu par les joueurs.
- Envoyés sur GitHub : le code, la config, `roster.csv`, les exports de `data/raw/` (indispensables pour reconstruire l'historique) et `docs/`. Le fichier legacy et `output/` restent en local (voir `.gitignore`).

**Tutoriel vidéo : https://artozz514.github.io/ToW-Activity---4113/tutorial/** (bouton « ▶ Tutorial » en haut du dashboard). La vidéo et sa page sont dans `docs/tutorial/` et ne sont pas touchées par le traitement hebdo. Pour la remplacer, il suffit d'écraser `docs/tutorial/tutorial.mp4` (H.264, moins de 100 Mo, la limite de GitHub), puis de publier.

**Passation à un successeur :** l'ajouter comme collaborateur du dépôt (Settings → Collaborators). Il clone le dépôt avec `git clone`, installe les dépendances, et lance `lancer_semaine.bat` chaque dimanche. Au premier envoi, une fenêtre GitHub lui demande de se connecter. Pour garder le même lien, on peut aussi transférer le dépôt (Settings → Transfer), mais l'adresse change alors de compte.

## Installation (une seule fois)

```
pip install -r requirements.txt
```
Il faut Python ≥ 3.10. Anaconda contient déjà tout le nécessaire.

## Structure

```
config.yaml            objectifs et règles
roster.csv             rangs, exemptions, notes
data/rangs_historique.csv  photo hebdo des rangs (à conserver)
data/raw/              exports hebdo bruts (ne pas renommer)
rok_activity/          code : ingest.py (lecture) · analyse.py (calculs) · dashboard.py (HTML) · publish.py (GitHub)
templates/dashboard.html  gabarit du dashboard
run_weekly.py          point d'entrée
docs/index.html        dashboard publié (GitHub Pages)
output/                fichiers générés
config_kingdom.yaml · rok_kingdom/ · run_kingdom.py · templates/kingdom.html   dashboard royaume (voir plus bas)
AUDIT_LEGACY.md        audit de l'ancien fichier Google Sheets
outils/import_legacy.py  import ponctuel des semaines du fichier legacy
```

## Dashboard royaume 4113 (indépendant)

Second dashboard, à l'échelle du royaume entier : un CSV hebdo avec tous les gouverneurs.

**Routine** : depuis mi-novembre 2026, déposer chaque fin de semaine un **snapshot du dernier jour** (période d'un jour, pas des 7 derniers jours : tout le monde est mesuré au même moment, sans décalage) au format `4113_governors_summary_activity_AAAAMMJJ_HHMMSS.csv`, sans le renommer, dans `data/kingdom/raw/`, puis double-cliquer sur `lancer_royaume.bat` (ou `python run_kingdom.py`). Le dashboard est publié sur https://artozz514.github.io/ToW-Activity---4113/kingdom/ (`--sans-publication` pour ne rien envoyer).

**Contenu** : total power et total KP, tendances, hausse hebdo du power et des KP, nouveaux arrivants et départs (par Governor ID), top 5 des hausses de power et de KP (en brut), liste complète des gouverneurs (25 / 50 / 100 / 400 / tous). Le toggle **TOP 400 View** en haut de la page restreint *toutes* les sections aux 400 plus gros power de chaque semaine (`top_n` dans `config_kingdom.yaml`).

**Rattachement aux semaines** : la semaine (lundi → dimanche) est lue dans le contenu du fichier (`From Date`), pas dans son nom. Plusieurs fichiers pour la même semaine : on garde celui qui couvre le plus loin (le snapshot le plus récent remplace les précédents). Les fichiers vides sont ignorés et signalés.

**Snapshot = liste de référence** : un fichier couvrant moins de 4 jours est un snapshot du royaume. Tout gouverneur absent du snapshot est compté comme **parti** et sort des totaux de power et de KP (règle validée par Arthur le 12/11/2026). Un snapshot pris avant le dimanche garde le label « semaine en cours » ; celui de fin de semaine le remplace.

**Ancien export « depuis lundi »** (avant les snapshots) : les gouverneurs de la semaine précédente pas encore revus étaient reportés à leur dernière valeur (« not seen yet ») au lieu d'être comptés comme départs.

**Blacklist** : `data/kingdom/blacklist.csv`. Pour ajouter quelqu'un, une ligne avec `governor_id`, `raison` (en anglais, affichée telle quelle) et `date_ajout`. À chaque exécution, le pipeline complète le dernier pseudo, le dernier power, la date et **tous les anciens noms** vus pour cet ID dans les exports (`raw/` et `analytics/`). Ces noms restent dans le CSV même si les exports disparaissent. Le dashboard affiche la section « Blacklist » et un tag noir `blacklist` dans les listes.

**Méthode** :
- hausse hebdo d'un total = total de la semaine − total de la semaine précédente (J-7), sur le même périmètre : arrivées et départs sont donc compris dedans ;
- hausse d'un gouverneur = sa valeur − sa valeur de la semaine précédente (même ID) ; un nouvel arrivant n'en a pas ;
- 1re semaine suivie (ou semaine précédente manquante) : on utilise à la place les deltas fournis par l'export (`Power Change`, `Kill Points Change`…), qui couvrent la période de suivi de l'outil (≈ 5 jours) ; le dashboard l'affiche dans un bandeau. Les arrivées et départs ne sont alors pas calculables ;
- les colonnes `T4` / `T5` de l'export sont des **nombres d'unités tuées** (cumul) et non de la puissance de troupes : le dashboard affiche donc « T4 / T5 kills WoW ».

**Fichiers** : `config_kingdom.yaml` (réglages), `rok_kingdom/` (code), `templates/kingdom.html` (gabarit), `run_kingdom.py` (point d'entrée), `output/kingdom/` (dashboard, `historique_royaume.csv`, `resume_royaume.csv`), `docs/kingdom/index.html` (version publiée).

## Historique importé du fichier legacy

Les semaines du 27/07 au 30/08/2026 viennent de l'ancien Google Sheet. Elles ont été converties une fois pour toutes par `outils/import_legacy.py` dans `data/raw/legacy/`. Le pipeline les lit comme n'importe quelle semaine.

- **Rapprochement par Governor ID** : le n° de ligne `#` du legacy est traduit en Governor ID grâce au memberlist ; à défaut, on utilise le pseudo exact. Les joueurs sans Governor ID connu (7 à 31 selon la semaine) reçoivent un ID technique négatif : ils comptent dans les totaux d'alliance mais ne sont pas reliés aux exports actuels.
- **Données disponibles** : tech, aides, forts, construction et puissance. Pas de date de connexion, donc pas de contrôle d'inactivité ces semaines-là.
- **L'onglet 31/08-06/09 était vide** : il n'est pas importé.
- **Règle « since last week »** : toute comparaison se fait uniquement avec la semaine juste avant (J-7). Ça concerne les arrivées, les départs, les variations des indicateurs, les semaines d'affilée sous l'objectif, le statut New et l'évolution de puissance. Si la semaine juste avant n'est pas suivie (trou dans l'historique, ici du 30/08 au 15/11), aucune comparaison n'est affichée : le dashboard indique « previous week not tracked ». Les graphiques montrent le trou en zone « no data ». Pour combler un trou, il suffit de déposer l'export manquant dans `data/raw/` : tout est recalculé.

## Points ouverts

- [ ] Compléter les **rangs** dans `roster.csv` : 85 sont vides, et les 51 repris du legacy sont à vérifier.
- [ ] Confirmer que tech, aides, forts et construction sont bien des **compteurs hebdomadaires** dans l'outil d'export (sinon passer en `mode: "cumul"`).
- [ ] Royaume : ré-exporter les semaines du 28/09–04/10 et du 05/10–11/10 (fichiers reçus vides le 11/11/2026).
- [ ] Module KvK (phase 2) : même pipeline, avec des KPI différents (kill points, deads, honneur), sur une fenêtre de dates KvK.
