"""Esquisse : une maison decrite par ses pieces, avant tout calepinage.

C'est le modele que manipule l'editeur graphique. Une esquisse n'est pas un plan
obqo : elle ignore l'epaisseur des murs, la grille de 240 et les regles de baie.
Elle sert a dessiner vite, et `engine.esquisse` la convertit ensuite en plan.

Convention : **les rectangles se touchent**, et chaque ligne partagee est un axe
de mur. Le contour dessine est le nu exterieur du batiment ; les lignes
interieures sont des axes de refend, centres, qui mangent 120 mm de chaque cote.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from obqo.units import EPAISSEUR_MUR, HAUTEUR_TREMIE_FENETRE, HAUTEUR_TREMIE_PORTE


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


class Baie(Base):
    """Une baie posee sur un axe de mur, avant que les murs aient un nom.

    Elle est decrite par le **segment** qu'elle occupe sur cet axe, et non par un
    mur et une abscisse : dans l'esquisse les murs n'existent pas encore, ils se
    deduisent des pieces. La conversion retrouve ensuite le mur porteur et
    l'abscisse de la rive.
    """

    id: str
    type: Literal["porte", "fenetre", "porte_fenetre"] = "fenetre"
    depart: tuple[int, int]
    arrivee: tuple[int, int]
    allege: Annotated[int, Field(ge=0)] = 960
    hauteur: Annotated[int, Field(gt=0)] = HAUTEUR_TREMIE_FENETRE

    @model_validator(mode="before")
    @classmethod
    def _defauts_du_type(cls, valeurs: object) -> object:
        """Une porte part du sol, et monte plus haut qu'une fenetre.

        L'allege est forcee a zero ; la hauteur n'est *completee* que si elle
        manque, pour ne jamais ecraser une cote choisie. Normaliser ici plutot
        qu'a la conversion fait dire la meme chose au modele, au fichier
        enregistre et au formulaire.
        """
        if not isinstance(valeurs, dict):
            return valeurs
        if valeurs.get("type") not in ("porte", "porte_fenetre"):
            return valeurs
        defauts = {"allege": 0}
        if valeurs.get("hauteur") is None:
            defauts["hauteur"] = HAUTEUR_TREMIE_PORTE
        return {**valeurs, **defauts}

    @model_validator(mode="after")
    def _segment_axial(self) -> Self:
        if self.depart == self.arrivee:
            raise ValueError(f"la baie « {self.id} » est reduite a un point")
        if self.depart[0] != self.arrivee[0] and self.depart[1] != self.arrivee[1]:
            raise ValueError(f"la baie « {self.id} » n'est ni horizontale ni verticale")
        return self

    @property
    def largeur(self) -> int:
        return abs(self.arrivee[0] - self.depart[0]) + abs(self.arrivee[1] - self.depart[1])

    @property
    def horizontale(self) -> bool:
        return self.depart[1] == self.arrivee[1]

    def sur(self, depart: tuple[int, int], arrivee: tuple[int, int]) -> bool:
        """La baie repose-t-elle entierement sur ce segment de mur ?"""
        if (depart[0] == arrivee[0]) == self.horizontale:
            return False
        if depart[0] == arrivee[0]:  # mur vertical
            return self.depart[0] == depart[0] and all(
                min(depart[1], arrivee[1]) <= y <= max(depart[1], arrivee[1])
                for y in (self.depart[1], self.arrivee[1])
            )
        return self.depart[1] == depart[1] and all(
            min(depart[0], arrivee[0]) <= x <= max(depart[0], arrivee[0])
            for x in (self.depart[0], self.arrivee[0])
        )


class MurInterieur(Base):
    """Mur interieur trace a la souris, avant que les murs aient un nom.

    Comme une baie, il est decrit par le **segment** qu'il occupe. Le type dit
    l'intention ; la conversion tranche : un refend qui ne traverse pas tout le
    batiment ne peut pas etre porteur, et redevient une cloison.
    """

    id: str
    type: Literal["refend", "cloison"] = "refend"
    depart: tuple[int, int]
    arrivee: tuple[int, int]

    @model_validator(mode="after")
    def _segment_axial(self) -> Self:
        if self.depart == self.arrivee:
            raise ValueError(f"le mur « {self.id} » est reduit a un point")
        if self.depart[0] != self.arrivee[0] and self.depart[1] != self.arrivee[1]:
            raise ValueError(f"le mur « {self.id} » n'est ni horizontal ni vertical")
        return self

    @property
    def horizontal(self) -> bool:
        return self.depart[1] == self.arrivee[1]

    @property
    def longueur(self) -> int:
        return abs(self.arrivee[0] - self.depart[0]) + abs(self.arrivee[1] - self.depart[1])


class Esquisse(Base):
    hauteur_sous_chainage: Annotated[int, Field(gt=0)] = 2640
    nom: str = "esquisse"
    pieces: Annotated[list[Piece], Field(min_length=1)]
    baies: list[Baie] = []
    murs: list[MurInterieur] = []
    """Murs interieurs traces a la main, qui s'ajoutent a ceux que le dessin
    des pieces laisse deja deduire."""

    @model_validator(mode="after")
    def _identifiants_de_baie_uniques(self) -> Self:
        vus = [b.id for b in self.baies]
        if len(vus) != len(set(vus)):
            raise ValueError("deux baies portent le meme identifiant")
        return self

    @model_validator(mode="after")
    def _identifiants_de_mur_uniques(self) -> Self:
        vus = [m.id for m in self.murs]
        if len(vus) != len(set(vus)):
            raise ValueError("deux murs interieurs portent le meme identifiant")
        return self

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
