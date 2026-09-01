# BRIQ — calepinage du système constructif en briques de bois chevillées

Calcule, à partir d'un plan de maison, tout ce qu'il faut pour la construire avec
le système BRIQ : calepinage rang par rang, nomenclature, plans de montage et
métré de matière première.

> Les plans produits portent la mention : « Document de calepinage —
> dimensionnement structural à valider par un bureau d'études bois
> (Eurocode 5, sismique) ».

## Démarrage

```bash
uv sync                                          # installe tout
uv run briq valider exemples/maison.json         # contrôle le plan
uv run briq calepiner exemples/maison.json -o sortie/   # dossier complet
```

| Commande | Effet |
|---|---|
| `briq valider PLAN` | rapport de validation seul ; sort en 1 s'il y a une erreur |
| `briq calepiner PLAN -o DOSSIER` | le dossier complet : modèle, nomenclature, métré, débit, plans |
| `briq nomenclature PLAN` | la nomenclature à l'écran, sans rien écrire |
| `briq debit PLAN` | le plan de découpe optimisé, sans rien écrire |
| `briq schema -o DOSSIER` | régénère le schéma JSON du format de plan |

Options utiles de `calepiner` : `-f svg` (répétable) restreint les formats de
plans, aucune occurrence produisant les quatre ; `--glouton` remplace le solveur
de débit exact par celui sans dépendance ; `--secondes` borne chaque phase du
solveur exact.

`calepiner` écrit `calepinage.json`, `nomenclature.csv`,
`nomenclature-par-mur.csv`, `metre.csv`, `debit.csv`, `rapport.txt`, les
17 planches en `plans/*.svg`, le `dossier.pdf` A3 relié, les `dxf/*.dxf` à
l'échelle 1 et les `3d/*.glb`.

Référencez le schéma depuis votre plan
(`"$schema": "../schemas/briq-plan-v1.schema.json"`) pour obtenir autocomplétion
et validation en direct dans l'éditeur pendant la saisie. Un test vérifie que le
schéma commité suit le modèle : sans cela l'autocomplétion mentirait.

## État d'avancement

| Jalon | Contenu | État |
|---|---|---|
| 1 | modèle, règles, moteur de calepinage, tests | **livré** |
| 2 | nomenclature, métré, débit optimisé | **livré** |
| 3 | plans SVG / PDF A3 / DXF, vue 3D de contrôle | **livré** |
| 4 | CLI complète, exemple, documentation | **livré** |

## Architecture

```
src/briq/
  units.py      constantes de grille — tout est un entier de millimètres
  model/        plan.py    schéma d'entrée validé (Pydantic, JSON Schema versionné)
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
Typer et Rich qu'à la CLI, OR-Tools qu'au solveur exact (avec un repli glouton),
ReportLab, ezdxf et trimesh qu'aux back-ends de dessin.

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
uv run pytest                  # 98 tests, ~60 s
uv run pytest -m "not lent"    # ~25 s : exclut les preuves d'optimalité du débit
uv run ruff check src tests
uv run mypy
```

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

## Documentation

- `docs/00-choix-techniques.md` — pourquoi cette pile technique
- `docs/etudes/longueur-de-barre.md` — pourquoi la barre de 4 m, et pourquoi
  2,40 m est le pire choix
- `docs/hypotheses.md` — les points du brief que l'application interprète, et les
  questions à trancher
