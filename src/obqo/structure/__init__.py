"""Justification structurale de l'entraxe des poteaux raidisseurs.

Le paragraphe 1.7 du brief fixe un poteau tous les 6 m sans dire d'ou vient ce
6 m. Ce module repond par le calcul : quel est le plus long pan de maconnerie
qui tient, au vent et sous la toiture, entre deux P10 ? Il ne remplace pas le
bureau d'etudes, il lui tend une note lisible, hypotheses en tete.

Trois natures de choses, tenues separement :

* les valeurs de **norme** (EN 338, EN 1995-1-1) vivent dans `materiaux`, en
  tables numerotees — personne ne les change, sauf changement de norme ;
* les valeurs **d'essai** (efficacite d'un rang, resistance d'une cheville)
  vivent dans `Hypotheses`, avec des defauts prudents et commentes — seul un
  essai les change ;
* le **modele** (grillage, appuis, combinaisons) vit dans `modele` — seul le
  bureau d'etudes le conteste.

`materiaux` et `eurocode5` s'importent avec la seule bibliotheque standard,
comme `engine`, `rules` et `bom`. PyNite ne s'importe que dans `modele`, a
l'interieur de la fonction : l'extra « structure » n'est requis que pour
calculer, pas pour lire les tables.

C'est le seul endroit d'obqo ou des flottants sont legitimes — contraintes et
fleches n'ont pas de sens en entiers. Ils n'en sortent pas : ce qui repart vers
`engine` est un entier de millimetres, multiple de 240.
"""

from __future__ import annotations

from obqo.structure.entraxe import Verification, entraxe_maxi, note, verifier
from obqo.structure.materiaux import Hypotheses
from obqo.structure.modele import Efforts, Pan

__all__ = [
    "Efforts",
    "Hypotheses",
    "Pan",
    "Verification",
    "entraxe_maxi",
    "note",
    "verifier",
]
