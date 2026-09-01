# Étude — quelle longueur d'approvisionnement pour le carrelet 80×80 ?

**Question posée :** la barre de 4 m est-elle l'optimum ? Une barre de 2,40 m ne
donnerait-elle pas moins de chute, puisque 2 400 = 10 × 240 exactement ?

**Réponse : non. 2,40 m est le pire choix de toute la gamme.** L'intuition est
juste dans un monde sans trait de scie, et elle s'inverse dès qu'on tient compte
de la lame.

Méthode : énumération exhaustive des patrons de découpe puis ILP résolu à
l'optimum par CP-SAT (`longueur_de_barre.py`), sur une demande représentative
d'une maison (~1 000 briques 480 + ~100 demi-briques + raccords) :
12 700 × 240, 6 100 × 160, 1 000 × 480, 300 × 80 — soit 4 528 m de bois
strictement nécessaires.

## Résultats

| Barre | Chute, trait 0 mm | Chute, trait 4 mm | Bois acheté (trait 4) |
|---|---|---|---|
| 2 400 | **0,00 %** | **3,33 %** | 4 685 m |
| 3 000 | 1,33 % | 3,14 % | 4 677 m |
| 3 600 | 0,00 % | 2,22 % | 4 633 m |
| **4 000** | 0,00 % | **2,00 %** | 4 624 m |
| 4 200 | 0,95 % | 2,61 % | 4 654 m |
| **4 800** | 0,00 % | **1,67 %** | 4 608 m |
| 6 000 | 0,00 % | 2,23 % | 4 632 m |

Sans trait de scie, 2 400 est parfait — c'est exactement l'intuition. Avec un
trait de 4 mm, il devient le pire, et coûte **61 m de bois de plus** que la barre
de 4 m pour la même maison, plus 800 barres supplémentaires à manipuler
(1 952 contre 1 156).

## Pourquoi : la loi des 80 mm

10 pièces de 240 dans une barre de 2 400 demandent 9 traits, soit 36 mm — il n'y
a pas la place. On ne sort donc que **9 pièces**, et il reste 208 mm de fond de
barre, trop court pour un 240.

Généralisation, vérifiée par le calcul : dès que la somme des traits d'une barre
dépasse 80 mm, on perd **un module de 80 entier** en fond de barre, quelle que
soit la longueur de la barre. La chute vaut alors :

> **chute ≈ 80 / L** — un module perdu par barre, amorti sur la longueur.

D'où 80/2400 = 3,33 %, 80/4000 = 2,00 %, 80/4800 = 1,67 %. Les chiffres mesurés
collent exactement. **Plus la barre est longue, moins le module perdu pèse.**

## Deux corollaires actionnables

**1. N'acheter que des longueurs multiples de 80.** 3 000, 4 200, 5 000 et 5 400
sont multiples de 40 mais pas de 80 : il reste un onglet de 40 mm incompressible
qu'aucune pièce du système ne peut occuper, et leur rendement devient erratique
(3 000 passe de 1,33 % à 3,14 % quand le trait passe de 3 à 4 mm). 2 400, 3 600,
4 000, 4 800 et 6 000 sont propres.

**2. Le trait de scie plafonne la longueur utile.** La barre cesse d'être
rentable dès que (nombre de pièces − 1) × trait dépasse 80 mm, soit environ
21 pièces à 4 mm. Avec des pièces majoritairement de 240, cela plafonne à
~5 040 mm. Au-delà on perd un deuxième module : à 6 000 mm et 4 mm de trait, la
chute remonte à 2,23 %.

## Sensibilité (le classement tient-il ?)

Testé sur 3 mélanges de demande × 3 traits de scie (3, 4, 5 mm) :

| Barre | Écart observé | Comportement |
|---|---|---|
| 2 400 | 3,33 – 3,34 % | **toujours le pire**, dans les 9 scénarios |
| 4 000 | 2,00 – 2,07 % | **le plus stable** de toute la gamme |
| 4 800 | 1,67 – 2,76 % | meilleur à trait fin, se dégrade à 5 mm |
| 6 000 | 1,34 – 2,48 % | très sensible au trait |

## Recommandation

**Garder la barre de 4 m comme référence.** Non parce qu'elle minimise la chute
dans l'absolu — 4,80 m fait mieux de 0,33 point à trait fin — mais parce qu'elle
est **la seule dont le rendement ne bouge pas** (2,00–2,07 %) quels que soient le
trait de scie réel et le mélange de pièces. Sur un chantier d'autoconstruction où
le trait dépend de la lame montée ce jour-là, la robustesse vaut mieux que
l'optimum théorique. C'est aussi la longueur commerciale standard de l'épicéa de
charpente, et celle du ratio de référence du §1.8 du brief.

**Passer à 4,80 m uniquement si** le scieur la fournit sans surcoût, que le
transport et la manipulation suivent (une barre de 4,80 m en 80×80 pèse ~14 kg),
et qu'on garantit un trait ≤ 4 mm. Gain attendu : ~16 m de bois sur la maison,
soit ~0,3 %. Marginal.

**Ne jamais descendre sous 3,60 m.** C'est là que la loi des 80/L mord.

La longueur de barre reste un paramètre du plan (`parametres.longueur_barre`) :
le solveur de débit du jalon 2 la traite comme une donnée, et cette étude est
rejouable sur la demande réelle de ta maison une fois le calepinage produit.
