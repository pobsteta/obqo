# obqo — calepinage du système constructif en briques de bois chevillées

Calcule, à partir d'un plan de maison, tout ce qu'il faut pour la construire avec
le système obqo : calepinage rang par rang, nomenclature, plans de montage et
métré de matière première.

> Les plans produits portent la mention : « Document de calepinage —
> dimensionnement structural à valider par un bureau d'études bois
> (Eurocode 5, sismique) ».

## Démarrage

```bash
uv sync                                          # installe tout
uv run obqo valider exemples/maison.json         # contrôle le plan
uv run obqo calepiner exemples/maison.json -o sortie/   # dossier complet
```

| Commande | Effet |
|---|---|
| `obqo valider PLAN` | rapport de validation seul ; sort en 1 s'il y a une erreur |
| `obqo calepiner PLAN -o DOSSIER` | le dossier complet : modèle, nomenclature, métré, débit, plans |
| `obqo nomenclature PLAN` | la nomenclature à l'écran, sans rien écrire |
| `obqo debit PLAN` | le plan de découpe optimisé, sans rien écrire |
| `obqo web` | interface web sur http://127.0.0.1:8000 — l'esquisse à l'accueil, le calepinage sur `/plan` |
| `obqo gabarit -o FICHIER` | écrit un plan de départ commenté, à modifier |
| `obqo schema -o DOSSIER` | régénère le schéma JSON du format de plan |

Options utiles de `calepiner` : `-f svg` (répétable) restreint les formats de
plans, aucune occurrence produisant les quatre ; `--glouton` remplace le solveur
de débit exact par celui sans dépendance ; `--secondes` borne chaque phase du
solveur exact.

`calepiner` écrit `calepinage.json`, `nomenclature.csv`,
`nomenclature-par-mur.csv`, `metre.csv`, `debit.csv`, `rapport.txt`, les
17 planches en `plans/*.svg`, le `dossier.pdf` A3 relié, les `dxf/*.dxf` à
l'échelle 1 et les `3d/*.glb`.

Référencez le schéma depuis votre plan
(`"$schema": "../schemas/obqo-plan-v1.schema.json"`) pour obtenir autocomplétion
et validation en direct dans l'éditeur pendant la saisie. Un test vérifie que le
schéma commité suit le modèle : sans cela l'autocomplétion mentirait.

## État d'avancement

| Jalon | Contenu | État |
|---|---|---|
| 1 | modèle, règles, moteur de calepinage, tests | **livré** |
| 2 | nomenclature, métré, débit optimisé | **livré** |
| 3 | plans SVG / PDF A3 / DXF, vue 3D de contrôle | **livré** |
| 4 | CLI complète, exemple, documentation | **livré** |
| — | interface web légère (option du brief) | **livrée** |
| — | contours en L, U, T et escalier (angles rentrants) | **livré** |
| — | esquisse : dessiner pièces et baies, enregistrer, rouvrir | **livré** |

## Architecture

```
src/obqo/
  units.py      constantes de grille — tout est un entier de millimètres
  model/        plan.py    schéma d'entrée validé (Pydantic, JSON Schema versionné)
                lecture.py lecture d'un plan, JSON ou YAML
                systeme.py types produits par le moteur (dataclasses gelées)
  rules/        catalogue.py   LES RÈGLES MÉTIER, en tables relisibles face au brief
  engine/       appareillage.py  remplissage d'une course, parité des joints
                geometrie.py     contour → murs et angles, harpage
                validation.py    contrôles et rapport
                calepinage.py    le moteur
  bom/          nomenclature.py  briques, pièces et chevilles, avec sous-totaux
                debit.py         cutting-stock 1D, glouton et optimum exact
                metre.py         métrés linéaires, masse, chiffrage
                sorties.py       CSV et tableaux texte
  web/          app.py           routes FastAPI, gabarits Jinja2
                etude.py         cache borné des études en mémoire
  model/        esquisse.py      les pièces dessinées, avant tout calepinage
                ecriture.py      écriture d'une esquisse en YAML commenté
  engine/       esquisse.py      calage sur la grille, contour, refends
  drawings/     ir.py            modèle de dessin, indépendant du format
                planches.py      élévations, plans de pose, instructions
                mise_en_page.py  échelle, centrage, cartouche A3
                svg.py           back-end SVG (bibliothèque standard)
                pdf.py           back-end PDF A3 multi-pages (ReportLab)
                dxf.py           back-end DXF à l'échelle 1 (ezdxf)
                volume.py        export 3D et vérification des tenons
  cli.py
```

`engine/`, `rules/` et `bom/` n'ont **aucune dépendance** : ils s'importent avec
la seule bibliothèque standard. Pydantic ne sert qu'à la frontière d'entrée,
Typer et Rich qu'à la CLI, FastAPI et Jinja2 qu'à l'interface web, OR-Tools qu'au
solveur exact (avec un repli glouton), ReportLab, ezdxf et trimesh qu'aux
back-ends de dessin. La CLI et le web sont deux clients du même cœur.

### Trois principes

**Aucun flottant.** Toutes les longueurs sont des `int` en millimètres. Un mur de
10 800 mm fait 45 modules de 240, exactement. Pas d'epsilon, pas de `isclose`.

**Les règles sont des données.** `rules/catalogue.py` ne contient aucune logique
de placement : la composition d'une brique y est une table, comparable ligne à
ligne avec le brief. Une règle d'atelier qui change se corrige dans une table.

**Sortie déterministe.** Deux exécutions sur le même plan produisent des fichiers
identiques : tri stable, identifiants calculés (`M2.R07.U01440`), aucune
itération sur des `set`. Sans cela, aucun test de non-régression n'est possible
sur les dessins du jalon 3.

## Le cœur de l'appareillage

Une course remplie de briques de 480 et 240 ne peut produire des joints que
d'**une seule parité**, mesurée en modules de 240 depuis l'origine du mur :

- commencer par une 480 → joints de parité `p₀ = (début / 240) % 2`
- commencer par une 240 → joints de parité `1 − p₀`

Décaler les joints d'un rang à l'autre revient donc à alterner cette parité, et
rien d'autre. Le harpage d'angle décale déjà l'origine du mur de 240 un rang sur
deux : la parité alterne d'elle-même, et la brique d'angle reste une 480 à chaque
rang — ce qu'exige le catalogue (480-ANR filante, 480-A en butée).

Conséquence utile pour dessiner votre plan : **une dimension multiple de 480
évite les demi-briques** sur les murs courants. C'est pourquoi la maison
d'exemple fait 13,92 × 10,56 m et non 13,92 × 10,80 : à 10,80 m, dix
demi-briques se retrouvent en position d'angle, où le catalogue du brief ne
définit aucune référence (voir `docs/hypotheses.md`).

## Tests

```bash
uv run pytest                  # 209 tests, ~85 s
uv run pytest -m "not lent"    # 208 tests, ~40 s : exclut les preuves d'optimalité du débit
uv run ruff check src tests outils
uv run mypy
```

96 % de couverture. La marche à suivre complète — clone neuf, installation
minimale, essai en navigateur, **et les équivalents PowerShell pour
Windows 11** — est dans [`docs/tester.md`](docs/tester.md).

Les tests unitaires vérifient des comptages faits à la main. Les tests à
propriétés (Hypothesis) vérifient les **invariants** sur des milliers de murs
tirés au hasard : une course exactement remplie, aucun recouvrement, et surtout
aucun joint du rang *n* aligné avec un joint du rang *n+1*.

Trois contrôles croisés protègent les règles métier, en comparant deux sources
écrites indépendamment : la table de composition d'une brique contre sa table de
géométrie interne, le métré contre la somme des pièces de la nomenclature, et les
tenons contre les réceptions du rang supérieur.

## Le débit de matière

Le problème est un cutting-stock 1D, mais **petit et exactement soluble** : les
longueurs demandées sont peu nombreuses, si bien qu'on énumère *tous* les patrons
de découpe d'une barre (761 pour une barre de 4 m à 4 mm de trait) puis on résout
un programme entier à l'optimum. Objectif lexicographique : minimiser les barres,
puis les patrons distincts, puis maximiser les chutes réutilisables.

Sur la maison d'exemple, l'optimum exact sort **1 215 barres en 3 patrons**, avec
2,00 % de chute — contre 1 229 barres en 7 patrons pour un glouton. Il n'y a donc
aucun arbitrage à faire entre économie de bois et simplicité d'atelier.

Le bois acheté se répartit en **trois** catégories, jamais deux : les pièces
utiles, la **surproduction** (des pièces en trop, utilisables en rechange — un
fond de barre rempli d'une pièce de plus ne gaspille rien) et la **chute**, seul
vrai déchet. Les confondre masque complètement le rendement réel.

## L'esquisse : dessiner les pièces, l'application en tire le plan

`obqo web` ouvre sur l'**éditeur d'esquisse** — c'est la page d'accueil, et
l'ordre du travail réel : on dessine, puis on calepine. On pose les pièces à la
souris, l'application cale le dessin sur la grille et en déduit le contour et les
refends ; la page de calepinage (`/plan`) s'atteint ensuite d'un bouton, déjà
chargée du plan dérivé. Arriver d'emblée sur un plan JSON suppose qu'on en a
un ; arriver sur une feuille à dessiner ne suppose rien. L'ancienne adresse
`/esquisse` redirige vers l'accueil : un signet ne tombe pas sur un 404.

Deux pas distincts, et c'est volontaire. On **dessine** au pas de 240 mm, avec
aimantation aux pièces voisines — un vide de 240 entre deux pièces ne se voit pas
à l'écran et couperait le bâtiment en deux. On **cale** ensuite sur 480, la cote
qui évite les demi-briques, et l'application dit ce qui a bougé, pièce par pièce.

Le calage porte sur les **lignes de coordonnées**, pas sur les pièces : deux
pièces qui se touchaient se touchent encore après calage, la topologie du plan
est préservée par construction.

Ce que le moteur sait calepiner borne le résultat, et l'application le dit au
lieu de produire un plan infaisable :

| Situation | Réponse |
|---|---|
| mur intérieur qui traverse tout le bâtiment | **refend obqo** |
| mur intérieur qui s'arrête en chemin | cloison légère, hors calepinage |
| deux refends qui se croisent | le sens le plus long l'emporte, l'autre devient cloison |
| pièces en deux blocs séparés | refus, avec la position de chaque bloc |
| pièces qui ne se touchent que par un coin | refus : le contour serait ambigu |

Une ligne du treillis n'est d'ailleurs pas forcément un mur : elle naît du bord
d'une pièce et peut traverser la voisine de part en part. Sans distinguer les
deux, l'application posait un mur porteur au milieu du séjour, que personne
n'avait dessiné.

**Les baies se posent aussi à la souris**, dans l'onglet *Baies* : on glisse le
long d'un mur, on choisit porte, fenêtre ou porte-fenêtre, on règle l'allège et
la hauteur. L'application rappelle en direct le passage libre — la trémie moins
les jambages — et signale la portée qui dépasserait le linteau chevillé.

**Et elles se redimensionnent au clavier** : les deux cotes de la trémie,
*hauteur × largeur*, se tapent dans le formulaire de la baie sélectionnée.
Glisser donne la baie à peu près, le champ la donne exactement — une porte de
2 160 × 960, une baie vitrée de 2 400 × 2 400. La largeur s'applique le long du
mur, rive gauche fixe ; si la baie ne tient plus jusqu'au bout, elle recule
d'elle-même au lieu d'en sortir, et un mur trop court le dit. Toute cote tapée
passe par la grille de 240, comme celle tirée à la souris : le pas du champ
n'est qu'une aide aux flèches, et 1 250 mm ferait refuser le plan dérivé.

Le résumé sous les champs ne se contente plus du passage libre : il annonce
aussi la baie qui dépasse la hauteur sous chaînage (allège + hauteur + le rang
de linteau) et la rive à moins de 480 mm d'un angle. Ces deux règles étaient
déjà vérifiées — mais à la génération du plan, une fois la baie posée, au lieu
du moment où l'on tape la cote.

Les murs sur lesquels on pose les baies viennent du serveur, pas d'un calcul
refait côté navigateur : une seule source de vérité pour la géométrie.

Une baie se cale sur **240**, jamais sur 480, contrairement aux murs : une porte
de 1 200 est parfaitement valide, et l'arrondir à 960 lui coûterait 24 cm de
passage.

Une esquisse complète — pièces et baies — produit un plan qui se calepine tel
quel, sans passer par le YAML. **Et sans copier-coller** : le plan dérivé est
déposé côté serveur, et deux boutons y mènent — « Calepiner ce plan » enchaîne
directement sur la nomenclature et les planches, « Ouvrir dans l'onglet Plan »
le charge dans l'éditeur pour le compléter à la main. Le bouton d'enchaînement
n'apparaît que si le plan se calepine vraiment : sinon il n'afficherait que ses
propres erreurs.

Passer par le serveur plutôt que par le stockage du navigateur n'est pas
gratuit — c'est ce qui fait marcher le transfert en navigation privée, survivre
à un lien copié dans un autre onglet, et se vérifier par un test.

**Les cotes des baies se placent toutes seules.** Une étiquette posée au-dessus
de la baie se couche en travers du mur dès qu'il est vertical : « porte
d'entrée H2160×L1200 » fait plusieurs mètres de long pour un mur de 240. Elle est donc décalée
perpendiculairement au mur, vers l'extérieur du bâtiment, rentrée du côté
intérieur quand le mur touche le bord du cadre, et écartée d'une ligne tant
qu'elle mord sur une voisine ou sur un nom de pièce. Le cran d'échappement vaut
une ligne, pas la longueur de l'étiquette : deux textes horizontaux se dégagent
en hauteur, et un cran trop grand envoie l'étiquette à des mètres de sa baie.

**Les baies portent un nom**, pas un code : « porte d'entrée », « fenêtre
cuisine ». Le nom par défaut suit le type (`porte 1`, `fenêtre 2`) et se met à
jour tant qu'on ne l'a pas choisi soi-même. C'est ce nom qu'on retrouve dans la
nomenclature et sur les élévations.

**L'esquisse s'enregistre et se rouvre** — un YAML commenté, lisible et
rechargeable — et le travail en cours survit à un rafraîchissement de page.

## Les contours non rectangulaires

Le moteur accepte tout contour rectiligne fermé : L, U, T, escalier. Ce qui
demande un traitement à part, ce sont les **angles rentrants** (270° à
l'intérieur), et ils ne sont pas le symétrique des angles convexes.

À 90°, les deux bandes de mur se recouvrent dans un carré de 240 × 240 : le mur
filant le prend, le mur en butée recule de 240. **À 270°, les deux bandes ne se
touchent que par un point** : la colonne de 240 se trouve au-delà du sommet, et
c'est le mur filant qui déborde de 240 pour la remplir. Traiter les deux cas de
la même façon laissait un trou de 240 × 240 dans le mur, à chaque rang.

Cinq familles de contour sont vérifiées en continu — rectangle, L, U, T,
escalier — plus des L et des U de dimensions tirées au hasard : couverture
exacte, aucun recouvrement, joints décalés, et aucun tenon sans réception.

## Les plans

Un **modèle de dessin intermédiaire** (`drawings/ir.py`) décrit les planches en
millimètres du modèle, sans rien savoir des formats. Trois back-ends s'en
servent : le SVG n'utilise que la bibliothèque standard, le PDF passe par
ReportLab (pur Python, A3 relié multi-pages, aucune dépendance système), et le
DXF dessine à l'échelle 1 dans l'espace objet, comme l'attend un logiciel de CAO.
On teste ainsi le dessin — « l'élévation du mur M2 contient 45 rectangles de
brique et 2 cotes » — au lieu de comparer des chaînes de SVG, et la mention
obligatoire est apposée par le back-end, donc impossible à oublier.

Le dossier comprend une élévation par mur, un plan de pose par rang et une page
d'instructions générée.

**Pagination.** Une élévation qui ne tiendrait pas au 1:50 est découpée en
plusieurs A3 qui se recouvrent d'une bande de 960 mm, plutôt que réduite au 1:100
où les repères portés sur les briques ne se lisent plus. Les pages partagent le
même cadre vertical pour rester comparables. Les murs de 13,92 m de la maison
d'exemple tiennent sur une seule feuille ; un mur de 24 m en demande deux.

## La vérification 3D

Toutes les pièces du système sont des boîtes alignées sur les axes : le rendu 3D
est presque gratuit. Il répond à la seule question que les élévations 2D ne
savent pas trancher — **le harpage croisé alterné tombe-t-il juste ?**

`drawings/volume.py` place chaque pièce dans le repère du plan et vérifie que
tout tenon trouve sa réception au rang supérieur. Un test permanent prouve que
les seuls tenons orphelins sont ceux qui tombent sous une baie ou hors de
l'emprise d'un linteau — et l'application en tire la liste exacte des **tenons à
couper à ras**, calculée sur la géométrie réelle des pièces plutôt que déduite de
la position des baies :

```
TENONS A COUPER A RAS (60)
  M1 rang R03 : u = 5360, 5600, 5840, 6080, 6320, 6560 mm
  M1 rang R08 : u = 2720, 4160, 5120, 6800, 8960, 11600 mm
  ...
```

Cette approche a déjà payé deux fois : elle a attrapé une erreur de composition
de la 480-ANR (trois carrés P8 au lieu d'un) et un défaut de placement sur les
murs orientés vers l'ouest ou le sud, où le point de départ d'une pièce est son
bord maximum et non son minimum.

## L'interface web

```bash
uv sync --extra web
uv run obqo web            # http://127.0.0.1:8000
```

Saisie du plan à gauche, résultat à droite : rapport de validation coloré par
gravité, nomenclature, métré, plan de découpe, et les 17 planches consultables
une à une. Le dossier complet se télécharge en un zip.

Le solveur glouton est le défaut ici — l'interface doit répondre tout de suite —
et l'optimum exact reste à une case à cocher. Les études sont gardées en mémoire,
indexées par l'empreinte du plan, les huit plus récentes ; rien n'est persisté,
il n'y a pas de base de données.

**Pas de HTMX ni de framework front**, contrairement à ce que recommandait
`docs/00-choix-techniques.md`. L'application n'a que trois interactions —
soumettre un plan, changer de planche, télécharger — et le serveur renvoie du
HTML déjà rendu. Une trentaine de lignes de JavaScript suffisent, sans
bibliothèque à maintenir ni CDN à joindre depuis un atelier hors ligne. Si
l'interface grossit (édition graphique du plan, comparaison de variantes), HTMX
redeviendra le bon choix.

## Versions et publication

**Le message de commit décide de la version.** Le dépôt suit les commits
conventionnels, et chaque fusion sur la branche par défaut se donne toute seule
sa version, son tag et sa release : `feat` avance la mineure, `fix` et `perf` la
corrective, une rupture (`feat!:`) la majeure ; `docs`, `refactor`, `chore` et
compagnie ne publient rien. Une fusion qui ne mérite pas de version n'en reçoit
pas — un dépôt qui publie à chaque virgule noie ses vraies versions.

```bash
uv run python -m outils.version   # ce que la prochaine fusion publierait
uv run obqo --version             # ce que le paquet installé annonce
```

Tant que la majeure vaut 0, une rupture avance la **mineure** et non la
majeure : une version 0 ne promet aucune stabilité, et le passage en 1.0 est une
décision, pas l'effet de bord d'un point d'exclamation.

La règle n'est pas apportée par une dépendance de publication : elle tient en
trente lignes lisibles dans `outils/version.py`, testées dans
`tests/test_version.py` — jusqu'au garde-fou qui vérifie que `pyproject.toml`,
`src/obqo/__init__.py` et le paquet installé disent le même numéro. Une chaîne
de publication qu'on ne sait pas relire finit par publier ce qu'on n'a pas
voulu. Le détail est dans [`docs/publier.md`](docs/publier.md), l'historique
dans [`CHANGELOG.md`](CHANGELOG.md), et les deux workflows dans
`.github/workflows/` : `controles.yml` (ruff, mypy, pytest — appelé par les
pull requests **et** par la publication, pour qu'une version ne passe pas une
porte plus large) et `publication.yml`.

## Documentation

- `docs/00-choix-techniques.md` — pourquoi cette pile technique
- `docs/etudes/longueur-de-barre.md` — pourquoi la barre de 4 m, et pourquoi
  2,40 m est le pire choix
- [`docs/saisir-un-plan.md`](docs/saisir-un-plan.md) — comment passer d'une idée
  ou d'un plan d'architecte au fichier que l'application calepine
- `docs/hypotheses.md` — les points du brief que l'application interprète, et les
  questions à trancher
- [`docs/tester.md`](docs/tester.md) — comment vérifier que l'application marche,
  et ce que les tests automatiques ne voient pas
- [`docs/publier.md`](docs/publier.md) — comment le message de commit décide de
  la version, du tag et de la release
