# Saisir le plan de sa maison

Comment passer d'une idée — ou d'un plan d'architecte — au fichier que
l'application sait calepiner. La méthode tient en cinq étapes, et le principe en
une phrase : **on ne dessine pas puis on cale sur la grille, on cale d'abord.**

```bash
uv run briq gabarit -o ma-maison.yaml   # un plan de départ commenté
uv run briq valider ma-maison.yaml      # après chaque modification
```

Le format accepte le **YAML** aussi bien que le JSON. Pour un plan saisi à la
main, prenez le YAML : on peut y écrire `# fenêtre de la cuisine, alignée sur
l'évier` à côté d'une cote, et se relire six mois plus tard.

---

## 1. Caler les dimensions sur la grille, avant tout le reste

Tout le système vit sur une grille de **240 mm**. Une cote hors grille n'est pas
approximée : elle est refusée, ou recalée avec un avertissement si vous mettez
`hors_grille: arrondir`.

Le réflexe à prendre : ne pensez plus en « environ 5 mètres » mais en **modules
de 240**. Le tableau ci-dessous donne les cotes utilisables autour des dimensions
courantes.

| Vous vouliez | Cotes sur grille | Multiple de 480 |
|---|---|---|
| ~3,00 m | 2 880 · 3 120 | **2 880** |
| ~4,00 m | 3 840 · 4 080 | **3 840** |
| ~5,00 m | 4 800 · 5 040 | **4 800** |
| ~6,00 m | 6 000 · 6 240 | **6 240** |
| ~8,00 m | 7 920 · 8 160 | **8 160** |
| ~10,00 m | 9 840 · 10 080 | **10 080** |
| ~12,00 m | 12 000 · 12 240 | **12 000** |
| ~14,00 m | 13 920 · 14 160 | **13 920** |

**Préférez la colonne de droite.** Une longueur de mur multiple de 480 évite des
demi-briques, et surtout évite qu'une demi-brique se retrouve en position
d'angle — position pour laquelle le catalogue du brief n'a pas de référence.
Ce n'est pas toujours suffisant (voir `hypotheses.md`, H3), mais ça aide
beaucoup : la maison rectangulaire d'exemple n'a aucune brique d'angle
en demi-brique, la maison en L en a 21.

## 2. Le contour, c'est le nu extérieur

Le contour décrit la face **extérieure** des murs. Les 240 mm d'épaisseur
s'ajoutent vers l'intérieur.

Conséquence à ne pas rater : **c'est le contour qu'on cale sur la grille, pas
l'intérieur.** Choisissez la cote extérieure dans la colonne de droite du tableau
ci-dessus, et lisez ce qu'il reste dedans :

| Contour | Intérieur (contour − 480) |
|---|---|
| 4 800 | 4 320 |
| 5 760 | 5 280 |
| 6 240 | 5 760 |
| 7 200 | 6 720 |
| 9 600 | 9 120 |
| 10 080 | 9 600 |
| 13 920 | 13 440 |

Une pièce intérieure d'environ 5 m demande donc un contour de **5 760** — pas
5 480, qui n'est même pas sur la grille de 240. Retenez l'égalité :

> largeur intérieure = largeur de contour − 480 − 240 par refend traversé

Saisissez-le par déplacements successifs plutôt qu'en coordonnées absolues : la
fermeture est alors garantie par construction, et le fichier se relit comme un
métré de terrain.

```yaml
contour:
  trace:
    depart: [0, 0]
    segments:
      - {direction: est,   longueur: 9600}   # M1 — façade sud
      - {direction: nord,  longueur: 7200}   # M2 — pignon est
      - {direction: ouest, longueur: 9600}   # M3 — façade nord
      - {direction: sud,   longueur: 7200}   # M4 — pignon ouest
```

Les murs sont numérotés **M1, M2, M3…** dans l'ordre des segments : c'est ce nom
que les baies et les plans utiliseront. Chaque mur a son abscisse propre, partant
de 0 à son point de départ.

Un contour en L, en U, en T ou en escalier fonctionne : ajoutez simplement les
segments. Seuls les angles droits sont traités.

## 3. Les refends

Un refend est un mur intérieur porteur. Ses deux extrémités doivent tomber **sur
le contour** — l'application n'accepte pas encore un refend qui s'arrête dans le
vide ou sur un autre refend.

```yaml
refends:
  - {id: R1, depart: [4800, 0], arrivee: [4800, 7200]}
```

Un refend est **centré sur son axe** : il mange 120 mm de chaque côté. Un refend
d'axe 4 800 dans un contour de 9 600 laisse donc deux pièces de **4 440 mm**
intérieurs chacune (4 800 − 240 de mur extérieur − 120 de refend), et
4 440 + 240 + 4 440 = 9 120, soit bien le contour moins ses deux murs.

Un refend compte comme raidisseur, au même titre qu'une baie.

## 4. Les baies : les cotes portent sur la trémie

C'est le point qui surprend le plus. `largeur` et `hauteur` décrivent la
**trémie** — le trou dans la maçonnerie — et non le passage libre. Les jambages
se logent à l'intérieur et retirent 160 mm (320 au-delà de 1 800 mm, où ils sont
doublés).

| Trémie | Jambages | Passage libre | Madrier P9 | Linteau chevillé |
|---|---|---|---|---|
| 960 | 2 × 80 | 800 | 1 440 | oui |
| 1 200 | 2 × 80 | **1 040** | 1 680 | oui |
| 1 440 | 2 × 80 | **1 280** | 1 920 | oui |
| 1 680 | 2 × 80 | 1 520 | 2 160 | oui |
| 1 920 | 4 × 80 | 1 600 | 2 400 | oui |
| 2 160 | 4 × 80 | 1 840 | 2 640 | oui |
| 2 400 | 4 × 80 | **2 080** | 2 880 | oui |
| 2 640 | 4 × 80 | 2 320 | 3 120 | **non — lamellé-collé** |

Pour une porte de 930 mm de passant, prenez une trémie de **1 200**. Pour une
porte-fenêtre à deux vantaux, **2 400**. Au-delà de 2 400 le linteau chevillé
n'est plus possible : l'application prescrit alors un lamellé-collé du commerce
aux mêmes cotes, sorti en ligne distincte du métré.

```yaml
ouvertures:
  - id: P-entree
    mur: M1
    position: 2880      # abscisse de la rive gauche, depuis l'origine du mur
    type: porte
    largeur: 1200       # trémie — passage libre 1040
    hauteur: 2160       # trémie — hauteur libre 2160
  - {id: F-sud, mur: M1, type: fenetre, position: 6240, largeur: 1440, allege: 960, hauteur: 1200}
```

Une porte et une porte-fenêtre n'ont pas d'allège ; une fenêtre en a une. Une
allège de 960 place l'appui à hauteur de plan de travail ; 1 440 convient à une
fenêtre de salle de bains.

## 5. La hauteur

`hauteur_sous_chainage` est un multiple de 240 : c'est le nombre de rangs.

| Hauteur | Rangs | Sous linteau de porte |
|---|---|---|
| 2 400 | 10 | 2 160 possible, tout juste |
| **2 640** | **11** | 2 160 confortable |
| 2 880 | 12 | 2 400 possible |

Vérifiez pour chaque baie que **allège + hauteur + 240** (le rang de linteau) ne
dépasse pas la hauteur sous chaînage. Avec 2 640 et une porte de 2 160, il reste
exactement un rang au-dessus du linteau — c'est le minimum acceptable.

---

## Les six règles que l'application refusera

Elle ne les contourne jamais : elle s'arrête et dit laquelle, où, et de combien.

| Règle | Pourquoi |
|---|---|
| Toute cote multiple de **240** | c'est la grille de calepinage |
| Rive de baie à **480 mm** minimum d'un angle | 240 d'appui de linteau + 240 de maçonnerie |
| **480 mm** minimum de trumeau entre deux baies | les deux appuis de linteau voisins |
| Trémie de **2 400 mm** maximum | portée maximale d'un linteau chevillé |
| **6 m** maximum de mur sans baie ni refend | raidissement |
| allège + hauteur + 240 ≤ hauteur sous chaînage | il faut un rang pour le linteau |

## La boucle de travail

1. `briq gabarit -o ma-maison.yaml`
2. Modifier le contour, puis `briq valider ma-maison.yaml`
3. Ajouter les refends, valider. Ajouter les baies une par une, valider.
4. Quand le rapport dit « Plan valide » : `briq calepiner ma-maison.yaml -o dossier/`

Valider après **chaque** ajout, pas à la fin : un message qui désigne la seule
baie que vous venez d'écrire se corrige en dix secondes, une liste de quinze
erreurs se démêle en une heure.

L'interface web (`briq web`) fait la même boucle sans quitter le navigateur, et
montre immédiatement les plans.

## Partir d'un plan d'architecte

1. Relevez les dimensions **hors tout** du bâtiment, ou additionnez les pièces
   intérieures plus 480 mm de murs extérieurs et 240 par refend.
2. Arrondissez chaque cote extérieure au multiple de 480 le plus proche (colonne
   de droite du tableau §1). Acceptez de perdre ou gagner 10 à 20 cm par pièce :
   c'est le prix d'un système modulaire, et c'est invisible à l'usage.
3. Reportez les baies en mesurant la **rive gauche** depuis l'angle de départ de
   chaque mur, et arrondissez à 240.
4. Convertissez les largeurs de passage en trémies avec le tableau du §4.
5. Validez, et corrigez ce que l'application signale.

## Ce que l'application ne vérifie pas

Elle contrôle le système constructif, pas l'habitabilité ni la structure :

- **rien sur le dimensionnement** — c'est l'objet de la mention portée sur chaque
  plan : un bureau d'études bois doit valider (Eurocode 5, sismique) ;
- rien sur les règles d'urbanisme, la RE2020, l'accessibilité ni les surfaces
  réglementaires d'ouverture ;
- rien sur la cohérence d'usage : elle acceptera une chambre sans fenêtre ou une
  porte donnant sur un mur ;
- rien sur les planchers, la charpente, les réseaux ni les fondations.

Elle vous dit ce que le mur coûte en bois et comment le monter. Le reste est à
vous, et au bureau d'études.
