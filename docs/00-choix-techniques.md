# BRIQ — Choix techniques recommandés

Document de décision préalable à l'implémentation. Il répond à la question :
*quelles technologies pour construire l'application de calepinage BRIQ ?*
Il ne discute aucune règle constructive : celles du brief sont la source de vérité.

---

## 0. Ce que le problème est réellement

Avant de choisir des outils, il faut nommer la nature du problème, parce qu'elle
détermine tout le reste :

| Ce qu'on croit | Ce que c'est vraiment |
|---|---|
| « de la géométrie CAO » | de la **combinatoire sur entiers** : tout est sur une grille de 80 mm, tous les angles sont à 90°, aucune coordonnée n'est irrationnelle |
| « un problème d'optimisation lourd » | un **cutting-stock à 4 longueurs distinctes** → 761 patrons de découpe possibles, donc résoluble **exactement** |
| « un générateur de dessins » | un **compilateur** : plan JSON → AST (rangs/briques) → back-ends (nomenclature, SVG, PDF, débit) |

Trois conséquences directes, qui valent plus que n'importe quel choix de librairie :

1. **Zéro flottant dans le cœur.** Toutes les longueurs sont des `int` en millimètres.
   Pas de `float`, pas d'epsilon, pas de `math.isclose`. Un mur de 10 800 mm fait
   45 modules de 240, exactement. C'est la décision qui supprime le plus de bugs
   sur ce projet.
2. **Pas de moteur géométrique.** Ni CGAL, ni OpenCASCADE, ni numpy dans `engine`.
   Un rang est une liste de briques posées bout à bout ; un angle est une règle de
   priorité entre deux murs. Tout est de l'arithmétique entière et des tables.
3. **Architecture de compilateur.** Un modèle intermédiaire unique (la liste des
   briques posées + pièces de chantier) alimente *tous* les livrables. On ne
   recalcule jamais la nomenclature à partir des dessins, ni l'inverse.

---

## 1. Socle

| Choix | Recommandation | Pourquoi |
|---|---|---|
| Langage | **Python 3.12** (3.13 possible) | Le brief a raison. C'est le seul écosystème où l'on trouve *au même endroit* un solveur industriel (OR-Tools), l'export DXF (ezdxf), le PDF vectoriel (ReportLab) et le test à propriétés (Hypothesis). TypeScript ferait le calepinage mais pas le débit optimal ni le DXF. |
| Packaging / venv / lock | **uv** | Standard de fait aujourd'hui, résolution en millisecondes, `uv.lock` reproductible, `uv run briq …` sans activer d'environnement. Remplace pip + venv + pip-tools + pipx. |
| Lint + format | **ruff** (`ruff check`, `ruff format`) | Un seul outil au lieu de flake8 + isort + black. |
| Typage | **mypy --strict** (ou pyright) sur `model/` et `engine/` | Sur un domaine où l'on manipule des `Millimetres`, des `Module` et des `IndiceDeRang` qui sont tous des `int`, le typage nominal (`NewType`) attrape les inversions d'unités à la compilation. |
| CI | GitHub Actions : `ruff` + `mypy` + `pytest` + génération de la maison d'exemple | Le test d'intégration doit tourner à chaque commit : c'est lui qui protège les ~1 000 briques. |

**Unités — à faire dès la première ligne :**

```python
from typing import NewType
Mm = NewType("Mm", int)          # millimètres, toujours entiers
Module = NewType("Module", int)  # multiples de 80
Grille = NewType("Grille", int)  # multiples de 240 (grille de calepinage)
```

---

## 2. Modèle de données et format d'entrée

### 2.1 Pydantic v2 plutôt que dataclasses + jsonschema

**Recommandation : Pydantic v2** pour la frontière d'entrée (le plan), et des
`@dataclass(frozen=True, slots=True)` pour les types internes du moteur.

Ce que Pydantic apporte ici, et qui n'est pas du confort :

- **Le JSON Schema versionné du brief est gratuit** : `Plan.model_json_schema()`
  produit `schemas/briq-plan-v1.schema.json`. On le commite, et la CI vérifie
  qu'il est à jour. Le fichier plan porte alors un `"$schema": "…v1.schema.json"`
  → **autocomplétion et validation en direct dans VS Code pendant qu'on saisit le
  plan à la main.** Pour un format saisi au clavier par un autoconstructeur,
  c'est la fonctionnalité la plus rentable de tout le projet.
- Les validateurs métier (`multiple de 240`, `rive de baie ≥ 480 d'un angle`)
  s'écrivent comme `field_validator` / `model_validator` et remontent des erreurs
  **localisées** (`murs[2].ouvertures[0].largeur`), ce qui est exactement le
  « rapport de validation » demandé en §2.3.4.
- Le paramètre « arrondir ou refuser » du §1.1 se modélise proprement par un
  mode de validation (`strict` / `arrondi`) porté par le contexte de validation.

### 2.2 Deux points où je conteste le format d'entrée du brief

**(a) Accepter aussi le YAML.** Le JSON est le bon format *canonique* (schéma,
outillage, diff). Mais un plan de maison écrit à la main sans commentaires est
inconfortable : on veut écrire `# fenêtre de la cuisine, alignée sur l'évier`.
Recommandation : parser YAML **et** JSON vers le même modèle Pydantic ; le JSON
reste la référence pour le schéma et les tests.

**(b) Offrir une saisie « tortue » en plus de la polyligne.** Saisir un contour
fermé en coordonnées absolues est une source d'erreurs (le dernier point doit
retomber pile sur le premier). Une écriture par déplacements relatifs :

```yaml
contour:
  depart: [0, 0]
  trace: [ {est: 13920}, {nord: 10800}, {ouest: 13920}, {fermer: true} ]
```

garantit la fermeture par construction, se relit comme un métré de chantier, et
se convertit trivialement en polyligne absolue. Les deux formes cohabitent dans
le même schéma (`oneOf`). À valider avec toi, mais je le recommande.

**(c) Identifiants stables.** Chaque mur, baie, rang et brique doit porter un
identifiant déterministe (`M2.R07.B04`), calculé et non aléatoire. C'est ce qui
rend les sorties diffables entre deux exécutions et ce qui permet aux plans, à la
nomenclature et aux instructions de pose de se référencer mutuellement.

---

## 3. Moteur de calepinage

**Recommandation : aucune dépendance.** `engine/` doit être du Python pur,
importable sans rien installer. C'est le module qu'on relira dans trois ans.

Une seule exception envisageable : **shapely**, et uniquement pour valider le
*contour* du plan (polygone simple, non auto-intersectant, orientation,
appartenance d'un refend à l'intérieur). C'est ~30 lignes de code délicat qu'on
n'a pas envie d'écrire soi-même. Si le contour v1 est un rectangle ou une forme
en L, on peut même s'en passer et l'ajouter plus tard.

Structure interne conseillée (au-delà du découpage `model / engine / bom /
drawings / cli` du brief, qui est correct) :

```
briq/
  model/        types du plan (Pydantic) + types du système (dataclasses gelées)
  rules/        LES RÈGLES MÉTIER, isolées : catalogue de briques, tables de
                pièces par référence, constantes de métré (§1.8), tenons,
                chevilles. Aucune logique de placement.
  engine/       placement : rangs, appareillage, angles, baies, raidisseurs
  bom/          nomenclature + métré + débit
  drawings/     modèle de dessin (IR) + back-ends SVG/PDF/DXF
  cli/
```

L'intérêt d'un module `rules/` séparé d'`engine/` : la table « la 480-ANR contient
1×P5-A, 4×P2, 2×P1, 1×P3, 2×P4, 2×P6, 1×P8, 6×C1… » est une **donnée**, pas du
code. Elle doit être lisible d'un coup d'œil et comparable au brief ligne à ligne
par toi, sans lire d'algorithme. Le jour où une règle d'atelier change, on modifie
une table, pas une fonction.

---

## 4. Débit de matière — le point où je recommande mieux que le brief

Le brief prévoit *first-fit decreasing* en v1. **FFD est inutile ici : le problème
est petit et exactement soluble.**

Vérification faite : pour une barre de 4 000 mm, un trait de scie de 4 mm et les
longueurs {80, 160, 240, 480} du carrelet 80×80, il existe **761 patrons de
découpe maximaux**. C'est minuscule.

**Recommandation : formulation de Gilmore-Gomory par énumération exhaustive des
patrons, résolue par OR-Tools CP-SAT.**

```
minimiser   Σ barres[p]
sous        Σ_p patron[p][L] · barres[p] ≥ demande[L]   pour chaque longueur L
            barres[p] ∈ ℕ
```

761 variables entières, 4 contraintes. CP-SAT rend l'optimum en quelques
millisecondes — pas une approximation, **l'optimum**. Sur ~25 000 pièces à
débiter, l'écart FFD/optimum se compte en dizaines de barres, donc en centaines
d'euros et en volume de chutes à évacuer. Ça justifie la dépendance.

Trois raffinements que la formulation exacte permet gratuitement, et pas FFD :

1. **Objectif lexicographique** : d'abord minimiser le nombre de barres, puis, à
   nombre de barres égal, maximiser la longueur des chutes **réutilisables**
   (≥ 240 mm) plutôt que de la disperser en poussière de 60 mm.
2. **Trait de scie explicite** (4 mm par coupe, pas une « marge de chute » globale) —
   c'est déjà dans le calcul ci-dessus.
3. **Minimiser le nombre de patrons distincts** en second objectif : 12 patrons à
   répéter, c'est une journée d'atelier sereine ; 300 patrons différents, c'est
   une journée d'erreurs. **Un plan de débit optimal mais illisible est un mauvais
   plan de débit.** C'est un vrai critère, pas un détail.

Garde l'interface `Solveur` du brief : `resoudre(demandes, stock) -> PlanDeDebit`,
avec deux implémentations (`FFD` sans dépendance comme repli et référence de test,
`CpSat` par défaut). OR-Tools reste alors une dépendance optionnelle (`extras`).

Le carrelet 80×80, les madriers 80×240 (P9), les jambages P10 et les lisses sont
des **stocks distincts** : le solveur tourne une fois par section.

---

## 5. Dessins — refonte de l'approche du brief

Le brief propose `svgwrite` + `cairosvg`. Je recommande autre chose, pour deux
raisons concrètes : `cairosvg` impose des bibliothèques système (libcairo,
pango) pénibles à installer et rend mal le texte, et il **ne produit pas de PDF
multi-pages** — or on veut un dossier A3 relié, pas 14 fichiers séparés.

**Recommandation : un modèle de dessin intermédiaire + trois back-ends.**

```
engine → DrawingIR (Ligne, Rect, Polyligne, Texte, Cote, Hachure, Calque)
              ├── back-end SVG   → xml.etree.ElementTree (stdlib, 0 dépendance)
              ├── back-end PDF   → ReportLab (pur Python, multi-pages A3, vectoriel)
              └── back-end DXF   → ezdxf (bonus, voir §5.2)
```

Ce que ça achète :

- **Testabilité.** On teste l'IR (« l'élévation du mur M2 contient 45 rectangles de
  brique et 2 cotes ») au lieu de comparer des chaînes de SVG. Les tests de
  non-régression deviennent lisibles.
- **Pas de dépendance système.** ReportLab est du Python pur : `uv sync` suffit,
  sur Linux comme sur Windows. Aucun `apt install libcairo2`.
- **Vrai dossier PDF A3** paginé, avec cartouche, numérotation, et la mention
  obligatoire du §3 (« Document de calepinage — dimensionnement structural à
  valider par un bureau d'études bois ») posée **par le back-end**, donc
  impossible à oublier sur une page.
- Une couche de dessin technique à écrire une fois (cotation, hachures, repères)
  et réutilisée par les élévations, les plans de rang et les fiches de débit.

Coût honnête : ~300 lignes de back-end SVG et ~300 de back-end PDF. C'est le prix
de ne jamais se battre contre cairo.

### 5.1 Typographie et échelle

Élévations au 1:50 sur A3 (420×297) : un mur de 13,92 m fait 278 mm sur la
feuille. Ça passe. Prévoir dès l'IR la **pagination automatique** (découpe d'un
mur trop long en plusieurs A3 avec zone de recouvrement), sinon c'est une
réécriture plus tard. Polices : Helvetica intégrée à ReportLab côté PDF, pile
générique `sans-serif` côté SVG — ne pas embarquer de police exotique.

### 5.2 Ajouter un export DXF (ezdxf) — fortement recommandé

Ce n'est pas dans le brief, et c'est probablement le meilleur rapport
valeur/effort du projet. `ezdxf` est du Python pur, très mûr. Un export DXF te
donne :

- l'ouverture des plans dans n'importe quel logiciel de CAO (LibreCAD, QCAD,
  AutoCAD) pour annoter, mesurer, imprimer à l'échelle exacte ;
- un format que **le bureau d'études bois attend** (le brief impose de faire
  valider le dimensionnement — autant lui envoyer du DXF, pas des PDF) ;
- la porte ouverte au perçage/usinage assisté plus tard.

Une centaine de lignes à partir de l'IR. À faire au jalon 3.

### 5.3 Un export 3D, presque gratuit

Chaque pièce du système est un **parallélépipède aligné sur les axes** (80×80×240,
80×80×480, 80×240×h…) percé de cylindres ø20. C'est le cas le plus simple qui
existe en 3D. Avec **trimesh** (ou un écrivain glTF maison de 150 lignes), la
liste des pièces posées devient un fichier `.glb` ouvrable dans n'importe quel
visualiseur.

Pourquoi ça compte : **le harpage croisé alterné des angles (§1.5) est le point du
système le plus difficile à vérifier sur une élévation 2D.** Une vue 3D éclatée de
la colonne d'angle, rang par rang, te dira en dix secondes si le tenon P5-A tombe
bien en face de sa réception — vérification qui coûterait une soirée d'atelier
autrement. À traiter comme un outil de débogage du moteur, pas comme un livrable.

**À ne pas faire en v1** : CadQuery / build123d / OpenCASCADE (dépendance
colossale, temps de calcul, aucun gain — on n'a que des boîtes), et IFC
(`ifcopenshell`) tant qu'aucun BE ne l'a explicitement demandé.

---

## 6. CLI et sorties

| Besoin | Choix | Note |
|---|---|---|
| CLI | **Typer** | Sous-commandes (`briq valider`, `briq calepiner`, `briq debiter`), aide générée, complétion shell. `argparse` conviendrait aussi si tu tiens au zéro-dépendance. |
| Affichage terminal | **Rich** | Le « tableau lisible » du §2.3.1 et le rapport de validation en couleur (erreur/avertissement). Vient avec Typer. |
| CSV | `csv` (stdlib) | Rien de plus. |
| Classeur XLSX | **openpyxl** *(optionnel)* | Un classeur à onglets (nomenclature / débit / métré / chiffrage) est bien plus commode qu'un CSV pour aller discuter prix chez le scieur. Vaut la dépendance. |
| Instructions de pose | **Jinja2** | Le texte du §2.3.2 (« ordre de pose, chevilles par rang, tenons à couper ») est du gabarit ; ne le construis pas par concaténation. |
| Chiffrage | `decimal.Decimal` | Jamais de `float` sur de l'argent, comme jamais sur des millimètres. |

**Sortie déterministe.** Deux exécutions sur le même plan doivent produire des
fichiers **octet pour octet identiques** (tri stable, pas d'horodatage dans les
fichiers, pas d'itération sur des `set`). Sans ça, aucun test de non-régression
sur les dessins n'est possible, et on ne peut pas voir ce qu'un changement de
règle a modifié.

---

## 7. Tests — là où se joue la fiabilité

Le brief demande des tests unitaires classiques. Ils sont nécessaires mais ne
suffisent pas pour un moteur combinatoire.

| Niveau | Outil | Ce qu'il attrape |
|---|---|---|
| Unitaire | **pytest** | Les comptages à la main du §2.5 (mur droit, mur avec baie, angle : 1/1/1/2 par rang). |
| **Propriétés** | **Hypothesis** | Le vrai filet de sécurité. Voir ci-dessous. |
| Non-régression | **syrupy** (snapshots) | Nomenclature et IR de dessin figés ; toute dérive apparaît en diff lisible. |
| Intégration | pytest | La maison d'exemple : ~1 000 briques, ~110 m², ~8,7 briques/m². |
| Erreurs | pytest | Le plan volontairement fautif produit les bons messages. |

**Le test à propriétés est le point clé.** Sur des murs de longueur aléatoire
(multiples de 240), avec des baies placées aléatoirement, le moteur doit
respecter des invariants qu'on peut vérifier automatiquement sur des milliers de
cas :

- la somme des longueurs de briques d'un rang **égale exactement** la longueur du mur ;
- deux briques d'un même rang ne se chevauchent jamais et ne laissent aucun vide ;
- **aucun joint vertical du rang *n* ne coïncide avec un joint du rang *n+1*** (règle §1.5) ;
- toute poche ouverte est soit fermée par un P8, soit occupée par un raccord P6 ;
- tout tenon P5 a une réception en face au rang supérieur, et réciproquement ;
- le total de carrelet du métré = Σ des longueurs de la nomenclature (cohérence croisée §1.8) ;
- le plan de débit couvre exactement la demande, sans dépassement de barre.

Hypothesis va trouver les cas limites (mur de 240 mm exactement, baie collée au
raidisseur, mur de longueur impaire en modules qui casse l'alternance du
harpage) que ni toi ni moi n'écrirons à la main. Sur un système constructif réel
où une erreur se paie en heures d'atelier, c'est l'investissement le plus
rentable du projet.

Ajoute aussi une **cohérence dimensionnelle croisée** en test permanent : la
masse totale calculée par pièce doit correspondre à ±1 % au ratio du §1.8
(4,16 m de carrelet par brique 480). Un écart signale une erreur de table, pas
une erreur d'arrondi.

---

## 8. Interface web (jalon ultérieur)

Le brief dit Flask. **Recommandation : FastAPI + HTMX + Jinja2**, pas de SPA.

- Le SVG est déjà généré côté serveur : on l'injecte dans la page, HTMX
  rafraîchit le fragment quand on change un paramètre. Zéro build front, zéro
  npm, zéro bundler.
- FastAPI plutôt que Flask parce que les modèles Pydantic du plan sont
  **directement** les modèles d'API : la validation, la doc OpenAPI et le
  formulaire de saisie découlent du même schéma que la CLI. Avec Flask il faut
  tout redéclarer.
- **Streamlit** est le chemin le plus court si tu veux un prototype visuel en une
  soirée, mais ça devient vite un plafond (mise en page contrainte, état global
  fragile). À utiliser comme jouet d'exploration, pas comme cible.

Contrainte à tenir : **le cœur ne doit rien savoir du web.** La CLI et le web sont
deux clients du même `briq.engine`. C'est déjà ce que dit le brief, c'est juste.

---

## 9. Récapitulatif des dépendances

```toml
[project]
requires-python = ">=3.12"
dependencies = [
  "pydantic>=2.9",     # schéma d'entrée + JSON Schema versionné
  "typer>=0.15",       # CLI (embarque click + rich)
  "reportlab>=4.2",    # PDF A3 multi-pages, pur Python
  "jinja2>=3.1",       # instructions de pose
]

[project.optional-dependencies]
solveur = ["ortools>=9.11"]   # débit exact (repli FFD sans dépendance)
cao     = ["ezdxf>=1.3"]      # export DXF pour le BE bois
tableur = ["openpyxl>=3.1"]   # classeur nomenclature/métré
3d      = ["trimesh>=4.5"]    # vérification visuelle du harpage
dev     = ["pytest", "hypothesis", "syrupy", "mypy", "ruff"]
```

Le SVG n'a **aucune** dépendance (`xml.etree` de la stdlib). `engine/` et `rules/`
n'en ont aucune non plus. Tout le reste est optionnel : l'application doit
fonctionner en mode dégradé (`pip install briq` seul) et produire nomenclature,
métré FFD et plans SVG.

---

## 10. Ce que je recommande de ne pas utiliser

| Écarté | Raison |
|---|---|
| `cairosvg` | Dépendances système, texte mal rendu, pas de PDF multi-pages. |
| `svgwrite` | Peu maintenu, et n'apporte rien face à `ElementTree` une fois qu'on a un IR de dessin. |
| `matplotlib` | Ce n'est pas un outil de dessin technique : cotation, échelles exactes et typographie de plan y sont un combat. |
| `numpy` | Aucun calcul vectoriel ici. Des `int` et des listes. |
| Base de données | JSON en entrée, fichiers en sortie. Aucun état à persister. |
| CadQuery / OpenCASCADE | Dépendance énorme pour ne modéliser que des boîtes. |
| ORM, Docker, microservices | Hors sujet pour un outil en ligne de commande mono-utilisateur. |

---

## 11. Jalons (inchangés dans l'esprit, précisés)

1. **Modèle + règles + moteur + tests** — Pydantic, `rules/` en tables, moteur pur,
   pytest **et** Hypothesis dès ce jalon. Sortie : le modèle de briques posées, en JSON.
2. **Nomenclature + métré + débit** — CSV/Rich, puis CP-SAT avec objectif
   lexicographique et trait de scie.
3. **Dessins** — IR de dessin, back-end SVG, back-end PDF A3, puis DXF. Export
   3D de débogage pour valider les angles.
4. **CLI + maison d'exemple + README** — Typer, schéma JSON publié, `uv run` en
   trois commandes.

---

## 12. Questions ouvertes qui influencent la technique

Aucune ne bloque le jalon 1 ; elles cadrent les jalons 2 et 3.

1. **Longueur de barre et trait de scie** — le brief fixe la barre à 4 m et parle
   d'une « marge de chute » globale. Je recommande de la remplacer par un **trait
   de scie explicite** (4 mm ?) plus une **longueur minimale de chute
   réutilisable** (240 mm ?). Quelles valeurs retiens-tu ?
2. **Stocks séparés** — je pars du principe que le carrelet 80×80, les madriers
   80×240 et les lisses proviennent de barres de longueurs différentes, donc de
   trois problèmes de débit indépendants. Longueurs d'approvisionnement pour les
   80×240 ?
3. **Lisibilité contre optimalité du débit** — acceptes-tu quelques barres
   supplémentaires en échange d'un nombre de patrons de découpe nettement plus
   faible (atelier plus simple, moins d'erreurs) ? Ça change la fonction objectif.
4. **Contour en v1** — rectangle et formes en L/U seulement (angles rentrants),
   ou faut-il prévoir des contours quelconques dès le départ ? Ça décide de
   l'entrée ou non de shapely et de la complexité des règles d'angle.
5. **Saisie « tortue »** (§2.2b) — je la recommande à côté de la polyligne
   absolue ; à confirmer avant de figer le schéma v1.

---

*Document de travail — les choix techniques ci-dessus n'engagent aucune
validation structurale. Tout plan produit par l'application portera la mention :
« Document de calepinage — dimensionnement structural à valider par un bureau
d'études bois (Eurocode 5, sismique) ».*
