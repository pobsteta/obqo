"""Coeur de l'appareillage : remplissage d'une course de rang en briques.

Tout repose sur une propriete demontrable de la grille : une course remplie de
briques de 480 et 240 ne peut produire que des joints d'une **seule parite**
(mesuree en modules de 240 depuis l'origine du mur). Decaler les joints d'un rang
a l'autre revient donc a alterner cette parite a chaque rang - et rien d'autre.

    course demarrant en `debut`, parite p0 = (debut / 240) % 2

    * commencer par un 480  -> joints de parite p0
    * commencer par un 240  -> joints de parite 1 - p0

Le harpage d'angle decale deja l'origine du mur de 240 un rang sur deux : la
parite demandee alterne donc naturellement, et la brique d'angle reste une 480
a chaque rang, ce qu'exige le catalogue (480-ANR filante, 480-A en butee).
"""

from __future__ import annotations

from obqo.units import GRILLE, LONGUEUR_BRIQUE, LONGUEUR_DEMI


def parite_du_rang(debut_rang0: int, rang: int) -> int:
    """Parite de joint imposee au rang donne.

    Ancree pour que la course partant de l'origine du mur commence toujours par
    une brique de 480, et alternee a chaque rang.
    """
    return (debut_rang0 // GRILLE + rang) % 2


def decouper(debut: int, longueur: int, parite: int) -> list[int]:
    """Longueurs de briques remplissant [debut, debut + longueur].

    Le resultat respecte la parite de joint demandee et n'utilise qu'au plus une
    demi-brique de 240, placee en debut ou en fin de course.
    """
    if longueur < 0 or longueur % GRILLE:
        raise ValueError(f"course de {longueur} mm : multiple de {GRILLE} attendu")
    if debut % GRILLE:
        raise ValueError(f"origine de course {debut} mm : multiple de {GRILLE} attendu")
    m = longueur // GRILLE
    if m == 0:
        return []
    if (debut // GRILLE) % 2 == parite:
        entieres, reste = divmod(m, 2)
        return [LONGUEUR_BRIQUE] * entieres + [LONGUEUR_DEMI] * reste
    entieres, reste = divmod(m - 1, 2)
    return [LONGUEUR_DEMI] + [LONGUEUR_BRIQUE] * entieres + [LONGUEUR_DEMI] * reste


def joints(debut: int, decoupe: list[int]) -> list[int]:
    """Abscisses des joints verticaux interieurs d'une course decoupee."""
    positions: list[int] = []
    u = debut
    for longueur in decoupe[:-1]:
        u += longueur
        positions.append(u)
    return positions
