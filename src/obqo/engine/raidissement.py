"""Poteaux raidisseurs : ou le mur en manque, et ou les poser.

Le paragraphe 1.7 impose un raidisseur tous les 6 m de mur sans refend ni
jambage, les jambages de baies comptant comme raidisseurs. L'application ne se
contente plus de refuser un plan trop long : elle pose les P10 qui manquent, et
dit ou elle les a mis.

**Regle actee (D6)** — le P10 est « insere entre briques d'about fermees », il
consomme donc 80 mm de course, ce qui sortirait le mur de la grille de 240. Le
poteau occupe donc un **module entier de 240** : 80 de P10 et 160 de
remplissage, entre deux abouts fermes. Le mur reste exactement modulaire, et le
poteau reste continu du soubassement au chainage — ce qu'exige un raidisseur
pour travailler, et que ne donnerait pas un P10 plaque contre la maconnerie.

Tout se calcule en **modules de 240**, jamais en millimetres : c'est ce qui
garantit qu'un pan de mur reste un nombre entier de briques.
"""

from __future__ import annotations

from itertools import pairwise

from obqo.units import ENTRAXE_MAXI_RAIDISSEUR, GRILLE, MODULE_POTEAU

MODULES_MAXI_PAN = ENTRAXE_MAXI_RAIDISSEUR // GRILLE
"""Longueur maximale d'un pan de mur sans raidisseur, en modules de 240."""


def coupures(longueur: int, bornes_de_baies: list[int], ancrages: list[int]) -> list[int]:
    """Points qui raidissent deja le mur, extremites comprises.

    Une rive de baie porte un jambage, un ancrage de refend porte le refend :
    les deux tiennent lieu de raidisseur.
    """
    return sorted({0, longueur} | set(bornes_de_baies) | set(ancrages))


def _nombre_de_poteaux(modules: int) -> int:
    """Combien de poteaux pour ramener chaque pan sous l'entraxe.

    Poser n poteaux retire n modules de maconnerie et decoupe le pan en n + 1
    morceaux. Le plus petit n tel que chaque morceau tienne dans l'entraxe est
    donc celui qui verifie `ceil((modules - n) / (n + 1)) <= MODULES_MAXI_PAN`.
    """
    n = 0
    while modules - n > MODULES_MAXI_PAN * (n + 1):
        n += 1
    return n


def _repartir(modules: int, poteaux: int) -> list[int]:
    """Longueurs des morceaux de maconnerie, en modules, aussi egales que possible."""
    maconnerie = modules - poteaux
    parts, reste = divmod(maconnerie, poteaux + 1)
    return [parts + 1] * reste + [parts] * (poteaux + 1 - reste)


def positions_dans_un_pan(debut: int, fin: int) -> list[int]:
    """Abscisses des modules de poteau a poser dans un pan de mur nu.

    Rend une liste vide si le pan tient deja dans l'entraxe. Les positions sont
    les rives gauches des modules de 240, sur la grille par construction.
    """
    modules = (fin - debut) // GRILLE
    nombre = _nombre_de_poteaux(modules)
    if not nombre:
        return []
    positions: list[int] = []
    u = debut
    for part in _repartir(modules, nombre)[:-1]:
        u += part * GRILLE
        positions.append(u)
        u += MODULE_POTEAU
    return positions


def positions_manquantes(
    longueur: int, bornes_de_baies: list[int], ancrages: list[int]
) -> list[int]:
    """Tous les poteaux a ajouter le long d'un mur, dans l'ordre."""
    manquants: list[int] = []
    for a, b in pairwise(coupures(longueur, bornes_de_baies, ancrages)):
        manquants.extend(positions_dans_un_pan(a, b))
    return manquants


def pans_maconnes(
    longueur: int,
    baies: list[tuple[int, int]],
    poteaux: list[int],
    ancrages: list[int],
) -> list[tuple[int, int]]:
    """Troncons de **maconnerie** entre deux raidisseurs, baies exclues.

    `coupures` rend les points qui raidissent ; les intervalles entre ces points
    ne sont pas tous de la maconnerie : celui d'une baie est une tremie, celui
    d'un poteau est le module du P10. Ce sont ces deux-la qu'on ecarte, pour ne
    garder que les pans dont il y a quelque chose a verifier.

    C'est la decoupe que lit le module `structure` pour noter un plan reel.
    """
    interdits = {(a, b) for a, b in baies} | {(u, u + MODULE_POTEAU) for u in poteaux}
    bornes = sorted({0, longueur} | {x for paire in interdits for x in paire} | set(ancrages))
    return [(a, b) for a, b in pairwise(bornes) if b > a and (a, b) not in interdits]
