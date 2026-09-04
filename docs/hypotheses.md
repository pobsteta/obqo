# Hypothèses et questions ouvertes

Le brief demande de poser la question plutôt que d'inventer : « c'est un système
constructif réel, une hypothèse silencieuse fausse coûte des heures d'atelier ».
Ce document liste tout ce que l'application interprète, et pourquoi.

Les décisions **D** sont actées et verrouillées par des tests. Les hypothèses
**H** sont émises à l'exécution par le rapport de validation : on ne peut pas les
rater. Les constats **F** sont des faits vérifiés par des tests. Les questions
**Q** attendent ta réponse.

---

## D1 — ✅ ACTÉ : le jambage est posé sur la hauteur de la baie

**Décidé le 2026-09-01.** Le §1.6 dit « Jambages P10 pleine hauteur de chaque
côté […] du soubassement au chaînage ». L'application les pose sur la **seule
hauteur de la baie**, du dessus de l'allège à la sous-face du linteau.

Cette règle n'est plus une hypothèse émise à l'exécution : elle est documentée
dans `engine/calepinage._poser_baie` et verrouillée par le test
`test_les_jambages_font_la_hauteur_de_la_baie`. Conséquence sur le métré : un
jambage mesure `hauteur de baie`, et non `hauteur de mur` — soit 24 pièces P10
totalisant 33,8 m sur la maison d'exemple, contre 63,4 m dans l'autre lecture.

Raison, purement arithmétique : un jambage fait 80 mm le long du mur. S'il
traverse l'allège, le remplissage d'allège entre les deux jambages mesure
`largeur − 160`. Or `largeur` est un multiple de 240, donc `largeur − 160`
laisse toujours un reste de 80 : **il n'est jamais calable sur la grille de 240**,
quelle que soit la baie. Le combler demanderait une colonne de 80 mm de large sur
toute l'épaisseur et toute la hauteur du rang — soit 9 carrés P8 par rang, ce que
le brief ne décrit nulle part.

Poser le jambage sur la hauteur de la baie fait tout retomber sur la grille :
l'allège est maçonnée sur toute la largeur de la trémie, le madrier prend appui
240 mm de chaque côté sur cette maçonnerie, et `P9 = portée + 480` est vérifié.

Pour mémoire, le raisonnement : un jambage fait 80 mm le long du mur. S'il
traverse l'allège, le remplissage d'allège entre les deux jambages mesure
`largeur − 160`. Or `largeur` est un multiple de 240, donc `largeur − 160` laisse
toujours un reste de 80 : **il n'est jamais calable sur la grille de 240**, quelle
que soit la baie.

## D2 — ✅ ACTÉ : le refend est en butée à ses deux extrémités

**Décidé le 2026-09-01.** Le §1.5 ne décrit le harpage que pour les angles à 90°.
Un refend est **en butée à ses deux extrémités à tous les rangs** : le mur
traversé file toujours et n'est jamais interrompu. Même quincaillerie qu'un angle
mais sans tenon P5-A, puisqu'il n'y a pas de rotation d'axe.

L'alternative — harpage alterné, le refend pénétrant dans l'épaisseur du mur
traversé un rang sur deux — donnerait une liaison mécanique bien meilleure, mais
demanderait une brique de pénétration absente du catalogue et ferait perdre 240
de course au mur extérieur un rang sur deux. La liaison repose donc sur le seul
chevillage traversant : **c'est un point à signaler au bureau d'études.**

Cette règle n'est plus émise à l'exécution : elle est documentée dans
`engine/calepinage` et vérifiée par les tests.

## D6 — ✅ ACTÉ : le poteau raidisseur occupe un module de 240

**Décidé le 2026-09-03.** Le §1.7 insère le P10 « entre briques d'about
fermées ». Il consomme donc 80 mm de course — et 80 n'est pas un multiple de
240. Trois lectures étaient possibles, une seule tient :

| Lecture | Verdict |
|---|---|
| le module de 240 porte le poteau : 80 de P10 + 160 de remplissage | **retenue** |
| le mur s'allonge de 80 mm par poteau | le contour sort de la grille, le moteur le refuse |
| le P10 se plaque sans entrer dans la course | contredit « inséré entre briques d'about fermées » |

La lecture retenue est aussi la meilleure structurellement : ce qui fait
travailler un raidisseur, c'est sa **continuité** du soubassement au chaînage et
son couplage à la maçonnerie à chaque rang. Logé dans la course entre deux
abouts fermés et chevillé en travers à chaque rang, le P10 a les deux. Plaqué
contre le mur, il n'aurait ni l'un ni l'autre.

Le remplissage de 160 × 240 × 240 par rang se bâtit en P6 — du carrelet 80×80
de 160 de long — soit trois rangées de trois lignes, **9 pièces par rang**. Le
volume tombe exactement : 9 × 80 × 80 × 160 = 160 × 240 × 240. Un test le
vérifie plutôt que de le croire.

**Ce qui reste à valider par le bureau d'études** : la section 80 × 240 et
l'entraxe de 6 m viennent du brief, pas d'une norme. Aucun DTU ne couvre ce
système — voir [`docs/normes.md`](normes.md).

## D7 — ✅ ACTÉ : deux chevilles par rang au poteau, et l'entraxe reste celui du brief

**Décidé le 2026-09-04.** Deux décisions liées, parce qu'elles portent sur le
même objet — la liaison entre le poteau raidisseur et la maçonnerie qu'il tient.

### a) Deux C1 par rang, décalées en hauteur

`RAIDISSEUR_PAR_RANG` passe de `C1: 1` à `C1: 2`. Une seule cheville ne liait le
poteau qu'à un côté et le laissait pivoter dans son module. Elles sont
**décalées** : celle de la couche 1 part vers la maçonnerie de gauche, celle de
la couche 3 vers celle de droite, chacune traversant 80 mm de P10 et pénétrant
de 150 mm dans l'about voisin — 230 mm, la longueur d'une C1 au catalogue.

Où ces chevilles atterrissent n'est pas une question de goût, et la table de
géométrie permet de le **vérifier** plutôt que de l'espérer :

| Cheville | Ce qu'elle traverse sur ses 150 mm | Verdict |
|---|---|---|
| couche 3, z = 200 | la ligne 1 (P2), puis le tenon P5 | plein, à tous les rangs |
| couche 1, z = 40 | la ligne 1 (P2), puis la mortaise de la ligne 2 | plein **dès le rang 1** : c'est le tenon du rang inférieur qui l'occupe |

Le rang 0 fait donc exception : il repose sur le soubassement, sa mortaise est
vide, et sa cheville basse traverserait 70 mm d'air. Le calepinage va chercher
le tenon dans le rang d'en dessous et émet le constat `POTEAU-CHEVILLE-VIDE`
pour les seules chevilles concernées — une par poteau, au premier rang. Deux
remèdes au choix du chantier : poser les deux chevilles du rang 0 en couche 3,
ou boucher la mortaise par un carré P8.

**Ce qui reste à valider par le bureau d'études** : que deux chevilles de hêtre
de 20 mm suffisent à transmettre la réaction d'un rang. Voir b).

### b) `ENTRAXE_MAXI_RAIDISSEUR` reste la valeur du brief

L'entraxe des raidisseurs est désormais une **valeur calculée** : `obqo entraxe`
la produit, et `structure.txt` la justifie pan par pan. Avec les hypothèses par
défaut, le pan admissible atteint 11 040 mm, presque le double des 6 000 mm du
§1.7.

**`units.ENTRAXE_MAXI_RAIDISSEUR` reste néanmoins à 6 000 mm**, et le moteur
continue de poser les poteaux sur cette base. La raison est simple : la marge
calculée est une marge sur des hypothèses, pas sur du bois. Les deux paramètres
qui commandent le résultat — l'efficacité d'un rang et la résistance d'une
cheville — ne sont mesurés par personne, et le critère qui borne l'entraxe est
une flèche de service dont le seuil est un choix, pas une norme. Voir
[`docs/etudes/structure.md`](etudes/structure.md) pour la critique complète.

La constante bougera quand deux essais l'auront méritée :

| Essai | Éprouvettes | Norme | Ce qu'il fixe |
|---|---|---|---|
| **E1** — cisaillement double d'une C1 Ø20 hêtre, entre carrelets épicéa C24 à 12 % d'humidité | 5 | EN 26891 / EN 383 | `resistance_cheville_k` (aujourd'hui 3 kN, borne basse assumée) et la raideur `K_ser` de la liaison |
| **E2** — flexion 4 points d'un rang de 3 briques 480-S, joints courants chevillés | 3 | EN 408, adaptée | `efficacite_rang` (aujourd'hui 0,30), et **si la raideur et la résistance s'écartent d'un facteur 2, le paramètre doit se dédoubler** |

Une variante E2b sur 3 rangs empilés (2 éprouvettes) dirait ce que le chevillage
vertical apporte — le modèle calcule chaque rang seul, ce qui est défavorable et
qu'aucune mesure ne confirme pour l'instant.

**Question ouverte :** ces essais valent 1 500 à 4 000 € en laboratoire d'école.
Est-ce un budget du projet, ou l'entraxe reste-t-il celui du brief pour toujours ?

## H3 — La 240-ANR n'existe pas au catalogue

Quand une course de longueur impaire en modules oblige la demi-brique à tomber à
l'about **filant** d'un angle, la brique d'angle est une demi-brique. Le §1.4 ne
définit qu'une 480-ANR. L'application émet alors une 240-ANR et le signale — en
un seul constat agrégé, listant les murs et les rangs concernés.

Géométriquement, une 240 convient : son tenon unique est à 120 mm de l'about,
donc exactement sur l'axe (120, 120) de la colonne d'angle du §1.5. Mais aucune
référence du brief ne la couvre.

**Ce n'est pas toujours évitable.** Un mur filant d'un côté et en butée de
l'autre a une course de longueur `L ± 240` : impaire en modules dès que `L` est
un multiple de 480. La demi-brique doit alors tomber à un about, et si cet about
est celui d'un angle filant, c'est une 240-ANR. Caler les dimensions sur 480
(voir R1) réduit fortement le phénomène sans le supprimer : la maison
rectangulaire d'exemple n'en a aucune, la maison en L en a 21.

**Question :** faut-il ajouter une 240-ANR au catalogue, ou interdire par une
règle de conception les configurations qui la produisent ?

## H4 — Angle rentrant (270 degrés)

Le §1.5 ne décrit le harpage que pour un angle de 90°. Une maison en L, en U ou
en T a aussi des angles **rentrants**, et ce n'est pas le symétrique du cas
convexe : à 90° les deux bandes de mur se recouvrent dans un carré de 240 × 240,
à 270° elles ne se touchent que par un point.

Le mécanisme reste le même — une colonne de 240 que le mur filant occupe un rang
sur deux — mais elle se trouve **au-delà** du sommet et non en deçà : c'est le
mur filant qui déborde de 240, au lieu que le mur en butée recule de 240.

L'application applique la quincaillerie d'angle par analogie et le signale.
**Question :** l'orientation de la mortaise de flanc de la 480-ANR (§1.4 : ligne
1, rangée intérieure) reste-t-elle valable quand le mur perpendiculaire arrive de
l'autre côté ?

---

## F1 — La constante « 4,16 m » du §1.8 décrit une 480-A, pas une 480-S

Vérifié par test. Le décompte des pièces du §1.2 donne, pour une obqo 480 nue
(abouts ouverts) : 8 × 240 (couchés) + 4 × 240 (montants) + 1 × 480 (âme)
+ 2 × 160 (remplissages) + 2 × 160 (tenons) = **4,00 m** de carrelet, 17 pièces.

Les deux carrés P8 qui ferment un about ajoutent 160 mm : la **480-A** vaut
exactement **4,16 m**, la constante du brief. De même le hêtre de la 480-A vaut
3 630 mm, contre 3,65 m annoncés — écart de 20 mm, soit un arrondi.

En revanche la constante de la demi-brique (1,84 m) correspond bien à une
**240-S** nue. Les deux constantes du §1.8 ne se réfèrent donc pas au même état
de brique.

**Question :** faut-il lire le §1.8 comme « brique avec un about fermé » (le cas
courant en bout de mur) ? Le métré du jalon 2 comptera de toute façon chaque
référence séparément, mais l'ordre de grandeur du brief sert de garde-fou.

## D3 — ✅ ACTÉ : les remplissages centraux sont 2 × 160, et l'écart de 2 pièces reste ouvert

**Décidé le 2026-09-01.** Les remplissages centraux (P6, lignes 3-4, couche 2)
sont bien **2 pièces de 160**, comme l'écrit la table du §1.3.

Conséquence assumée : pour la même longueur de 4,16 m, le §1.8 annonce 21 pièces
bois et la structure du §1.2 en donne 19. Les deux pièces manquantes seraient de
longueur nulle, ce qui est impossible — l'écart reste donc **inexpliqué**, et
c'est le §1.8 qui est en cause, pas la nomenclature. Le test
`test_ecart_documente_sur_le_nombre_de_pieces_d_une_480` le verrouille pour
qu'il ne se referme pas silencieusement un jour.

## Q2 — 1,30 m de hêtre annoncés pour la demi-brique, 1,09 m calculés

Le §1.4 précise pour la demi-brique : « âme courte P7 tenue par 2 piges, pas de
chevilles verticales ». En comptant 2 chevilles traversantes C1, 1 verrouillage
de tenon C2 et 10 piges C3, on obtient 1,09 m. Atteindre 1,30 m demanderait
4 chevilles C1 au lieu de 2, ou 5 piges de plus.

**Question :** combien de piges exactement pour la demi-brique 240 ?

## D4 — ✅ ACTÉ : la brique en butée d'angle est une 480-A complète, plus un carré d'angle

**Décidé le 2026-09-01.** La brique en butée d'angle est une **480-A ordinaire**
(2 carrés P8 posés à l'atelier), et l'angle ajoute son propre carré au chantier —
soit 3 carrés par rang d'angle. Le comptage d'acceptation du §2.5
(1 P5-A / 1 raccord / 1 carré / 2 chevilles par rang) est donc respecté à la
lettre, et la 480-A garde une définition unique quelle que soit sa position.

Le §1.5 (« la poche intérieure de la brique en butée est fermée par un P8 »)
suggérait qu'un carré pouvait être compté à la fois en atelier et au chantier.
Le choix retenu est de garder la marge : 88 carrés de plus sur la maison
d'exemple, soit 7 m de carrelet sur 4 762 — 0,15 % du métré.

---

## F2 — La vérification 3D a corrigé deux erreurs d'implémentation

La table de géométrie interne d'une brique (`rules/geometrie_brique.py`) a été
écrite **indépendamment** de la table de composition (`rules/catalogue.py`), puis
les deux ont été comparées par un test. Cela a immédiatement révélé deux défauts
de l'application — aucun des deux dans le brief :

1. la 480-ANR se voyait attribuer **trois carrés P8 au lieu d'un**. Le §1.4 dit
   que l'about d'angle est fermé comme une 480-A mais que le carré de la ligne 1,
   rangée intérieure, est omis : c'est la mortaise de flanc qui reçoit le raccord
   du mur perpendiculaire. Il ne reste donc qu'un carré, celui du parement
   extérieur ;
2. sur un mur orienté vers l'ouest ou vers le sud, le point de départ d'une pièce
   est son bord **maximum**, pas son minimum. Sans corriger cela, tenons et
   réceptions ne coïncidaient plus sur la moitié des murs.

La vérification « tout tenon trouve-t-il sa réception au rang supérieur ? » est
désormais un test permanent. Elle prouve que le harpage croisé alterné tombe
juste, ce qu'aucune élévation 2D ne sait montrer.

## R1 — Recommandation : caler les dimensions sur 480, pas seulement sur 240

Mesuré sur la maison d'exemple, à géométrie et baies identiques :

| Dimensions | 480-S | 480-A | 480-ANR | 240-A | **240-ANR** |
|---|---|---|---|---|---|
| 13 920 × 10 800 | 884 | 68 | 34 | 48 | **10** |
| 13 920 × 10 560 | 862 | 80 | 44 | 36 | **0** |

Passer de 10,80 m à 10,56 m (une seule demi-brique de différence sur la
profondeur) élimine complètement les briques d'angle en demi-brique — celles que
le catalogue ne couvre pas (H3) — et réduit aussi le nombre de demi-briques.

Raison : un mur filant aux deux angles a une course de longueur `L`, un mur en
butée aux deux angles une course de `L − 480`. Les deux sont paires en modules
de 240 si et seulement si `L` est un multiple de 480. Sinon une demi-brique
apparaît, et elle peut tomber à l'angle.

C'est pourquoi `exemples/maison.json` fait 13,92 × 10,56 m plutôt que les
10,80 × 13,92 suggérés au §2.1. **Question :** cette contrainte est-elle
acceptable sur ton plan réel ?

## Q6 — L'échantillon E1 du brief Code_Aster ne peut pas se bâtir tel quel

Le §4 du [brief Code_Aster](../specs/structure/aster/BRIEF-aster.md) décrit
l'essai de cisaillement double ainsi : « Deux carrelets extérieurs P2 (fil selon
y) et un montant central P4 (fil selon z), la cheville selon y : elle est donc
**parallèle au fil des traversants** ».

Cette éprouvette ne peut pas exister. Trois pièces empilées le long de l'axe de
la cheville occupent chacune 80 mm en y ; aucune ne peut avoir son fil — donc sa
longueur — selon y. Et les conditions aux limites du même paragraphe (« faces
x = 0 des pièces extérieures bloquées, face x = 240 de la pièce centrale : DX
imposé ») supposent des pièces longues de 240 mm **selon x**, pas selon y.

`geometrie_echantillon.py` retient donc la configuration réellement percée dans
la brique, sous le code **H-A7** : la cheville selon y traverse deux montants P4
(fil z) et l'âme P3 (fil x) entre eux. Les conditions aux limites du brief y
tombent juste, mot pour mot ; seul le « parallèle au fil des traversants »
tombe.

**Questions :** l'essai visé est-il bien la traversante de montant du §1.2 —
celle qui traverse P4 / P3 / P4 ? Ou bien la cheville verticale d'atelier, qui
elle traverse effectivement les traversants dans le sens de leur fil, mais selon
z et non selon y ? Les deux existent dans la brique, et elles n'ont pas la même
résistance : c'est la seconde qui fend le bois le long du fil, donc la
défavorable. Si c'est elle qu'il faut mesurer, corrigez `FIL` et la fonction
`cheville()` du script, et régénérez le JSON — ne retouchez pas le maillage.

## Q4 — Paramètres de débit

Voir `docs/etudes/longueur-de-barre.md` pour l'analyse complète. Le jalon 2 est
livré avec les valeurs par défaut ci-dessous, toutes paramétrables dans le plan.

1. **Trait de scie** : ✅ **acté le 2026-09-01 à 4 mm**, en remplacement de la
   « marge de chute » globale du §2.1. C'est la valeur retenue par défaut dans
   `parametres.trait_de_scie` et celle sur laquelle repose l'étude de longueur de
   barre : à 4 mm, la barre de 4 m reste le choix le plus robuste, 2,40 m le
   pire, et il ne faut acheter que des longueurs multiples de 80.
2. **Chute minimale réutilisable** : 240 mm par défaut (une demi-brique).
3. **Lisibilité contre optimalité** : la question ne se pose finalement pas. Sur
   la maison d'exemple, l'objectif lexicographique (minimiser les barres, puis
   les patrons distincts, puis maximiser les chutes réutilisables) donne
   **1 215 barres en 3 patrons seulement**. Il n'y a rien à sacrifier : la
   solution la plus économique est aussi la plus simple à l'atelier.
4. **Longueur d'approvisionnement des 80 × 240** : 4 000 mm par défaut
   (`parametres.longueur_barre_madrier`), stock distinct du carrelet.

## Q5 — La surproduction est-elle un rebut ou une rechange ?

Le solveur exact peut, à nombre de barres constant, sortir quelques pièces de
plus que nécessaire — par exemple une pièce de 240 supplémentaire dans un fond de
barre qui serait sinon perdu. L'application les compte comme **rechanges** et non
comme chute, dans une catégorie distincte (0,9 m sur la maison d'exemple).

C'est ce qui rend le taux de chute honnête : confondre les deux masquait
totalement la loi des 80/L. **Question :** veux-tu au contraire que le solveur
interdise toute surproduction ? Par défaut elle est autorisée et comptée à part.
