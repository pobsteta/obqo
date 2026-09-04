# Étude — que vaut la justification d'entraxe du module `structure` ?

Ce document relit le module `structure` face à la règle D6 et au §1.7 du brief
constructif. Il dit ce que le schéma statique suppose, ce qu'il ignore, et ce
qu'un bureau d'études contestera. Il répond aussi à la question 5.4 du brief du
module : le plan doit-il porter ses hypothèses de calcul ?

**Ce que le module conclut, en une ligne :** avec des hypothèses prudentes, le
pan admissible atteint 11 040 mm, soit **presque le double des 6 000 mm du
§1.7**. Le brief est donc du côté sûr — mais pour une raison qui n'est pas
celle qu'on croit, et le reste de ce document explique pourquoi je ne
recommande pas de toucher à `ENTRAXE_MAXI_RAIDISSEUR` pour autant.

---

## 1. Le schéma statique, et ce qu'il suppose

| Élément | Modèle | Ce que ça suppose |
|---|---|---|
| Un rang de 240 | poutre 240 × 240, inertie **et** résistance hors plan multipliées par `efficacite_rang`, articulée sur les deux poteaux | qu'une file de briques creuses aboutées par deux P6 chevillés se comporte comme une poutre homogène affaiblie d'un facteur constant |
| Un poteau | poutre 80 × 240 continue, articulée en pied, tenue en tête par la lisse | que le chaînage tient réellement la tête latéralement, et que le soubassement n'encastre pas |
| La liaison | nœud partagé : le rang déverse sa réaction dans le poteau | que les deux C1 par rang transmettent l'effort tranchant **sans glissement** |
| La portée | d'axe à axe des P10, soit `pan + 240` | que les 160 mm de remplissage du module travaillent avec le poteau |
| Le vent | pression uniforme, chaque poutre sur sa bande tributaire | une pression, pas une dépression ni un tourbillon d'angle |

Les rangs sont calculés **seuls** : le chevillage vertical entre rangs et les
tenons ne raidissent rien dans le modèle. C'est volontairement défavorable, et
c'est aussi ce que mesure l'essai E2 du brief Code_Aster.

## 2. Ce que le modèle ignore — la liste sans complaisance

1. **Le mur ne porte que dans un sens.** Chaque rang franchit l'espace entre
   poteaux ; rien ne franchit la hauteur entre soubassement et chaînage. Un mur
   réel est une plaque qui porte dans les deux sens. Conséquence directe et
   vérifiable : **l'entraxe maximal calculé ne dépend pas de la hauteur du mur**
   — 11 040 mm sous 2,64 m comme sous 3,12 m. C'est le symptôme le plus visible
   de la limite du modèle, et le premier point sur lequel un BE tiquera. Le sens
   de l'erreur est du côté sûr (une plaque porte mieux qu'une poutre), mais un
   résultat insensible à une dimension qui devrait compter n'inspire pas
   confiance, et il ne devrait pas.
2. **Une seule efficacité pour la raideur et pour la résistance.** Rien ne dit
   qu'un rang perde autant de l'une que de l'autre. Si l'essai E2 les sépare
   d'un facteur 2, le paramètre doit se dédoubler — c'est une dizaine de lignes
   dans `materiaux.py` et `entraxe.py`, prévues pour.
3. **Aux extrémités d'un mur, il n'y a pas de poteau.** Le modèle en met un
   quand même, alors que c'est le mur perpendiculaire qui tient l'angle — bien
   plus raide qu'un P10, et harpé, pas chevillé. Le critère « rang » reste du
   côté sûr ; le critère « poteau » d'un pan d'extrémité est un **substitut**,
   pas une vérification. La note l'affiche comme les autres, ce qui est un
   défaut d'affichage à corriger le jour où un pan d'extrémité sera dimensionnant.
4. **Pas de contreventement.** Le mur dans son propre plan, le vent sur pignon,
   le diaphragme de toiture, le sismique : rien de tout cela n'est calculé. Or
   c'est le point faible d'un système chevillé sans métal, et `docs/normes.md`
   le dit déjà.
5. **Pas de poids propre** dans la compression du poteau : seule la charge de
   tête y entre. Un P10 de 2,64 m pèse 23 kg, soit 0,22 kN contre 21 kN de
   charge de tête — 1 %. C'est négligeable, mais c'est une omission, pas une
   hypothèse, et ça cesserait de l'être si le P10 reprenait aussi une part du
   poids de la maçonnerie qu'il raidit.
6. **La cheville n'est justifiée par rien.** L'EN 1995-1-1 §8 traite les tiges
   en acier ; une C1 de hêtre de 20 mm rompt en cisaillement de son propre bois.
   Les 3 kN par défaut sont une borne basse assumée, pas un calcul.
7. **Calcul du premier ordre.** Le flambement passe par le `k_c` de l'article
   6.3.2, qui est la méthode du code ; il n'y a pas d'analyse P-delta. C'est
   correct pour un élément aussi peu élancé (λ = 38), et ce serait à revoir pour
   un mur de 4 m de haut.
8. **La torsion transmise par les rangs aux poteaux est nulle.** Elle est
   mesurée, pas supposée : annuler la raideur de torsion du rang ne change
   aucun résultat de plus de 0,00 %, la structure et les charges étant
   symétriques. Libérer `Rx` aux deux abouts d'un rang, en revanche, en ferait
   un mécanisme — c'est pourquoi seule la rotation `Ry` est libérée.

## 3. Ce qui commande vraiment le résultat

Sur un pan de 6 m, avec les hypothèses par défaut, le taux maximal est de
**0,36** et c'est la flexion composée du poteau qui l'emporte. La marge est
donc large, mais elle n'est large que dans la mesure où les hypothèses le sont :

| On fait varier | Le 6 m du §1.7 lâche à | Facteur de marge |
|---|---|---|
| pression de vent | 3,0 kN/m² | ~3,7 |
| efficacité d'un rang | 0,05 | ~6 |
| résistance d'une C1 | 0,5 kN | ~6 |

Aucune de ces trois valeurs n'est mesurée. **La marge apparente est une marge
sur des hypothèses, pas sur du bois.** C'est exactement pourquoi le module ne
propose pas de relever `ENTRAXE_MAXI_RAIDISSEUR` : voir D7 dans
[`docs/hypotheses.md`](../hypotheses.md).

Ce qui borne l'entraxe maximal, en revanche, ce n'est aucun de ces trois-là :
c'est la **flèche d'un rang** sous vent, à l'ELS. Un critère de service, pas de
ruine — donc un critère dont le seuil (portée / 250) est un choix, discuté au
§5 ci-dessous.

## 4. Écart avec les valeurs de référence du brief

Le brief du module annonce, pour le patch qui ne nous est pas parvenu :

| Commande | Brief | Ce module | Écart |
|---|---|---|---|
| `obqo entraxe` | 10 800 mm, flèche du rang | 11 040 mm, flèche du rang | +1 module de 240 |
| `obqo entraxe --vent 1.1 --efficacite 0.1` | 6 480 mm, flèche du rang | 6 720 mm, flèche du rang | +1 module de 240 |
| `obqo entraxe --pan 6000` | admis, 0,43 (chevilles) | admis, 0,43 (chevilles) | **exact**, avec une seule C1 par rang |

Le troisième chiffre tombe **exactement** avec une cheville par rang, ce qui
donne bonne confiance dans les combinaisons, les k_mod et les coefficients
partiels. Avec les deux chevilles de D7, ce taux passe à 0,22 et le critère
dimensionnant devient le poteau, à 0,36.

Les deux premiers sont décalés d'un module, toujours dans le même sens : le
module retenu ici rapporte la flèche à la **portée d'axe à axe** (`pan + 240`),
là où la référence semble la rapporter au pan nu. Rapportée au pan nu, la
première ligne tombe exactement sur 10 800 — mais pas la seconde, qui reste à
6 720. Les deux références ne sont donc pas simultanément explicables par une
seule règle simple ; l'écart, d'un module de 240 sur 6 à 11 m, reste dans le
bruit du modèle. C'est la portée d'axe à axe qui est retenue, parce que c'est
celle qui sert déjà au moment fléchissant : deux longueurs différentes dans la
même vérification s'expliqueraient mal devant un BE.

## 5. La flèche admissible est le vrai choix caché

Le tableau 7.2 de l'EN 1995-1-1 donne des fourchettes, pas des seuils, et rien
n'y vise un remplissage de façade en bois massif. Le module retient portée / 250.
À portée / 300, l'entraxe maximal tombe à 10 320 mm ; à portée / 200 il
remonte. **Le paramètre qui borne le résultat est donc celui qui a le moins de
fondement normatif de tout le module.** Ce qui commande réellement, sur un mur
de bois massif empilé, c'est la menuiserie et l'étanchéité à l'air — donc un
critère de conception, pas de structure. C'est un point à trancher avec le BE
et le menuisier, pas à calculer.

## 6. Question 5.4 — le plan doit-il porter ses hypothèses de calcul ?

**Pour**

- La zone de vent et la charge de toiture sont des propriétés **du projet**,
  au même titre que la hauteur sous chaînage qui, elle, est déjà dans le plan.
- Aujourd'hui, `structure.txt` peut sortir avec des hypothèses différentes de
  celles de la veille sans que rien ne le trace : la note est reproductible, le
  dossier ne l'est pas.
- Un dossier remis à un BE doit se suffire à lui-même. Un plan qui ne porte pas
  ses charges oblige à transmettre la ligne de commande à côté, ce qui se perd.

**Contre**

- Cela change le schéma versionné `obqo-plan-v1`. Le champ serait optionnel,
  donc rétrocompatible en lecture, mais tout plan écrit après le changement ne
  serait plus lisible par une version antérieure — ce que `v1` promet.
- Le plan cesserait d'être purement **géométrique**. Aujourd'hui il décrit une
  maison ; il décrirait en plus un calcul. Deux choses de nature différente dans
  un même fichier vieillissent mal : la géométrie ne change pas, les hypothèses
  de calcul changent à chaque échange avec le BE.
- Ces valeurs viennent du BE, pas de l'autoconstructeur qui saisit son plan.
  Les mettre dans le fichier qu'il édite invite à les inventer.

**Proposition — un fichier d'hypothèses séparé, pas un champ de plan.**
Un `hypotheses.yaml` optionnel, passé par `obqo entraxe --hypotheses`, repris
tel quel en tête de `structure.txt`. Le plan reste géométrique et `v1` reste
`v1` ; le dossier redevient auto-suffisant ; et le fichier que le BE relit et
signe est un fichier à lui, court, qu'il peut renvoyer corrigé. Si l'usage
montre que les deux fichiers se séparent toujours, alors seulement il sera
temps de fusionner, en `v2`.

**Non implémenté**, conformément au §5.4 : la question est posée, pas tranchée.

## 7. Ce qu'il faudrait pour que cette note devienne une preuve

Dans l'ordre de ce qui change le plus le résultat :

1. **Essai E1** — cisaillement double d'une C1, 5 éprouvettes, EN 26891. Fixe
   `resistance_cheville_k` et la raideur de la liaison. Quelques centaines
   d'euros.
2. **Essai E2** — flexion 4 points d'un rang de 3 briques, 3 éprouvettes. Fixe
   `efficacite_rang`, et dit s'il faut deux paramètres au lieu d'un.
3. **Un calcul de plaque**, ou à défaut l'aveu explicite que le mur ne porte que
   dans un sens. C'est ce qui rendrait le résultat sensible à la hauteur.
4. **Le contreventement d'ensemble**, hors du périmètre de ce module et du
   brief, mais qui décidera de la maison bien avant l'entraxe des raidisseurs.

Le brief Code_Aster ([`specs/structure/aster/BRIEF-aster.md`](../../specs/structure/aster/BRIEF-aster.md))
dimensionne les deux premiers essais et permet de les extrapoler. Il ne les
remplace pas.

---

*Document de travail. Aucune valeur de cette étude n'engage de validation
structurale : dimensionnement à valider par un bureau d'études bois
(Eurocode 5, sismique).*
