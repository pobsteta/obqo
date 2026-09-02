"""Esquisse : une maison decrite par ses pieces, avant tout calepinage.

C'est le modele que manipule l'editeur graphique. Une esquisse n'est pas un plan
BRIQ : elle ignore l'epaisseur des murs, la grille de 240 et les regles de baie.
Elle sert a dessiner vite, et `engine.esquisse` la convertit ensuite en plan.

Convention : **les rectangles se touchent**, et chaque ligne partagee est un axe
de mur. Le contour dessine est le nu exterieur du batiment ; les lignes
interieures sont des axes de refend, centres, qui mangent 120 mm de chaque cote.
"""

from __future__ import annotations

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from briq.units import EPAISSEUR_MUR


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Piece(Base):
    """Un rectangle du plan, en millimetres, cotes de mur a mur (axes compris)."""

    nom: str = "piece"
    x: int
    y: int
    largeur: Annotated[int, Field(gt=0)]
    hauteur: Annotated[int, Field(gt=0)]

    @property
    def droite(self) -> int:
        return self.x + self.largeur

    @property
    def haut(self) -> int:
        return self.y + self.hauteur

    def chevauche(self, autre: Piece) -> bool:
        return (
            self.x < autre.droite
            and autre.x < self.droite
            and self.y < autre.haut
            and autre.y < self.haut
        )

    def interieur(self, murs_exterieurs: tuple[bool, bool, bool, bool]) -> tuple[int, int]:
        """Dimensions habitables : 240 par mur exterieur, 120 par refend.

        `murs_exterieurs` designe les cotes (gauche, droite, bas, haut) qui
        donnent sur l'exterieur du batiment.
        """
        gauche, droite, bas, haut = murs_exterieurs
        demi = EPAISSEUR_MUR // 2
        return (
            self.largeur
            - (EPAISSEUR_MUR if gauche else demi)
            - (EPAISSEUR_MUR if droite else demi),
            self.hauteur - (EPAISSEUR_MUR if bas else demi) - (EPAISSEUR_MUR if haut else demi),
        )


class Esquisse(Base):
    hauteur_sous_chainage: Annotated[int, Field(gt=0)] = 2640
    nom: str = "esquisse"
    pieces: Annotated[list[Piece], Field(min_length=1)]

    @model_validator(mode="after")
    def _sans_chevauchement(self) -> Self:
        for i, piece in enumerate(self.pieces):
            for autre in self.pieces[i + 1 :]:
                if piece.chevauche(autre):
                    raise ValueError(
                        f"les pieces « {piece.nom} » et « {autre.nom} » se chevauchent"
                    )
        return self

    @property
    def abscisses(self) -> list[int]:
        return sorted({p.x for p in self.pieces} | {p.droite for p in self.pieces})

    @property
    def ordonnees(self) -> list[int]:
        return sorted({p.y for p in self.pieces} | {p.haut for p in self.pieces})
