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

## H3 — La 240-ANR n'existe pas au catalogue

Quand une course de longueur impaire en modules oblige la demi-brique à tomber à
l'about **filant** d'un angle, la brique d'angle est une demi-brique. Le §1.4 ne
définit qu'une 480-ANR. L'application émet alors une 240-ANR et le signale.

Géométriquement, une 240 convient : son tenon unique est à 120 mm de l'about,
donc exactement sur l'axe (120, 120) de la colonne d'angle du §1.5. Mais aucune
référence du brief ne la couvre.

**Le contourner est possible et gratuit :** voir R1 ci-dessous.

---

## F1 — La constante « 4,16 m » du §1.8 décrit une 480-A, pas une 480-S

Vérifié par test. Le décompte des pièces du §1.2 donne, pour une BRIQ 480 nue
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

## Q4 — Paramètres de débit

Voir `docs/etudes/longueur-de-barre.md` pour l'analyse complète. Le jalon 2 est
livré avec les valeurs par défaut ci-dessous, toutes paramétrables dans le plan.

1. **Trait de scie** : 4 mm par défaut, en remplacement de la « marge de chute »
   globale du §2.1. Quelle est la valeur réelle de ta lame ?
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
