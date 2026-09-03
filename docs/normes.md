# Normes et DTU — ce qui s'applique à obqo, et ce qui ne s'applique pas

> **Aucun texte normatif ne peut être copié dans ce dépôt.** Les NF DTU et les
> Eurocodes sont des documents sous droit d'auteur, vendus par
> [AFNOR Éditions](https://www.boutique.afnor.org/). Cette fiche donne leurs
> références exactes, dit ce que chacun couvre, et où se les procurer
> légalement. Elle ne les remplace pas et ne les résume pas.

## Le point qui décide de tout

**Le système obqo n'est couvert par aucun NF DTU.**

Le NF DTU 31.2 est le texte de référence pour la construction bois en France,
mais il vise les **ossatures** : des montants espacés de 600 mm au maximum,
contreventés par des panneaux cloués sur tout leur pourtour. Les constructions
en **bois massif empilé** — madriers, fustes, rondins — en sont explicitement
exclues, et n'ont pas de DTU propre.

obqo n'est ni l'un ni l'autre : c'est du bois massif chevillé, sans colle ni
métal. Il est donc **hors de tout DTU**, et relève de la procédure des Avis
Techniques ou d'une justification au cas par cas par un bureau d'études.

C'est exactement ce que dit la mention portée sur chaque plan produit :

> Document de calepinage — dimensionnement structural à valider par un bureau
> d'études bois (Eurocode 5, sismique).

## Les textes, et ce qu'ils couvrent

| Référence | Objet | Rapport à obqo |
|---|---|---|
| **NF EN 1995-1-1** (Eurocode 5, partie 1-1) | Calcul des structures en bois, règles générales | **La base du calcul.** C'est sous ce texte qu'un BET justifiera l'ossature, les assemblages chevillés et le contreventement |
| **NF EN 1995-1-2** | Eurocode 5, tenue au feu | S'applique dès qu'une exigence de résistance au feu est demandée |
| **NF EN 1998-1** (Eurocode 8) | Calcul sismique | S'applique selon la zone ; nommé dans la mention portée sur les plans |
| **NF EN 1990 / NF EN 1991** | Bases de calcul, actions (neige, vent, charges) | Fournissent les charges que l'Eurocode 5 combine |
| **NF DTU 31.1** (juin 2017) | Charpente en bois | S'applique à la charpente posée **sur** les murs, pas aux murs |
| **NF DTU 31.2** (mai 2019) | Maisons et bâtiments à ossature en bois | **Ne s'applique pas** : exclut le bois massif empilé. Utile par analogie sur l'étanchéité à l'air et à la vapeur, jamais comme justification |
| **NF DTU 31.3** | Charpentes assemblées par connecteurs métalliques | Sans objet : obqo n'a aucune pièce métallique |
| **NF DTU 20.1 / 13.1x** | Maçonnerie, fondations | Le soubassement et la lisse basse d'ancrage, hors périmètre bois |

## Le volet thermique : « passif ou non »

Le calepinage ne dit rien de la thermique, mais deux textes commandent la
conception d'ensemble :

- **RE2020** — la réglementation en vigueur pour le neuf en France. Elle impose
  des seuils d'étanchéité à l'air et un calcul d'impact carbone sur tout le
  cycle de vie. Le bois massif y est favorisé au titre du stockage carbone.
- **Label Passivhaus / Bâtiment passif** — un label volontaire, pas une
  réglementation, avec ses propres seuils (besoin de chauffage, perméabilité
  à l'air n50, absence de pont thermique).

**Le point dur du bois massif empilé, pour l'un comme pour l'autre, est le
même : le tassement et l'étanchéité à l'air.** Un mur de briques empilées
travaille en hauteur avec le séchage du bois ; les menuiseries et les réseaux
doivent l'accepter. C'est un sujet de conception, hors du champ de cette
application — mais il conditionne l'atteinte des seuils bien plus que le
calepinage.

## Ce que l'application fait de tout cela

obqo ne calcule rien de normatif. Il applique les règles du brief, qui sont des
règles d'**atelier et de géométrie** :

| Règle appliquée | Origine | Ce qu'un BET doit confirmer |
|---|---|---|
| poteau raidisseur tous les 6 m | §1.7 du brief | l'entraxe et la section 80 × 240 |
| portée maxi de linteau chevillé 2 600 mm | §1.6 | la portée admissible réelle |
| rive de baie à 480 mm minimum d'un angle | §2.2.1 | l'appui de linteau |
| refend en butée, liaison par chevillage seul | règle actée D2 | **la liaison mécanique refend/mur** |
| harpage croisé alterné aux angles | §1.5 | le contreventement d'ensemble |

Les points marqués en gras dans `docs/hypotheses.md` sont ceux que
l'application signale d'elle-même comme relevant du bureau d'études.

## Où se les procurer

- **AFNOR Éditions** — <https://www.boutique.afnor.org> : vente à l'unité et
  abonnement COBAZ, qui donne accès à la collection complète.
- **CSTB Éditions** — <https://boutique.cstb.fr> : les NF DTU et les Avis
  Techniques.
- **Bibliothèques universitaires et écoles d'ingénieurs** : beaucoup ont un
  abonnement COBAZ consultable sur place.
- Les **Avis Techniques et ATEx** sont consultables gratuitement sur
  <https://evaluation.cstb.fr>. C'est la voie à regarder en premier pour un
  système hors DTU comme obqo.

## Pourquoi ces textes ne sont pas dans le dépôt

Ils sont vendus, et leur diffusion est contractuellement interdite. Les copier
ici exposerait le projet, et les versions qui circulent gratuitement sont
presque toujours périmées — le NF DTU 31.2 a été refondu en 2019, le 31.1 en
2017. **Pour un document de construction, une norme périmée est pire que pas de
norme du tout.** Achetez la version en vigueur, ou consultez-la en
bibliothèque.
