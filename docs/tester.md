# Comment tester l'application

Quatre niveaux, du plus rapide au plus révélateur. Les trois premiers sont
automatisables ; le quatrième ne l'est pas, et c'est pourtant lui qui a trouvé
le plus de bugs.

## 1. La suite de tests

```bash
uv run pytest -m "not lent"    # 178 tests, ~40 s
uv run pytest                  # + les preuves d'optimalité du débit, ~85 s
uv run ruff check src tests
uv run mypy
```

Le marqueur `lent` isole les tests qui résolvent le programme entier du débit à
l'optimum et vérifient qu'aucune solution meilleure n'existe. Ils prennent la
moitié du temps total ; on les exclut pendant le développement, jamais avant de
pousser.

La couverture se mesure avec :

```bash
uv run pytest -m "not lent" --cov=briq --cov-report=term-missing
```

96 % au dernier passage. Le chiffre global ne dit rien d'utile : ce qui compte
est de le lire **module par module**. C'est ainsi qu'on a vu que
`drawings/volume.py` était à 50 % — la vérification des tenons était testée,
l'écriture effective des fichiers `.glb` ne l'était pas du tout.

### Ce que les tests garantissent réellement

| Famille | Ce qu'elle protège |
|---|---|
| tests unitaires | des comptages faits à la main, sur des cas connus |
| tests à propriétés (Hypothesis) | les invariants du calepinage sur des milliers de murs tirés au hasard |
| contrôles croisés | deux sources écrites indépendamment qui doivent concorder |
| tests de dessin | le contenu des planches, pas les chaînes de SVG |
| test de schéma | que le JSON Schema commité suit encore le modèle |

Les trois contrôles croisés sont la meilleure défense du projet, parce qu'ils ne
comparent pas le code à lui-même : composition d'une brique contre sa géométrie
interne, métré contre somme des pièces de la nomenclature, tenons d'un rang
contre réceptions du rang au-dessus. Chacun a déjà attrapé une vraie erreur.

## 2. Le clone neuf

Les tests tournent dans un environnement déjà installé : ils ne peuvent pas voir
un défaut d'installation. Il faut donc partir de zéro.

```bash
git clone <dépôt> /tmp/essai && cd /tmp/essai
uv sync
uv run briq valider exemples/maison.json
uv run briq calepiner exemples/maison.json -o sortie/
```

`uv sync` installe l'application **complète** : le groupe `complet` de
`pyproject.toml` référence les extras du projet, et `default-groups` l'active.
Sans cela, `uv sync` n'installait que le noyau et les trois commandes du README
échouaient sur un `ModuleNotFoundError: No module named 'ezdxf'` — bug trouvé
exactement de cette façon, et par aucun test.

## 3. L'installation minimale

L'inverse du précédent : vérifier que l'application reste utilisable **sans**
les extras.

```bash
python -m venv .venv && .venv/bin/pip install -e .
.venv/bin/briq valider exemples/maison.json
.venv/bin/briq calepiner exemples/maison.json -o sortie/
.venv/bin/briq debit exemples/maison.json
.venv/bin/briq web
```

Attention : `uv run` resynchronise l'environnement depuis `pyproject.toml` et
réinstallerait tous les extras. Il faut appeler le binaire directement pour que
l'essai veuille dire quelque chose.

Comportement attendu, sans aucun extra :

| Commande | Résultat |
|---|---|
| `valider` | identique — le noyau n'a besoin de rien |
| `calepiner` | 23 fichiers, SVG seul, avec un message par format écarté |
| `debit` | repli sur le solveur glouton : 1 229 barres, 3,13 % de chute |
| `web` | « Interface web indisponible : installer l'extra avec `uv sync --extra web` » |

La règle : **un extra manquant retire une sortie, il ne casse jamais une
commande.** Les back-ends de dessin sont donc importés paresseusement, à
l'intérieur des fonctions qui s'en servent, et jamais au chargement du module.

## 4. L'essai en navigateur

C'est le niveau qui trouve le plus de bugs, et aucun test ne le remplace.

```bash
uv run briq web        # http://127.0.0.1:8000
```

Le parcours à refaire après toute modification de l'éditeur :

1. **Onglet Plan** — coller `exemples/maison.json`, calepiner, ouvrir plusieurs
   planches, télécharger le zip et vérifier qu'il contient bien le PDF.
2. **Onglet Esquisse** — dessiner trois ou quatre pièces contiguës, en glissant
   (un simple clic ne doit rien créer), caler sur 480, lire le rapport de ce qui
   a bougé.
3. Créer volontairement un **recouvrement** de deux pièces : le message doit
   être en français et désigner les pièces, pas remonter une trace Pydantic.
4. Laisser volontairement un **vide de 240** entre deux pièces : l'application
   doit refuser et donner la position de chaque bloc.
5. **Onglet Baies** — poser une porte de 1 200 sur un mur, vérifier qu'elle
   reste à 1 200 après calage (les baies se calent sur 240, pas sur 480), lire
   le passage libre annoncé.
6. Renommer une baie, **enregistrer** l'esquisse, rafraîchir la page, la
   **rouvrir** : le nom choisi doit revenir tel quel.
7. Envoyer l'esquisse au calepinage et vérifier que les baies apparaissent sur
   les élévations.

Sont sortis de ce parcours, et d'aucun test : le clic simple qui créait une
pièce fantôme de 240 × 240, la porte de 1 200 réduite à 960 par un calage sur
480, l'origine du plan normalisée à 0 qui décalait tous les murs par rapport au
dessin à l'écran, et une route `/etude/{clé}/planche/{index}` qui capturait
`0.svg` et renvoyait un 422 — Starlette compare les routes dans l'ordre de
déclaration, la variante `.svg` doit être déclarée en premier.

## Ce que rien ne teste encore

- Le rendu des DXF dans un vrai logiciel de CAO : on vérifie la structure du
  fichier, pas ce qu'un opérateur voit à l'écran.
- L'impression des A3 sur du papier : la pagination est testée, pas la lisibilité
  des repères portés sur les briques.
- Et surtout, ce qu'aucun logiciel ne saura tester : le calepinage produit est un
  document de calepinage, pas une note de calcul. Le dimensionnement structural
  reste à valider par un bureau d'études bois (Eurocode 5, sismique).
