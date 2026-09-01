# BRIQ — calepinage du système constructif en briques de bois chevillées

Calcule, à partir d'un plan de maison, tout ce qu'il faut pour la construire avec
le système BRIQ : calepinage rang par rang, nomenclature, plans de montage et
métré de matière première.

> Les plans produits portent la mention : « Document de calepinage —
> dimensionnement structural à valider par un bureau d'études bois
> (Eurocode 5, sismique) ».

## Démarrage

```bash
uv sync                                        # installe tout
uv run briq valider exemples/maison.json       # contrôle le plan
uv run briq calepiner exemples/maison.json -o sortie/
```

`uv run briq schema` régénère `schemas/briq-plan-v1.schema.json`. Référencez-le
depuis votre plan (`"$schema": "../schemas/briq-plan-v1.schema.json"`) pour
obtenir autocomplétion et validation en direct dans l'éditeur pendant la saisie.

## État d'avancement

| Jalon | Contenu | État |
|---|---|---|
| 1 | modèle, règles, moteur de calepinage, tests | **livré** |
| 2 | nomenclature, métré, débit optimisé | à venir |
| 3 | plans SVG / PDF A3 / DXF | à venir |
| 4 | CLI complète, exemple, documentation | partiel (CLI minimale) |

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
  cli.py
```

`engine/` et `rules/` n'ont **aucune dépendance** : ils s'importent avec la seule
bibliothèque standard. Pydantic ne sert qu'à la frontière d'entrée.

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
uv run pytest          # 44 tests
uv run ruff check src tests
uv run mypy
```

Les tests unitaires vérifient des comptages faits à la main. Les tests à
propriétés (Hypothesis) vérifient les **invariants** sur des milliers de murs
tirés au hasard : une course exactement remplie, aucun recouvrement, et surtout
aucun joint du rang *n* aligné avec un joint du rang *n+1*.

## Documentation

- `docs/00-choix-techniques.md` — pourquoi cette pile technique
- `docs/etudes/longueur-de-barre.md` — pourquoi la barre de 4 m, et pourquoi
  2,40 m est le pire choix
- `docs/hypotheses.md` — les points du brief que l'application interprète, et les
  questions à trancher
