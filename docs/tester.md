# Comment tester l'application

Quatre niveaux, du plus rapide au plus révélateur. Les trois premiers sont
automatisables ; le quatrième ne l'est pas, et c'est pourtant lui qui a trouvé
le plus de bugs.

## 1. La suite de tests

```bash
uv run pytest -m "not lent"    # 186 tests, ~40 s
uv run pytest                  # 187 avec les preuves d'optimalité du débit, ~85 s
uv run ruff check src tests
uv run mypy
```

Le marqueur `lent` isole les tests qui résolvent le programme entier du débit à
l'optimum et vérifient qu'aucune solution meilleure n'existe. Ils prennent la
moitié du temps total ; on les exclut pendant le développement, jamais avant de
pousser.

La couverture se mesure avec :

```bash
uv run pytest -m "not lent" --cov=obqo --cov-report=term-missing
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
uv run obqo valider exemples/maison.json
uv run obqo calepiner exemples/maison.json -o sortie/
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
.venv/bin/obqo valider exemples/maison.json
.venv/bin/obqo calepiner exemples/maison.json -o sortie/
.venv/bin/obqo debit exemples/maison.json
.venv/bin/obqo web
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
uv run obqo web        # http://127.0.0.1:8000
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
6. Poser **deux baies côte à côte** sur un mur vertical, puis deux autres sur
   un mur horizontal : chaque étiquette doit rester à côté de sa baie, sans
   recouvrir sa voisine ni sortir du cadre.
7. Renommer une baie, **enregistrer** l'esquisse, rafraîchir la page, la
   **rouvrir** : le nom choisi doit revenir tel quel.
8. Générer le plan, puis cliquer **« Calepiner ce plan »** : l'onglet Plan doit
   s'ouvrir déjà rempli et lancer le calepinage tout seul. Sur un plan
   incomplet, ce bouton ne doit pas apparaître.
9. Vérifier que les baies apparaissent sur les élévations.

Sont sortis de ce parcours, et d'aucun test : le clic simple qui créait une
pièce fantôme de 240 × 240, la porte de 1 200 réduite à 960 par un calage sur
480, l'origine du plan normalisée à 0 qui décalait tous les murs par rapport au
dessin à l'écran, et une route `/etude/{clé}/planche/{index}` qui capturait
`0.svg` et renvoyait un 422 — Starlette compare les routes dans l'ordre de
déclaration, la variante `.svg` doit être déclarée en premier.

Le placement des étiquettes de baies en est un cas d'école : les deux premières
versions passaient les tests serveur sans broncher, mais la capture d'écran
montrait d'abord deux étiquettes disparues hors du cadre, puis une étiquette
partie à huit mètres de sa baie. Rien qu'un `assert` n'aurait vu.

## Sous Ubuntu

C'est le système sur lequel tout ce document a été vérifié — Ubuntu 24.04 LTS.
Les commandes des quatre niveaux ci-dessus s'appliquent telles quelles ; il ne
reste qu'à installer `uv` et à lancer l'application.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env          # ou rouvrez le terminal

git clone <dépôt> /tmp/essai && cd /tmp/essai
uv sync
uv run obqo valider exemples/maison.json
uv run obqo web                  # puis xdg-open http://127.0.0.1:8000
```

`uv sync` installe aussi Python : rien à prendre dans `apt`, pas de
`python3-venv` ni de `build-essential`, aucune dépendance système pour
ReportLab, ezdxf ou trimesh.

| Situation | Réponse |
|---|---|
| port 8000 déjà pris | `uv run obqo web --port 8010` |
| y accéder depuis un autre poste | `uv run obqo web --hote 0.0.0.0` |
| `Interface web indisponible` | `uv sync --extra web` |

**Sans `uv`**, à condition que `python3 --version` affiche 3.12 ou plus —
Ubuntu 24.04 le fournit, 22.04 est en 3.10 et ne suffit pas :

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[solveur,dessins,volume,web]"
.venv/bin/obqo web
```

## Sous Windows 11

Tout ce qui précède marche à l'identique, à trois différences près : le shell,
le chemin du binaire dans l'environnement virtuel, et le tableur.

### Installer

Dans **PowerShell** (pas `cmd.exe` : il ne connaît pas `curl` ni les accents du
terminal moderne).

**Si vous avez déjà un Python** — Anaconda, Miniconda ou python.org, votre
invite affiche alors quelque chose comme `(base)` — le plus court est de
l'installer avec ce pip-là :

```powershell
pip install uv
```

`uv` atterrit dans le `Scripts\` de cet environnement, donc il est utilisable
tout de suite, sans rouvrir le terminal.

**Sinon**, l'installateur officiel, indépendant de tout Python déjà présent :

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

> **Le piège.** `winget install --id=astral-sh.uv` comme le script ci-dessus
> modifient le `PATH` **des sessions futures, pas de celle en cours**.
> Enchaîner l'installation et `uv sync` dans la même fenêtre donne
> `Le terme « uv » n'est pas reconnu`. Ouvrez une nouvelle fenêtre PowerShell,
> ou rafraîchissez le `PATH` sur place :
>
> ```powershell
> $env:Path = [Environment]::GetEnvironmentVariable("Path","User") + ";" + $env:Path
> ```

Ensuite, quel que soit le chemin pris :

```powershell
git clone <dépôt> $env:TEMP\essai
cd $env:TEMP\essai
uv sync
uv run obqo valider exemples\maison.json
uv run obqo calepiner exemples\maison.json -o sortie\
```

`uv sync` règle tout : Python, les dépendances, les roues Windows d'OR-Tools,
ReportLab, ezdxf et trimesh. Il n'y a **ni compilateur ni bibliothèque système à
installer** — c'est une des raisons du choix de cette pile.

### Se passer de `uv`

C'est possible, à une condition : l'application demande **Python 3.12 ou plus**,
et la base d'une installation Anaconda est souvent en dessous.

```powershell
python --version                       # 3.12 ou plus, sinon restez sur uv
python -m venv .venv
.venv\Scripts\pip install -e ".[solveur,dessins,volume,web]"
.venv\Scripts\obqo valider exemples\maison.json
```

En dessous de 3.12, pip refuse net :

```
ERROR: Package 'obqo' requires a different Python: 3.11.15 not in '>=3.12'
```

Gardez alors `uv` : il télécharge son propre Python et ne touche pas à votre
installation. Cette liste d'extras a été vérifiée — elle produit le dossier
complet, PDF, DXF et GLB compris, exactement comme `uv sync`.

### Les quatre niveaux, en PowerShell

| Niveau | Commande |
|---|---|
| suite de tests | `uv run pytest -m "not lent"` |
| clone neuf | `git clone <dépôt> $env:TEMP\essai` puis `uv sync` |
| installation minimale | `python -m venv .venv` ; `.venv\Scripts\pip install -e .` ; `.venv\Scripts\obqo.exe valider exemples\maison.json` |
| navigateur | `uv run obqo web` puis <http://127.0.0.1:8000> |

Le seul vrai piège est le troisième : sous Windows l'environnement virtuel range
ses exécutables dans **`.venv\Scripts\`** et non `.venv/bin/`, et le binaire
s'appelle `obqo.exe`. Le reste de la consigne tient : appelez-le directement,
`uv run` réinstallerait tous les extras et l'essai ne voudrait plus rien dire.

### Lancer l'interface web

```powershell
cd $env:TEMP\essai
uv run obqo web
Start-Process http://127.0.0.1:8000    # ou collez l'adresse dans Edge
```

`Ctrl+C` arrête le serveur. Tant qu'il tourne il occupe la fenêtre PowerShell :
ouvrez-en une seconde pour continuer à taper des commandes.

| Situation | Réponse |
|---|---|
| demande de pare-feu au premier lancement | refuser — le serveur n'écoute que sur `127.0.0.1` |
| port 8000 déjà pris (fréquent avec Anaconda) | `uv run obqo web --port 8080` |
| y accéder depuis un téléphone ou un autre poste | `uv run obqo web --hote 0.0.0.0`, et accepter le pare-feu |
| `Interface web indisponible` | `uv sync --extra web` |

Rien n'est persisté : les études vivent en mémoire, les huit dernières, et
fermer le serveur les efface. C'est à cela que sert le bouton *Enregistrer* de
l'esquisse, qui rend un fichier YAML à garder.

### Ce qui a été corrigé pour Windows

Deux défauts n'apparaissaient que là, et aucun test ne les voyait :

- **Les CSV s'ouvraient de travers dans Excel.** Un fichier en UTF-8 sans marque
  d'ordre des octets est lu en cp1252 par Excel : « Débit » devenait
  « DÃ©bit ». Les CSV sortent maintenant en `utf-8-sig` — la marque ne gêne
  aucun autre lecteur, Python, LibreOffice et pandas la retirent seuls. Le
  séparateur est déjà le point-virgule, celui qu'attend un Excel français.
- **Les fichiers texte perdaient leur déterminisme.** `write_text` traduit les
  fins de ligne selon la plateforme : le même plan sortait en CRLF sous Windows
  et en LF ailleurs, donc deux fichiers différents. `calepinage.json`,
  `rapport.txt`, les SVG et le gabarit sont désormais écrits en `newline="\n"`,
  et un test le vérifie.

Le reste du code était déjà portable : aucun chemin en dur, `pathlib` partout,
`tempfile.gettempdir()` plutôt que `/tmp`, et tous les fichiers lus et écrits
avec un `encoding=` explicite. C'est vérifiable :

```powershell
uv run pytest -m "not lent"       # les 186 tests doivent passer tels quels
```

### Ce qui reste à vérifier sur une vraie machine

Contrairement à la section Ubuntu, celle-ci vient d'un audit du code et des
équivalents PowerShell, pas d'une exécution sous Windows 11 — l'application n'y a pas encore tourné. Restent donc
à confirmer par quelqu'un qui l'a sous la main : le rendu des accents dans
Windows Terminal, l'ouverture des CSV dans un Excel réellement installé, et
l'affichage des SVG dans Edge.

## Ce que rien ne teste encore

- Le rendu des DXF dans un vrai logiciel de CAO : on vérifie la structure du
  fichier, pas ce qu'un opérateur voit à l'écran.
- L'impression des A3 sur du papier : la pagination est testée, pas la lisibilité
  des repères portés sur les briques.
- Et surtout, ce qu'aucun logiciel ne saura tester : le calepinage produit est un
  document de calepinage, pas une note de calcul. Le dimensionnement structural
  reste à valider par un bureau d'études bois (Eurocode 5, sismique).
