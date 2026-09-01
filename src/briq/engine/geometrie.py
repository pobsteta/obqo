"""Du contour du plan aux murs et aux angles.

Version 1 : contours rectilignes (tous les angles a 90 degres), murs de 240
d'epaisseur poses **a l'interieur** du contour, qui represente donc le nu
exterieur.
"""

from __future__ import annotations

from dataclasses import dataclass

from briq.model.plan import Plan
from briq.units import EPAISSEUR_MUR

Point = tuple[int, int]


@dataclass(frozen=True, slots=True)
class Angle:
    """Un angle de mur a 90 degres entre deux murs consecutifs."""

    id: str
    sommet: Point
    entrant: str
    """Mur qui arrive sur l'angle."""
    sortant: str
    """Mur qui en repart."""
    filant_rang0: str
    """Mur qui file jusqu'au nu de l'autre au rang 0 (le plus long)."""

    def filant(self, rang: int) -> str:
        """Harpage croise alterne : le mur filant change a chaque rang."""
        if rang % 2 == 0:
            return self.filant_rang0
        return self.sortant if self.filant_rang0 == self.entrant else self.entrant


@dataclass(frozen=True, slots=True)
class Mur:
    id: str
    depart: Point
    arrivee: Point
    interieur: bool = False

    @property
    def longueur(self) -> int:
        return abs(self.arrivee[0] - self.depart[0]) + abs(self.arrivee[1] - self.depart[1])

    @property
    def horizontal(self) -> bool:
        return self.depart[1] == self.arrivee[1]


@dataclass(frozen=True, slots=True)
class Squelette:
    murs: list[Mur]
    angles: list[Angle]
    angles_par_mur: dict[str, tuple[Angle | None, Angle | None]]
    """Pour chaque mur : (angle de depart, angle d'arrivee). None pour un refend."""
    ancrages: dict[str, list[int]]
    """Abscisses des refends venant s'ancrer sur chaque mur exterieur."""

    def mur(self, identifiant: str) -> Mur:
        return next(m for m in self.murs if m.id == identifiant)

    def course(self, mur: Mur, rang: int) -> tuple[int, int]:
        """Abscisses de debut et de fin de la maconnerie du mur a ce rang.

        Au droit d'un angle, le mur filant occupe la colonne d'angle et part de 0 ;
        le mur en butee s'arrete au nu de l'autre, donc recule de 240.
        """
        depart, arrivee = self.angles_par_mur[mur.id]
        debut = 0 if depart is None or depart.filant(rang) == mur.id else EPAISSEUR_MUR
        fin = mur.longueur - (
            0 if arrivee is None or arrivee.filant(rang) == mur.id else EPAISSEUR_MUR
        )
        return debut, fin


def _sur_segment(point: Point, a: Point, b: Point) -> bool:
    """Le point appartient-il au segment [a, b] (segment axial) ?"""
    (x, y), (xa, ya), (xb, yb) = point, a, b
    if xa == xb:
        return x == xa and min(ya, yb) <= y <= max(ya, yb)
    if ya == yb:
        return y == ya and min(xa, xb) <= x <= max(xa, xb)
    return False


def _oriente(points: list[Point]) -> list[Point]:
    """Oriente le contour dans le sens trigonometrique (aire positive)."""
    aire = sum(
        points[i][0] * points[(i + 1) % len(points)][1]
        - points[(i + 1) % len(points)][0] * points[i][1]
        for i in range(len(points))
    )
    return points if aire > 0 else list(reversed(points))


def squelette(plan: Plan) -> Squelette:
    """Construit les murs et les angles a partir du contour et des refends."""
    sommets = _oriente(plan.contour.sommets())
    n = len(sommets)
    murs = [Mur(f"M{i + 1}", sommets[i], sommets[(i + 1) % n]) for i in range(n)]
    longueurs = {m.id: m.longueur for m in murs}

    angles: list[Angle] = []
    for i in range(n):
        entrant, sortant = murs[i - 1], murs[i]
        # Choix deterministe : le mur le plus long file au rang 0 ; a egalite,
        # le mur d'indice le plus faible.
        if (longueurs[entrant.id], -int(entrant.id[1:])) >= (
            longueurs[sortant.id],
            -int(sortant.id[1:]),
        ):
            filant = entrant.id
        else:
            filant = sortant.id
        angles.append(
            Angle(
                id=f"A{i + 1}",
                sommet=sommets[i],
                entrant=entrant.id,
                sortant=sortant.id,
                filant_rang0=filant,
            )
        )

    # Un refend court entre les **nus interieurs** des deux murs qu'il rejoint :
    # ses extremites saisies sur le contour sont donc rentrees de 240.
    refends: list[Mur] = []
    ancrages: dict[str, list[int]] = {}
    for refend in plan.refends:
        (x0, y0), (x1, y1) = refend.depart, refend.arrivee
        dx = (x1 > x0) - (x1 < x0)
        dy = (y1 > y0) - (y1 < y0)
        refends.append(
            Mur(
                refend.id,
                (x0 + dx * EPAISSEUR_MUR, y0 + dy * EPAISSEUR_MUR),
                (x1 - dx * EPAISSEUR_MUR, y1 - dy * EPAISSEUR_MUR),
                interieur=True,
            )
        )
        for bout in ((x0, y0), (x1, y1)):
            for m in murs:
                if _sur_segment(bout, m.depart, m.arrivee):
                    abscisse = abs(bout[0] - m.depart[0]) + abs(bout[1] - m.depart[1])
                    ancrages.setdefault(m.id, []).append(abscisse)
                    break

    par_mur: dict[str, tuple[Angle | None, Angle | None]] = {}
    for i, m in enumerate(murs):
        par_mur[m.id] = (angles[i], angles[(i + 1) % n])
    for interieur in refends:
        par_mur[interieur.id] = (None, None)

    return Squelette(
        murs=[*murs, *refends],
        angles=angles,
        angles_par_mur=par_mur,
        ancrages=ancrages,
    )
