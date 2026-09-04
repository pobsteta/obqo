# Brief — module `structure` : justifier l'entraxe des poteaux raidisseurs

Ce brief accompagne le patch `0001-feat-structure-*.patch` et l'archive
`obqo-structure.zip` déposés dans ce dossier. Le code existe, il est testé ;
ta tâche est de l'**intégrer proprement dans le dépôt**, de le relire face
aux règles du projet, et de le prolonger sur les points listés au §5. Tu ne
réinventes pas le module, tu le fais rentrer dans la maison.

Lis d'abord, dans cet ordre : `README.md`, `docs/00-choix-techniques.md`,
`docs/hypotheses.md` (D6 en particulier), `src/obqo/units.py`,
`src/obqo/rules/catalogue.py`, `src/obqo/engine/raidissement.py`.

---

## 1. Ce que le problème est réellement

Le brief constructif (§1.7) fixe **un poteau raidisseur P10 tous les 6 m** de
mur sans refend ni jambage. `units.ENTRAXE_MAXI_RAIDISSEUR = 6000` le fige, et
`engine/raidissement.py` pose les poteaux qui manquent. Personne ne sait d'où
vient ce 6 m.

Le module `structure/` répond à la question par le calcul : *quel est le plus
long pan de maçonnerie qui tient, au vent et sous la toiture, entre deux P10 ?*
Il ne remplace pas le bureau d'études ; il lui donne une note lisible, avec
ses hypothèses en tête, à signer ou à contredire. Chaque plan produit porte
déjà la mention « à valider par un bureau d'études bois » : ce module est ce
qu'on lui tend avec le plan.

Trois natures de choses cohabitent, et il faut les tenir séparées :

| Nature | Où ça vit | Qui peut le changer |
|---|---|---|
| Valeurs de **norme** (EN 338, EN 1995-1-1) | `structure/materiaux.py`, en tables avec le numéro de tableau | personne, sauf changement de norme |
| Valeurs **d'essai** (efficacité d'un rang, résistance d'une C1) | `Hypotheses`, défauts prudents et commentés | le résultat d'un essai |
| Le **modèle** (grillage, appuis, combinaisons) | `structure/modele.py` | le BE, s'il conteste le schéma statique |

---

## 2. Règles du projet qui s'appliquent ici

- **Tables, pas d'algorithmes** dans `materiaux.py`. Aucune valeur numérique
  de norme ailleurs que là. `eurocode5.py` ne contient que des formules.
- **PyNite ne s'importe que dans `modele.py`**, à l'intérieur de la fonction.
  `materiaux` et `eurocode5` restent importables avec la seule bibliothèque
  standard, comme `engine`, `rules` et `bom`.
- **Le cœur reste entier.** Ce module est le seul endroit d'obqo où des
  flottants sont légitimes (contraintes, flèches). Ils n'en sortent pas : ce
  qui revient vers `engine` est un entier de millimètres multiple de 240.
- **Sortie déterministe.** Même hypothèses, même note, octet pour octet.
- **Pas d'hypothèse silencieuse.** Ce qui n'est pas dans le brief est dans
  `Hypotheses` avec un docstring qui dit d'où vient le défaut et comment le
  mesurer. Si tu dois inventer, tu poses une question dans
  `docs/hypotheses.md` plutôt que de choisir.
- Style : français sans accents dans le code et les docstrings (comme le
  reste du dépôt), ruff et mypy strict verts, tests avec pytest.

---

## 3. Ce que le patch livre déjà

```
src/obqo/structure/
  __init__.py
  materiaux.py   classes C18/C24/C30/D30 (EN 338), gamma_M, k_mod (tab. 3.1),
                 beta_c, dataclass Hypotheses
  eurocode5.py   Section, resistance_de_calcul, elancement_relatif,
                 coefficient_flambement (6.3.2), taux_compression_flexion,
                 taux_flexion, taux_cisaillement, taux_cheville, taux_fleche
  modele.py      calculer(pan, hyp) -> Efforts : grillage PyNite
  entraxe.py     verifier(pan, hyp) -> Verification ; entraxe_maxi(hyp) ;
                 note(v, hyp) -> list[str]
tests/test_structure.py   13 tests
src/obqo/cli.py           commande `obqo entraxe`
pyproject.toml            extra `structure = ["PyNiteFEA>=1.0"]`, ajouté a `complet`
README.md                 section « Justification structurale »
```

Schéma statique du modèle (à relire, pas à deviner) :

- Axes : X le long du mur, Y vertical, Z hors du plan.
- Chaque rang de 240 est une poutre 240 × 240 d'inertie hors-plan réduite par
  `efficacite_rang`, **articulée** sur les deux poteaux (`Ry` libéré aux deux
  bouts). Elle reçoit le vent sur 240 de hauteur.
- Chaque poteau est une poutre 80 × 240 continue du pied à la tête, articulée
  en pied (DX DY DZ RY tenus) et tenue en tête par la lisse (DX DZ). Il reçoit
  le vent de son propre module de 240 et, en tête, la charge verticale
  `charge_verticale × part_poteau × portée`.
- Portée de calcul : d'axe à axe des P10, soit `pan + MODULE_POTEAU`
  (enveloppe : le remplissage de 160 est chevillé au poteau).
- Combinaisons : ELU = 1,5 vent + 1,35 permanent ; ELS = 1,0 vent.
- Vérifications sur le poteau : compression + flexion avec flambement hors
  plan sur la hauteur (section 80 × 240, 240 dans le plan de flexion) ;
  flambement dans le plan sur 240 mm (le mur le tient à chaque rang) ; flèche.
  Sur le rang : flexion (résistance réduite par la même efficacité),
  cisaillement, flèche. Sur la liaison : réaction du rang / résistance de
  calcul des C1.

Ordres de grandeur obtenus (pour te dire si tu as cassé quelque chose) :

```
obqo entraxe                                 → pan admis 10 800 mm, critère flèche du rang
obqo entraxe --vent 1.1 --efficacite 0.1     → pan admis  6 480 mm, critère flèche du rang
obqo entraxe --pan 6000                      → admis, taux maxi 0,43 (chevilles)
```

---

## 4. Ta tâche, dans l'ordre

1. **Appliquer le patch** (`git am specs/structure/0001-*.patch`) sur une
   branche `feat/structure`. Si `git am` refuse à cause d'un conflit de
   contexte dans `cli.py` ou `README.md`, reprends les fichiers du zip et
   refais l'intégration à la main ; ne réécris pas le module.
2. **Faire tourner** `uv sync --extra structure`, `uv run pytest`,
   `uv run ruff check`, `uv run mypy`. Tout doit être vert, y compris
   `test_debit` et `test_web` qui n'ont pas pu être lancés à la rédaction du
   patch (ortools et fastapi absents de l'environnement).
3. **Relire le modèle** face à D6 et au §1.7 du brief constructif, et écrire
   ce que tu en penses dans `docs/etudes/structure.md` (crée le fichier) :
   ce que le schéma statique suppose, ce qu'il ignore, ce qu'un BE risque de
   contester. Pas de complaisance : si le grillage te paraît trop simple,
   dis-le et dis pourquoi.
4. **Ajouter D7 à `docs/hypotheses.md`** : « l'entraxe des raidisseurs est
   une valeur calculée, `ENTRAXE_MAXI_RAIDISSEUR` reste la valeur du brief
   tant qu'aucun essai n'a fixé `efficacite_rang` et `resistance_cheville_k` ».
   Liste sous D7 les deux essais à faire, avec ce qu'ils mesurent et combien
   d'éprouvettes.
5. **Prolonger**, voir §5.

---

## 5. Prolongements demandés

### 5.1 `obqo entraxe PLAN` — la note par pan réel

Aujourd'hui la commande travaille sur un pan abstrait. Ajoute la forme
`obqo entraxe PLAN` : calepiner le plan, puis pour **chaque pan de chaque mur
extérieur** (entre deux coupures au sens de `raidissement.coupures`), lancer
`verifier` avec la hauteur réelle du plan et imprimer un tableau
`mur | pan (mm) | critère dimensionnant | taux | admis`. Sortie non nulle si un
pan est refusé. Les hypothèses restent des options de la commande ; ne les
mets pas dans le schéma de plan pour l'instant (voir 5.4).

Les pans intérieurs (refends) ne reçoivent pas de vent : saute-les et dis-le
dans le rapport.

### 5.2 Deux chevilles par rang, décalées

D6 ne lie le poteau que d'un côté (la C1 de 230 traverse 80 de P10 et 160 de
remplissage). La discussion a retenu l'option **deux C1 par rang, décalées
en hauteur** : ligne 1 vers le mur de gauche, ligne 3 vers le mur de droite,
chacune 80 dans le poteau et 150 dans l'about voisin.

- `catalogue.RAIDISSEUR_PAR_RANG` passe de `C1: 1` à `C1: 2` ; mets à jour le
  docstring, le test de catalogue et les constantes de métré de contrôle
  croisé si elles en dépendent.
- `Hypotheses.chevilles_par_rang` prend 2 par défaut, cohérent avec le
  catalogue : **une seule source de vérité**, le calcul lit le catalogue, il
  ne duplique pas le nombre.
- Ajoute dans `engine` (ou là où c'est le plus naturel) une vérification que
  la cheville de 150 tombe dans du plein et non dans une mortaise, selon la
  parité du rang (about = tenon P5 ou carré P8). Si tu ne peux pas le
  déterminer avec le modèle actuel, ouvre une question dans
  `docs/hypotheses.md` au lieu de supposer.

### 5.3 La note dans le dossier

`obqo calepiner` écrit déjà `rapport.txt`. Quand l'extra `structure` est
installé, ajoute `structure.txt` dans le dossier de sortie : les hypothèses,
puis la note par pan (5.1). Quand il ne l'est pas, une ligne dans
`rapport.txt` dit que la justification n'a pas été produite et pourquoi.
Le `dossier.pdf` n'est pas concerné pour l'instant.

### 5.4 Question à poser, pas à trancher

Faut-il que le plan JSON porte ses hypothèses de calcul (zone de vent,
charge de toiture) ? C'est tentant et c'est probablement juste, mais ça
change le schéma versionné. Écris le pour et le contre dans
`docs/etudes/structure.md` et propose ; n'implémente pas.

---

## 6. Critères d'acceptation

- [ ] `uv run pytest` vert, `ruff` et `mypy --strict` verts, avec et sans
      l'extra `structure` installé (sans : `test_structure` est *skipped*,
      `obqo entraxe` sort en 2 avec un message clair).
- [ ] `obqo entraxe --pan 6000` reste admis avec les défauts.
- [ ] `obqo entraxe exemples/maison.json` imprime un tableau avec tous les
      pans extérieurs de la maison d'exemple ; deux exécutions donnent la
      même sortie.
- [ ] `RAIDISSEUR_PAR_RANG["C1"] == 2` et le calcul le lit depuis le
      catalogue.
- [ ] `docs/hypotheses.md` a un D7 ; `docs/etudes/structure.md` existe et
      contient une critique du modèle et la question 5.4.
- [ ] Aucun flottant n'a franchi la frontière vers `engine`, `rules`, `bom`.
- [ ] Commits conventionnels, un par sujet (`feat(structure): …`,
      `docs: …`), puisque `outils/version.py` écrit le CHANGELOG à partir
      d'eux.

---

## 7. Ce que tu ne fais pas

- Tu ne calcules pas le vent selon l'EN 1991-1-4 (zones, rugosité, altitude).
  `pression_vent` reste une entrée ; le BE la fournit.
- Tu ne fais pas de sismique.
- Tu ne justifies pas la cheville hêtre par Johansen : l'EC5 traite les
  tiges en acier, et le 3 kN par défaut est une borne basse issue du
  cisaillement du hêtre, explicitement à remplacer par un essai.
- Tu ne mets pas Code_Aster, numpy ni scipy dans le dépôt.
- Tu n'écris pas dans `CHANGELOG.md` à la main.
