# Brief — Code_Aster : qualifier le système obqo pour alimenter le module `structure`

Le module `structure` (PyNite + Eurocode 5) répond à *« ce mur tient-il ? »*
à condition qu'on lui donne des raideurs et des résistances qu'aucune norme ne
fournit pour un mur de briques de bois chevillées. Ce dossier dit **ce que
Code_Aster doit calculer, sur quelle géométrie, avec quels matériaux, et
comment convertir ses résultats en paramètres d'obqo.**

Un calcul n'est pas un essai : tout ce qui sort d'ici reste à confirmer sur
au moins un échantillon physique avant d'être présenté à un bureau d'études
(voir §6). Mais le calcul dit *quoi* mesurer, et donne l'ordre de grandeur
à attendre.

Contenu du dossier :

```
specs/structure/aster/
  BRIEF-aster.md                  ce document
  geometrie_echantillon.py        obqo → JSON : boîtes des pièces + axes des chevilles
  salome_echantillon.py           JSON → géométrie Salome, groupes, maillage MED  (non testé)
  E1_cheville.comm                fichier de commandes Aster de l'essai E1        (non testé)
  rang.json / cheville.json / poteau.json   exemples générés
```

---

## 1. Ce qu'on demande, et à quoi ça sert

| Calcul | Échantillon | Sortie Aster | Paramètre obqo alimenté |
|---|---|---|---|
| **E1** cheville en double cisaillement | 3 carrelets 80×80×240, 1 C1 Ø20 traversante | courbe F(u), u de 0 à 15 mm | `Hypotheses.resistance_cheville_k` (kN) et `K_ser` (N/mm, futur ressort dans le grillage) |
| **E2** rang en flexion hors-plan | 3 briques 480-S bout à bout, joints courants chevillés, abouts fermés | flèche sous charge répartie, moment à première rupture | `Hypotheses.efficacite_rang` (raideur **et** résistance) |
| **E3** liaison poteau–rang | 1 P10 sur 3 rangs, 2 briques par rang, 2 C1 décalées par rang | raideur et résistance de la liaison en translation hors-plan | remplace l'articulation parfaite du grillage par un ressort ; vérifie le 3 kN par cheville dans sa vraie configuration |
| **E4** (optionnel) colonne de briques en compression | 3 briques empilées, tenons engagés | E équivalent vertical du mur | `part_poteau` : combien de la charge de toiture va au mur et combien au poteau |

E1 et E2 sont les deux qui changent le résultat de `obqo entraxe`. E3 vaut le
coup parce que c'est la configuration réelle des chevilles ; E4 seulement si le
BE conteste `part_poteau = 0,5`.

---

## 2. Géométrie : d'obqo vers Salome

`geometrie_echantillon.py` lit les tables du dépôt (`rules/geometrie_brique.py`,
`rules/catalogue.py`) et écrit un JSON : une boîte par pièce bois avec sa
référence et la direction de son fil, un axe par cheville. Rien n'est redessiné
à la main ; si la composition d'une brique change dans obqo, le JSON change
avec.

```bash
cd dev/obqo && uv run python specs/structure/aster/geometrie_echantillon.py rang --briques 3 -o rang.json
```

`salome_echantillon.py` lit ce JSON dans Salome, perce les boîtes, fait la
partition, crée les groupes de mailles et exporte le MED. Il est écrit sans
Salome sous la main : **à relire appel par appel** contre la doc de votre
version (9.x), en particulier `GetShapesOnShape` et la création des groupes de
faces cylindriques.

Groupes de mailles produits, et à quoi ils servent dans le `.comm` :

| Groupe | Type | Rôle |
|---|---|---|
| `P_P1`, `P_P2`, … `P_P10` | volumes | une référence de pièce ; utile pour lire les contraintes par pièce |
| `FIL_X`, `FIL_Y`, `FIL_Z` | volumes | direction du fil → `AFFE_CARA_ELEM / MASSIF / ANGL_REP` |
| `CHEVILLES` | volumes | hêtre |
| `FUT_<cheville>` / `TROU_<cheville>` | faces | paire maître/esclave du contact fût/trou |
| `APPUI_*`, `CHARGE_*`, `PAREMENT_EXT`, `PIED`, `TETE` | faces | conditions aux limites, par échantillon |

Taille de maille : 20 mm dans le bois, 8 mm sur les chevilles, tétraèdres
quadratiques. Un rang de 3 briques donne de l'ordre de 300 000 à 600 000
nœuds : compter des heures de `STAT_NON_LINE` avec contact, pas des minutes.
Si c'est trop, coller les interfaces bois/bois (les laisser partagées par la
partition) et ne garder le contact qu'au fût des chevilles : c'est ce que fait
`E1_cheville.comm`.

---

## 3. Matériaux (tableau M)

Aster veut un matériau orthotrope par essence : `ELAS_ORTH` avec E_L (fil),
E_T, E_N (travers), les trois G et les trois ν. Repère local L-T-N tourné par
`ANGL_REP` selon le groupe `FIL_*`.

| Propriété | Épicéa C24 | Hêtre (chevilles) | Source / statut |
|---|---|---|---|
| E_L | 11 000 | 14 000 | EN 338 (E_0,mean) ; hêtre : littérature, ±15 % |
| E_T = E_N | 370 | 1 100 | EN 338 (E_90,mean) ; hêtre : littérature |
| G_LT = G_LN | 690 | 1 000 | EN 338 (G_mean) |
| G_TN (roulant) | 69 | 300 | ≈ G/10 pour les résineux ; **hypothèse H-M1** |
| ν_LT = ν_LN | 0,40 | 0,45 | littérature (Kollmann, Bodig & Jayne) |
| ν_TN | 0,50 | 0,60 | idem |
| ρ | 450 kg/m³ | 700 kg/m³ | `Parametres.masse_volumique_epicea`, hêtre usuel |
| f_m,k / f_c,0,k / f_v,k | 24 / 21 / 4,0 | 60 / 45 / 10 (indicatif) | EN 338 ; hêtre : à confirmer, **H-M2** |
| f_c,90,k (portance) | 2,5 | 9 | EN 338 ; hêtre indicatif |
| f_h,k (portance locale, tige Ø20) | 0,082 (1 − 0,01·20) · 350 = 23 | — | EN 1995-1-1 §8.5.1, pour tiges acier : **à utiliser avec prudence pour une cheville bois** |
| Frottement bois/bois μ | 0,35 | 0,35 | 0,3 à 0,5 selon humidité et état de surface, **H-A6** |

Teneur en eau : prendre 12 % (classe de service 1-2, bois à l'équilibre).
Une cheville chassée plus sèche que le carrelet gonfle et se serre : c'est
ce qui fait tenir les assemblages traditionnels. Le modèle « jeu nul »
l'ignore ; l'introduire est une hypothèse (**H-A5**) : interférence
géométrique de 0,2 à 0,5 mm sur le rayon, ou précontrainte radiale.

En unités N-mm-MPa, ρ se donne en t/mm³ : 4,5e-10 pour l'épicéa.

---

## 4. Les trois calculs

### E1 — cheville en double cisaillement

*Géométrie* : `cheville.json`. Deux carrelets extérieurs P2 (fil selon y) et
un montant central P4 (fil selon z), la cheville selon y : elle est donc
parallèle au fil des traversants et perpendiculaire au fil du montant. C'est
la configuration réelle des « traversantes de montants » du §1.2.

*Conditions* : faces x = 0 des pièces extérieures bloquées ; face x = 240 de
la pièce centrale : déplacement imposé DX de 0 à 15 mm en 30 pas.

*Contact* : fût/trou, Coulomb 0,35. Interfaces bois/bois collées en première
passe (peu sollicitées), en contact frottant en seconde.

*Sorties* : `F(u)` (table `TFU`). Puis, EN 26891 :
- `K_ser` = pente entre 0,1 F_max et 0,4 F_max ;
- `F_v,R` = min(F_max, F à 15 mm).

Le bois étant élastique en première passe, il n'y a pas de F_max : on lit
F à 15 mm et l'on applique les critères de rupture à la main (tableau R). Si
l'on veut une courbe qui plafonne, on donne un comportement plastique au
hêtre (`VMIS_ISOT_LINE` avec SY ≈ f_v apparent) : c'est une modélisation, à
écrire comme telle dans le rapport.

*Conversion obqo* : `resistance_cheville_k = F_v,R / 1e3` (kN, valeur
**par cheville**, deux plans de cisaillement compris). Attendu : 3 à 8 kN.
En dessous de 2 kN, le 6 m du brief tombe.

### E2 — rang en flexion hors-plan

*Géométrie* : `rang.json`, 3 briques (1 440 mm), 2 joints courants avec leurs
raccords P6 et chevilles, abouts fermés P8. Le rang est **seul** : ni rang
dessous, ni rang dessus, tenons libres. C'est volontairement défavorable :
dans le mur, les tenons et les chevilles verticales des rangs voisins
raidissent le joint. Une variante E2b avec 3 rangs empilés dira combien.

*Conditions* : faces x = 0 et x = 1 440 bloquées en y (appuis simples,
libres en x et z sauf un nœud) ; pression uniforme sur `PAREMENT_EXT`
(y = 0), montée de 0 à 5 kN/m² (≈ 6 fois le vent de calcul, pour voir la
non-linéarité).

*Contact* : fût/trou des chevilles de joint ; interfaces P6/brique en contact
frottant (c'est là que ça travaille) ; le reste collé.

*Sorties* :
- flèche `w` au milieu (y, nœuds de la ligne médiane du parement intérieur)
  en fonction de la pression `p` ;
- contraintes σ_LL dans les âmes P3 et les raccords P6 ; σ_TT (traction
  perpendiculaire) dans les traversants P1/P2 autour des chevilles de joint ;
- glissement fût/trou aux chevilles de joint.

*Conversion obqo* — deux nombres, et on prend le plus petit :
- raideur : pour une poutre sur deux appuis sous charge répartie q = p·240,
  `EI_eff = 5 q L⁴ / (384 w)` sur la partie linéaire ;
  `efficacite_raideur = EI_eff / (E_L · 240 · 240³ / 12)` ;
- résistance : moment `M_R = q_R L² / 8` à la première atteinte d'un critère
  du tableau R ; `efficacite_resistance = M_R / (f_m,k · 240 · 240² / 6)`.

`Hypotheses.efficacite_rang` = min des deux. Attendu : 0,1 à 0,4. Si les
deux diffèrent d'un facteur 2 ou plus, scinder le paramètre en deux dans
`materiaux.py` (raideur / résistance) — c'est une évolution simple du module.

### E3 — liaison poteau–rang

*Géométrie* : `poteau.json`. P10 de 3 rangs, une brique fermée de chaque
côté à chaque rang, 2 C1 décalées par rang (option retenue : ligne 1 vers la
gauche, ligne 3 vers la droite, 80 dans le poteau, 150 dans l'about).

*Conditions* : `PIED` et `TETE` du poteau bloqués en x, y, z ; les briques
libres sauf leurs faces extérieures (x = 0 et x = 1 040) bloquées en x
(elles continuent dans le mur). Pression sur `PAREMENT_EXT` des briques,
0 à 3 kN/m².

*Sorties* : déplacement relatif brique/poteau en y à chaque rang, effort
transmis par chaque C1 (résultante sur `FUT_*`), contraintes de fendage dans
le P10 autour des trous.

*Conversion obqo* : raideur `k_liaison = F_rang / Δy` (N/mm) par rang ; effort
maximal par cheville à comparer à `F_v,R` de E1. Si `k_liaison` est du même
ordre que la raideur du rang lui-même (E2), remplacer l'articulation parfaite
du grillage par un ressort `def_support_spring` : c'est une dizaine de lignes
dans `modele.py`.

---

## 5. Critères de rupture (tableau R)

Aster ne décide pas qu'une pièce casse ; il faut lire les champs et comparer.
Critères à appliquer au premier pas de charge où l'un est atteint :

| Critère | Où lire | Seuil |
|---|---|---|
| Flexion / traction dans le fil | σ_LL dans P3, P6, P10 | f_m,k = 24 (C24) |
| Compression dans le fil | σ_LL < 0 dans P4, P10 | f_c,0,k = 21 |
| Traction perpendiculaire (fendage) | σ_TT, σ_NN > 0 autour des trous | f_t,90,k = 0,4 — **c'est presque toujours lui qui gouverne** |
| Cisaillement roulant | τ_TN dans P1/P2 | ≈ 1,0 |
| Portance locale | σ de contact fût/trou | f_h,k ≈ 23 (indicatif) |
| Cisaillement du hêtre | τ dans la cheville au plan de cisaillement | f_v ≈ 10 (**H-M2**) |

Lire les contraintes **moyennées sur un élément**, jamais au nœud singulier
du bord du trou : la singularité géométrique donne une contrainte infinie au
raffinement, ce n'est pas une rupture. Une moyenne sur 5 à 10 mm (une
« distance caractéristique ») est l'usage ; le dire dans le rapport.

---

## 6. Ce que le calcul ne remplace pas

Un BE acceptera un calcul Aster comme *argumentation*, pas comme *preuve*. La
preuve, ce sont des essais physiques, et ils coûtent moins cher qu'on croit :

| Essai | Éprouvettes | Norme | Ce qu'il fixe | Ordre de coût |
|---|---|---|---|---|
| Cisaillement double d'une C1 | 5 (épicéa C24, hêtre, 12 %) | EN 26891 / EN 383 | `resistance_cheville_k`, `K_ser` | quelques centaines d'€ en labo d'école |
| Flexion 4 points d'un rang de 3 briques | 3 | EN 408 (adapté) | `efficacite_rang` | 1 000 à 3 000 € |
| Idem, 3 rangs empilés | 2 | — | effet du chevillage vertical | idem |

Le calcul Aster sert à **dimensionner ces essais** (charge à prévoir,
capteurs, où mettre les jauges) et à **extrapoler** ensuite à des
configurations non testées. C'est son vrai rôle ici.

---

## H — Hypothèses à confirmer avant tout maillage

Toutes marquées dans le JSON (`"hypothese": "H-A…"`) ou dans ce document.

- **H-A1** — chevilles de joint courant : 2 C1 verticales, une par raccord P6,
  chacune dans la brique dont le raccord dépasse (x = joint ± 40, y = 40 et
  200). Le §1.2 dit « 1 cheville par brique » sans donner la position.
- **H-A2** — chevilles d'atelier d'une 480 : 6 C1 verticales au centre de
  l'épaisseur (y = 120), une par ligne ; 4 C1 traversantes (selon y) à
  mi-hauteur des 4 montants P4. Lecture de « 6 verticales + 4 traversantes de
  montants ».
- **H-A3** — piges C3 (40 mm) : 2 par interface traversant/montant, couches 1
  et 3, sur chaque parement, selon x. 16 par brique comme le catalogue.
- **H-A4** — liaison poteau–rang : 2 C1 par rang, décalées, y = 120, z = 40 et
  200 dans le rang. C'est l'option 1 de la discussion, pas encore dans le
  catalogue (`RAIDISSEUR_PAR_RANG` dit encore `C1: 1`).
- **H-A5** — jeu fût/trou nul, pas de serrage à l'humidité.
- **H-A6** — frottement bois/bois 0,35.
- **H-M1** — G roulant = G/10.
- **H-M2** — résistances du hêtre : f_v ≈ 10, f_m ≈ 60, f_c,0 ≈ 45 MPa.
- **Fil des pièces** (`FIL` dans `geometrie_echantillon.py`) : déduit des
  noms (« couché traversant » → fil dans l'épaisseur, « bois debout » → fil
  vertical, âme et raccords → fil le long du mur). À confirmer, c'est ce qui
  décide de tout.

Si l'une de ces hypothèses est fausse, corrigez le script et régénérez le
JSON ; ne corrigez pas le maillage à la main.

---

## Rapport attendu

Un `docs/etudes/aster-<date>.md` par calcul : hypothèses retenues (copie du
tableau H avec ce qui a été confirmé ou changé), maillage (taille, nombre de
nœuds), courbes F(u) ou w(p) en image, valeurs extraites, conversion en
paramètres obqo, et **un paragraphe « ce que je ne crois pas »** : les
endroits où le modèle est le plus loin de la réalité. Puis les valeurs
entrent dans `structure/materiaux.py` avec, en docstring, le nom du rapport
qui les justifie.
