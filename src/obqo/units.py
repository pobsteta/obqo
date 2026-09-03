"""Unites et constantes de grille du systeme obqo.

Regle absolue du projet : **toutes les longueurs sont des entiers en
millimetres**. Aucun flottant n'entre dans le modele ni dans le moteur. Tout le
systeme vit sur une grille de 80 mm ; le calepinage vit sur une grille de 240.
"""

from __future__ import annotations

from typing import NewType

Mm = NewType("Mm", int)
"""Longueur en millimetres, toujours entiere."""

MODULE = 80
"""Module de base du systeme (section du carrelet, pas des lignes)."""

GRILLE = 240
"""Pas de la grille de calepinage : longueurs de murs, baies, positions."""

EPAISSEUR_MUR = 240
"""Epaisseur d'un mur : 3 rangs de 80."""

HAUTEUR_RANG = 240
"""Hauteur d'un rang de briques."""

LONGUEUR_BRIQUE = 480
"""Longueur de la brique standard obqo 480."""

LONGUEUR_DEMI = 240
"""Longueur de la demi-brique."""

PORTEE_MAXI_LINTEAU = 2600
"""Portee maximale d'un linteau cheville (paragraphe 1.6 du brief)."""

APPUI_LINTEAU = 240
"""Appui du madrier de linteau de chaque cote de la baie."""

ENTRAXE_MAXI_RAIDISSEUR = 6000
"""Longueur maximale de mur sans refend ni jambage (paragraphe 1.7)."""

RECUL_MINI_BAIE_ANGLE = 480
"""Distance minimale entre la rive d'une baie et un angle (paragraphe 2.2.1)."""

LARGEUR_JAMBAGE = 80
"""Epaisseur d'un jambage P10 mesuree le long du mur."""

LARGEUR_BAIE_JAMBAGE_DOUBLE = 1800
"""Au-dela de cette largeur de tremie, les jambages sont doubles (160)."""

HAUTEUR_TREMIE_PORTE = 2160
"""Hauteur de tremie usuelle d'une porte : 9 rangs, soit 2040 de vantail fini
plus le jeu. Avec les 240 du linteau, 2400 mm sous un chainage a 2640."""

HAUTEUR_TREMIE_FENETRE = 1200
"""Hauteur de tremie usuelle d'une fenetre, sous une allege de 960."""

LARGEUR_POTEAU = 80
"""Epaisseur d'un poteau raidisseur P10 mesuree le long du mur (paragraphe 1.3)."""

MODULE_POTEAU = GRILLE
"""Longueur de mur qu'occupe un poteau raidisseur : un module de 240.

Le paragraphe 1.7 insere le P10 « entre briques d'about fermees ». Il consomme
donc 80 mm de course, ce qui sortirait le mur de la grille. Le poteau occupe
donc un module entier : 80 de P10 et 160 de remplissage, entre deux abouts
fermes. Le mur reste exactement modulaire et le poteau reste continu du
soubassement au chainage, ce qu'exige un raidisseur pour travailler.
"""

REMPLISSAGE_POTEAU = MODULE_POTEAU - LARGEUR_POTEAU
"""Ce qui reste du module une fois le P10 pose : 160 mm de maconnerie."""

HAUTEUR_MINI_PASSAGE = 1920
"""En dessous, on ne passe plus debout sous le linteau : 8 rangs.

La hauteur d'une tremie *est* le passage libre vertical — contrairement a la
largeur, dont les jambages retirent 160 mm.
"""


def sur_grille(valeur: int, pas: int = GRILLE) -> bool:
    """La valeur tombe-t-elle sur la grille ?"""
    return valeur % pas == 0


def modules(longueur: int) -> int:
    """Nombre de modules de 240 d'une longueur (qui doit etre sur la grille)."""
    if longueur % GRILLE:
        raise ValueError(f"{longueur} mm n'est pas un multiple de {GRILLE}")
    return longueur // GRILLE
