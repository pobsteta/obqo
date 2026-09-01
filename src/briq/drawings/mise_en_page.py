"""Mise en page A3 : echelle, centrage et cartouche, communs a tous les formats."""

from __future__ import annotations

from dataclasses import dataclass

from briq.drawings.ir import Dessin, echelle_adaptee


@dataclass(frozen=True, slots=True)
class Feuille:
    """Feuille A3 a l'italienne, cotes en millimetres de papier."""

    largeur: float = 420.0
    hauteur: float = 297.0
    marge: float = 12.0
    cartouche: float = 26.0
    legende: float = 34.0

    @property
    def zone(self) -> tuple[float, float, float, float]:
        """Zone de dessin (x, y, largeur, hauteur), origine en bas a gauche."""
        x = self.marge
        y = self.marge + self.cartouche
        return (
            x,
            y,
            self.largeur - 2 * self.marge - self.legende,
            self.hauteur - 2 * self.marge - self.cartouche,
        )


@dataclass(frozen=True, slots=True)
class Cadrage:
    """Transformation modele -> feuille, en millimetres de papier."""

    echelle: int
    ox: float
    oy: float
    x0: float
    y0: float

    def point(self, x: float, y: float) -> tuple[float, float]:
        return (self.ox + (x - self.x0) / self.echelle, self.oy + (y - self.y0) / self.echelle)

    def longueur(self, valeur: float) -> float:
        return valeur / self.echelle


A3 = Feuille()
"""Feuille de reference du dossier : A3 a l'italienne."""


def cadrer(dessin: Dessin, feuille: Feuille = A3) -> Cadrage:
    """Choisit l'echelle la plus grande qui tienne, et centre le dessin."""
    zx, zy, zdx, zdy = feuille.zone
    echelle = dessin.echelle if dessin.echelle == 1 else echelle_adaptee(dessin, zdx, zdy)
    x0, y0, x1, y1 = dessin.emprise
    largeur, hauteur = (x1 - x0) / echelle, (y1 - y0) / echelle
    return Cadrage(
        echelle=echelle,
        ox=zx + max(0.0, (zdx - largeur) / 2),
        oy=zy + max(0.0, (zdy - hauteur) / 2),
        x0=x0,
        y0=y0,
    )
