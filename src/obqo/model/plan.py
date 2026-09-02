"""Schema d'entree du plan de maison (frontiere de validation, Pydantic v2).

Ce module est la **seule** porte d'entree des donnees utilisateur. Tout ce qui en
sort est deja valide : sur grille, coherent, et exprime en millimetres entiers.
Le schema JSON versionne se derive de ces modeles (`obqo schema`).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from obqo.units import GRILLE, HAUTEUR_RANG, sur_grille

VERSION_SCHEMA: Final[Literal["1"]] = "1"

Direction = Literal["est", "ouest", "nord", "sud"]


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class Segment(Base):
    """Un deplacement du trace en « tortue »."""

    direction: Direction
    longueur: Annotated[int, Field(gt=0)]


class Trace(Base):
    """Contour saisi par deplacements relatifs : la fermeture est verifiee."""

    depart: tuple[int, int] = (0, 0)
    segments: Annotated[list[Segment], Field(min_length=3)]

    def points(self) -> list[tuple[int, int]]:
        pas = {"est": (1, 0), "ouest": (-1, 0), "nord": (0, 1), "sud": (0, -1)}
        x, y = self.depart
        sommets = [(x, y)]
        for s in self.segments:
            dx, dy = pas[s.direction]
            x, y = x + dx * s.longueur, y + dy * s.longueur
            sommets.append((x, y))
        return sommets


class Contour(Base):
    """Contour exterieur des murs : soit une polyligne absolue, soit un trace."""

    points: list[tuple[int, int]] | None = None
    trace: Trace | None = None

    @model_validator(mode="after")
    def _une_seule_forme(self) -> Self:
        if (self.points is None) == (self.trace is None):
            raise ValueError("renseigner exactement l'un de « points » ou « trace »")
        if self.points is not None and len(self.points) < 3:
            raise ValueError("un contour demande au moins 3 points")
        return self

    def sommets(self) -> list[tuple[int, int]]:
        """Sommets du contour, sans repeter le point de fermeture."""
        if self.trace is not None:
            suivis = self.trace.points()
            if suivis[0] != suivis[-1]:
                raise ValueError(
                    f"le trace ne se referme pas : depart {suivis[0]}, arrivee {suivis[-1]}"
                )
            return suivis[:-1]
        assert self.points is not None
        bruts: list[tuple[int, int]] = [(x, y) for x, y in self.points]
        return bruts[:-1] if bruts[0] == bruts[-1] else bruts


class Ouverture(Base):
    """Une baie. Toutes les cotes portent sur la **tremie**, pas sur le passage
    libre : les jambages P10 se logent a l'interieur de la tremie."""

    id: str
    mur: str
    type: Literal["porte", "fenetre", "porte_fenetre"]
    position: Annotated[int, Field(ge=0)]
    """Abscisse de la rive gauche de la tremie, depuis l'origine du mur."""
    largeur: Annotated[int, Field(gt=0)]
    allege: Annotated[int, Field(ge=0)] = 0
    hauteur: Annotated[int, Field(gt=0)]

    @model_validator(mode="after")
    def _porte_sans_allege(self) -> Self:
        if self.type in ("porte", "porte_fenetre") and self.allege:
            raise ValueError(f"{self.id} : une {self.type} n'a pas d'allege")
        return self

    @property
    def fin(self) -> int:
        return int(self.position + self.largeur)

    @property
    def rang_bas(self) -> int:
        return int(self.allege // HAUTEUR_RANG)

    @property
    def rang_linteau(self) -> int:
        return int((self.allege + self.hauteur) // HAUTEUR_RANG)


class Refend(Base):
    """Mur interieur porteur, attache a deux murs existants."""

    id: str
    depart: tuple[int, int]
    arrivee: tuple[int, int]


class Parametres(Base):
    longueur_barre: Annotated[int, Field(gt=0)] = 4000
    """Longueur d'approvisionnement du carrelet 80x80. Voir
    docs/etudes/longueur-de-barre.md : 4 m est le choix le plus robuste."""

    longueur_barre_madrier: Annotated[int, Field(gt=0)] = 4000
    """Longueur d'approvisionnement du 80x240 : stock distinct du carrelet."""
    trait_de_scie: Annotated[int, Field(ge=0)] = 4
    chute_minimale_reutilisable: Annotated[int, Field(ge=0)] = 240
    hors_grille: Literal["refuser", "arrondir"] = "refuser"
    prix_barre: Decimal = Decimal("0")
    prix_ml_hetre: Decimal = Decimal("0")
    prix_ml_madrier: Decimal = Decimal("0")
    prix_ml_lamelle: Decimal = Decimal("0")
    masse_volumique_epicea: Annotated[int, Field(gt=0)] = 450
    """kg/m3, pour le metre de masse."""


class Plan(Base):
    schema_: str | None = Field(default=None, alias="$schema")
    """Reference au schema JSON, pour l'autocompletion dans l'editeur."""

    version: Literal["1"] = VERSION_SCHEMA
    nom: str = "sans nom"
    hauteur_sous_chainage: Annotated[int, Field(gt=0)]
    contour: Contour
    ouvertures: list[Ouverture] = []
    refends: list[Refend] = []
    parametres: Parametres = Parametres()

    @model_validator(mode="after")
    def _hauteur_sur_grille(self) -> Self:
        if not sur_grille(self.hauteur_sous_chainage):
            raise ValueError(
                f"hauteur sous chainage {self.hauteur_sous_chainage} mm : "
                f"multiple de {GRILLE} attendu"
            )
        return self

    @model_validator(mode="after")
    def _identifiants_uniques(self) -> Self:
        for champ, objets in (("ouvertures", self.ouvertures), ("refends", self.refends)):
            vus = [o.id for o in objets]
            if len(vus) != len(set(vus)):
                raise ValueError(f"identifiants dupliques dans {champ}")
        return self

    @property
    def rangs(self) -> int:
        return int(self.hauteur_sous_chainage // HAUTEUR_RANG)
