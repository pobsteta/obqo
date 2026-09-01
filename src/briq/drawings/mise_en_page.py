"""Mise en page A3 : echelle, centrage et cartouche, communs a tous les formats."""

from __future__ import annotations

from dataclasses import dataclass

from briq.drawings.ir import Dessin, Polyligne, Rect, Texte, Trait, echelle_adaptee


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


ECHELLE_DE_LISIBILITE = 50
"""Au-dela de 1:50, les reperes portes sur les briques deviennent illisibles :
on prefere pagineer une elevation trop longue plutot que de la reduire."""

RECOUVREMENT = 960
"""Bande commune entre deux pages, en millimetres du modele : deux briques."""


A3 = Feuille()
"""Feuille de reference du dossier : A3 a l'italienne."""


def cadrer(dessin: Dessin, feuille: Feuille = A3) -> Cadrage:
    """Choisit l'echelle la plus grande qui tienne, et centre le dessin."""
    zx, zy, zdx, zdy = feuille.zone
    echelle = dessin.echelle or echelle_adaptee(dessin, zdx, zdy)
    x0, y0, x1, y1 = dessin.emprise
    largeur, hauteur = (x1 - x0) / echelle, (y1 - y0) / echelle
    return Cadrage(
        echelle=echelle,
        ox=zx + max(0.0, (zdx - largeur) / 2),
        oy=zy + max(0.0, (zdy - hauteur) / 2),
        x0=x0,
        y0=y0,
    )


def _intersecte(primitive: object, xmin: float, xmax: float) -> bool:
    match primitive:
        case Rect():
            return primitive.x <= xmax and primitive.x + primitive.dx >= xmin
        case Trait():
            return min(primitive.x1, primitive.x2) <= xmax and (
                max(primitive.x1, primitive.x2) >= xmin
            )
        case Polyligne():
            xs = [x for x, _ in primitive.points]
            return min(xs) <= xmax and max(xs) >= xmin
        case Texte():
            return xmin <= primitive.x <= xmax
    return False


def paginer(
    dessin: Dessin,
    feuille: Feuille = A3,
    echelle_maxi: int = ECHELLE_DE_LISIBILITE,
    recouvrement: int = RECOUVREMENT,
) -> list[Dessin]:
    """Decoupe une planche trop longue en plusieurs feuilles qui se recouvrent.

    Un mur de 14 m tient au 1:50 sur un A3 ; un mur de 25 m n'y tiendrait qu'au
    1:100, ou les reperes portes sur les briques ne se lisent plus. Plutot que de
    reduire, on decoupe en bandes avec une zone commune, comme sur un plan de
    chantier. Les pages partagent le meme cadre pour rester comparables.
    """
    _, _, zdx, _ = feuille.zone
    x0, y0, x1, y1 = dessin.emprise
    largeur = x1 - x0
    if dessin.echelle is not None or largeur / echelle_maxi <= zdx:
        return [dessin]

    utile = zdx * echelle_maxi
    pas = utile - recouvrement
    pages = max(1, -(-int(largeur - recouvrement) // int(pas)))
    decoupes: list[Dessin] = []
    for index in range(pages):
        debut = x0 + index * pas
        fin = min(debut + utile, x1)
        decoupes.append(
            Dessin(
                titre=f"{dessin.titre} ({index + 1}/{pages})",
                sous_titre=dessin.sous_titre,
                primitives=[p for p in dessin.primitives if _intersecte(p, debut, fin)],
                echelle=echelle_maxi,
                emprise_imposee=(debut, y0, fin, y1),
                legende=list(dessin.legende),
            )
        )
    return decoupes
