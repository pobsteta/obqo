"""Ou se trouve chaque piece a l'interieur d'une brique.

Encore une table, pas un algorithme. Repere local d'une brique :

* **x** le long du mur, de 0 a 480 (ou 240) — les six lignes du paragraphe 1.2
  occupent x = 80i a 80i+80, centres a 40/120/200/280/360/440 ;
* **y** dans l'epaisseur, de 0 a 240 — parement exterieur [0, 80], centre
  [80, 160], parement interieur [160, 240] ;
* **z** en hauteur, de 0 a 240 — couche 1 [0, 80], couche 2 [80, 160],
  couche 3 [160, 240]. Les tenons debordent jusqu'a 320.

Cette table sert au rendu 3D, mais surtout de **controle croise** : un test
verifie qu'elle produit exactement les memes pieces que les tables de
composition de `catalogue.py`, et que les 54 cellules de 80 d'une brique 480 sont
soit occupees, soit une poche ou un trou de reception identifie.
"""

from __future__ import annotations

from typing import NamedTuple

from briq.model.systeme import Ref

MODULE = 80


class PiecePlacee(NamedTuple):
    """Une piece bois dans le repere local de la brique, en millimetres."""

    ref: str
    x: int
    y: int
    z: int
    dx: int
    dy: int
    dz: int

    @property
    def volume(self) -> int:
        return self.dx * self.dy * self.dz


# Poches ouvertes de la couche 2 (paragraphe 1.2), par about et par parement.
def _poches(longueur: int) -> dict[str, tuple[tuple[int, int], ...]]:
    dernier = longueur - MODULE
    return {"debut": ((0, 0), (0, 160)), "fin": ((dernier, 0), (dernier, 160))}


def _corps_480() -> list[PiecePlacee]:
    pieces: list[PiecePlacee] = []
    for z in (0, 160):  # couches 1 et 3
        for i in (0, 2, 3, 5):  # lignes 1, 3, 4, 6
            ref = "P2" if i in (0, 5) else "P1"
            pieces.append(PiecePlacee(ref, MODULE * i, 0, z, MODULE, 240, MODULE))
    for i in (1, 4):  # lignes 2 et 5 : montants pleine hauteur, deux parements
        for y in (0, 160):
            pieces.append(PiecePlacee("P4", MODULE * i, y, 0, MODULE, MODULE, 240))
    pieces.append(PiecePlacee("P3", 0, MODULE, MODULE, 480, MODULE, MODULE))
    for y in (0, 160):  # remplissages centraux, lignes 3-4
        pieces.append(PiecePlacee("P6", 160, y, MODULE, 160, MODULE, MODULE))
    for i in (1, 4):  # tenons plantes sur l'ame, debord 80 vers le haut
        pieces.append(PiecePlacee("P5", MODULE * i, MODULE, 160, MODULE, MODULE, 160))
    return pieces


def _corps_240() -> list[PiecePlacee]:
    pieces: list[PiecePlacee] = []
    for z in (0, 160):
        for i in (0, 2):
            pieces.append(PiecePlacee("P2", MODULE * i, 0, z, MODULE, 240, MODULE))
    for y in (0, 160):
        pieces.append(PiecePlacee("P4", MODULE, y, 0, MODULE, MODULE, 240))
    pieces.append(PiecePlacee("P7", 0, MODULE, MODULE, 240, MODULE, MODULE))
    pieces.append(PiecePlacee("P5", MODULE, MODULE, 160, MODULE, MODULE, 160))
    return pieces


def pieces_de(ref: Ref) -> list[PiecePlacee]:
    """Toutes les pieces bois d'une brique du catalogue, placees.

    Les chevilles de hetre n'ont pas de geometrie ici : elles sont percees, non
    posees.
    """
    longueur = ref.longueur
    pieces = _corps_480() if longueur == 480 else _corps_240()
    suffixe = ref.value.split("-", 1)[1]
    poches = _poches(longueur)

    abouts: list[str] = {"S": [], "A": ["fin"], "AA": ["debut", "fin"], "ANR": []}[suffixe]
    for about in abouts:
        for x, y in poches[about]:
            pieces.append(PiecePlacee("P8", x, y, MODULE, MODULE, MODULE, MODULE))

    if suffixe == "ANR":
        # Repere oriente **angle en x = 0** : c'est la convention de la filante
        # d'angle, que le rendu retourne quand l'angle tombe a l'autre about.
        # Paragraphe 1.4 : l'about d'angle est ferme comme une 480-A, mais le
        # carre de la ligne 1 rangee interieure est omis — c'est la mortaise de
        # flanc qui recoit le raccord du mur perpendiculaire. Il reste donc un
        # seul carre, celui du parement exterieur. Et le tenon cote angle
        # devient un P5-A, perce au quart de tour.
        pieces.append(PiecePlacee("P8", 0, 0, MODULE, MODULE, MODULE, MODULE))
        pieces = [
            PiecePlacee("P5-A", *p[1:]) if p.ref == "P5" and p.x == MODULE else p for p in pieces
        ]

    return sorted(pieces, key=lambda p: (p.z, p.y, p.x, p.ref))


def cellules_vides(ref: Ref) -> list[tuple[int, int, int]]:
    """Cellules de 80 non occupees : poches ouvertes et trous de reception."""
    longueur = ref.longueur
    occupees = set()
    for p in pieces_de(ref):
        for x in range(p.x, p.x + p.dx, MODULE):
            for y in range(p.y, p.y + p.dy, MODULE):
                for z in range(p.z, min(p.z + p.dz, 240), MODULE):
                    occupees.add((x, y, z))
    return sorted(
        (x, y, z)
        for x in range(0, longueur, MODULE)
        for y in (0, MODULE, 160)
        for z in (0, MODULE, 160)
        if (x, y, z) not in occupees
    )
