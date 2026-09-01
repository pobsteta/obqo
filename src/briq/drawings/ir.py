"""Modele de dessin intermediaire : ce que le moteur decrit, avant tout format.

Les primitives sont exprimees en **millimetres du modele**, y vers le haut.
Chaque back-end decide ensuite quoi en faire : le SVG et le PDF appliquent une
echelle et centrent sur la feuille, le DXF dessine a l'echelle 1 dans l'espace
objet, comme l'attend un logiciel de CAO.

L'interet de passer par la : on teste le dessin (« l'elevation du mur M2 contient
45 rectangles de brique et 2 cotes ») au lieu de comparer des chaines de SVG, et
la mention obligatoire est apposee par le back-end, donc impossible a oublier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

MENTION = (
    "Document de calepinage — dimensionnement structural a valider "
    "par un bureau d'etudes bois (Eurocode 5, sismique)"
)

ECHELLES = (10, 20, 25, 50, 100, 200, 500)
"""Echelles normalisees, de la plus grande a la plus petite."""


class Calque(StrEnum):
    BRIQUE = "briques"
    DEMI = "demi-briques"
    ANGLE = "briques d'angle"
    ABOUT = "abouts fermes"
    TENON = "tenons"
    BAIE = "baies"
    LINTEAU = "linteaux"
    JAMBAGE = "jambages"
    CHAINAGE = "chainage"
    REFEND = "refends"
    COTE = "cotation"
    TEXTE = "texte"
    REPERE = "reperes"
    CADRE = "cadre"


@dataclass(frozen=True, slots=True)
class Style:
    trait: str
    remplissage: str | None
    epaisseur: float
    aci: int
    """Index de couleur AutoCAD, pour le DXF."""


STYLES: dict[Calque, Style] = {
    Calque.BRIQUE: Style("#4a4a4a", "#f2ece1", 0.25, 8),
    Calque.DEMI: Style("#4a4a4a", "#e4d9c3", 0.25, 42),
    Calque.ANGLE: Style("#8a3324", "#e9c9a8", 0.35, 1),
    Calque.ABOUT: Style("#4a4a4a", "#ddd0b6", 0.25, 30),
    Calque.TENON: Style("#8a3324", None, 0.2, 1),
    Calque.BAIE: Style("#2f5d7c", "#eef4f8", 0.4, 5),
    Calque.LINTEAU: Style("#7a5c1e", "#f0e3bf", 0.4, 2),
    Calque.JAMBAGE: Style("#7a5c1e", "#e2d3a6", 0.35, 2),
    Calque.CHAINAGE: Style("#3f6212", "#e6efd4", 0.4, 3),
    Calque.REFEND: Style("#4a4a4a", "#eae4d8", 0.3, 9),
    Calque.COTE: Style("#2f5d7c", None, 0.18, 5),
    Calque.TEXTE: Style("#1a1a1a", None, 0.18, 7),
    Calque.REPERE: Style("#6b6b6b", None, 0.18, 8),
    Calque.CADRE: Style("#1a1a1a", None, 0.5, 7),
}


class Ancrage(StrEnum):
    GAUCHE = "gauche"
    MILIEU = "milieu"
    DROITE = "droite"


@dataclass(frozen=True, slots=True)
class Trait:
    x1: float
    y1: float
    x2: float
    y2: float
    calque: Calque = Calque.BRIQUE
    pointille: bool = False


@dataclass(frozen=True, slots=True)
class Rect:
    x: float
    y: float
    dx: float
    dy: float
    calque: Calque = Calque.BRIQUE
    pointille: bool = False


@dataclass(frozen=True, slots=True)
class Texte:
    x: float
    y: float
    texte: str
    calque: Calque = Calque.TEXTE
    taille_mm: float = 2.5
    """Hauteur du texte **sur la feuille**, independante de l'echelle."""
    ancrage: Ancrage = Ancrage.MILIEU
    rotation: float = 0.0


@dataclass(frozen=True, slots=True)
class Polyligne:
    points: tuple[tuple[float, float], ...]
    calque: Calque = Calque.BRIQUE
    ferme: bool = False
    pointille: bool = False


Primitive = Trait | Rect | Texte | Polyligne


@dataclass(slots=True)
class Dessin:
    """Une planche : un dessin cote, avec son titre et son echelle."""

    titre: str
    sous_titre: str = ""
    primitives: list[Primitive] = field(default_factory=list)
    echelle: int | None = None
    """None : l'echelle normalisee la plus grande qui tienne sur la feuille."""
    emprise_imposee: tuple[float, float, float, float] | None = None
    """Cadre force, pour que les pages d'une meme planche restent alignees."""
    legende: list[tuple[str, Calque]] = field(default_factory=list)

    def ajouter(self, *primitives: Primitive) -> None:
        self.primitives.extend(primitives)

    @property
    def emprise(self) -> tuple[float, float, float, float]:
        """Boite englobante du dessin, en millimetres du modele."""
        if self.emprise_imposee is not None:
            return self.emprise_imposee
        xs: list[float] = []
        ys: list[float] = []
        for p in self.primitives:
            match p:
                case Rect():
                    xs += [p.x, p.x + p.dx]
                    ys += [p.y, p.y + p.dy]
                case Trait():
                    xs += [p.x1, p.x2]
                    ys += [p.y1, p.y2]
                case Polyligne():
                    xs += [x for x, _ in p.points]
                    ys += [y for _, y in p.points]
                case Texte():
                    xs.append(p.x)
                    ys.append(p.y)
        if not xs:
            return (0.0, 0.0, 1.0, 1.0)
        return (min(xs), min(ys), max(xs), max(ys))

    def calques_utilises(self) -> list[Calque]:
        vus = {p.calque for p in self.primitives}
        return [c for c in Calque if c in vus]

    def calques_de_legende(self) -> list[Calque]:
        """Calques porteurs d'information graphique : ni texte, ni cotation."""
        muets = {Calque.TEXTE, Calque.REPERE, Calque.COTE, Calque.CADRE}
        return [c for c in self.calques_utilises() if c not in muets]


# --- aides a la construction --------------------------------------------------


def cadre(x: float, y: float, dx: float, dy: float, calque: Calque, **kw: object) -> Rect:
    return Rect(x, y, dx, dy, calque, **kw)  # type: ignore[arg-type]


def coter_horizontal(
    dessin: Dessin, x1: float, x2: float, y: float, texte: str | None = None
) -> None:
    """Ligne de cote horizontale, avec ses pattes de rappel."""
    if x2 < x1:
        x1, x2 = x2, x1
    patte = (x2 - x1) * 0.02 or 20
    dessin.ajouter(
        Trait(x1, y, x2, y, Calque.COTE),
        Trait(x1, y - patte, x1, y + patte, Calque.COTE),
        Trait(x2, y - patte, x2, y + patte, Calque.COTE),
        Texte(
            (x1 + x2) / 2,
            y + patte * 0.6,
            texte if texte is not None else f"{int(x2 - x1)}",
            Calque.COTE,
            taille_mm=2.2,
        ),
    )


def coter_vertical(
    dessin: Dessin, y1: float, y2: float, x: float, texte: str | None = None
) -> None:
    if y2 < y1:
        y1, y2 = y2, y1
    patte = (y2 - y1) * 0.03 or 20
    dessin.ajouter(
        Trait(x, y1, x, y2, Calque.COTE),
        Trait(x - patte, y1, x + patte, y1, Calque.COTE),
        Trait(x - patte, y2, x + patte, y2, Calque.COTE),
        Texte(
            x - patte * 0.6,
            (y1 + y2) / 2,
            texte if texte is not None else f"{int(y2 - y1)}",
            Calque.COTE,
            taille_mm=2.2,
            rotation=90,
        ),
    )


def echelle_adaptee(dessin: Dessin, largeur_utile: float, hauteur_utile: float) -> int:
    """Plus grande echelle normalisee qui fait tenir le dessin sur la feuille."""
    x0, y0, x1, y1 = dessin.emprise
    largeur, hauteur = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
    for echelle in ECHELLES:
        if largeur / echelle <= largeur_utile and hauteur / echelle <= hauteur_utile:
            return echelle
    return ECHELLES[-1]


def nom_de_fichier(titre: str) -> str:
    """Nom de fichier stable et portable, derive du titre d'une planche."""
    propre = "".join(c if c.isalnum() else "-" for c in titre.lower())
    return "-".join(filter(None, propre.split("-")))
