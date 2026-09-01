"""Metre matiere : metres lineaires, plan de debit, masse et chiffrage."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal

from briq.bom.debit import PlanDeDebit, Solveur, Stock, solveur_par_defaut
from briq.bom.nomenclature import Nomenclature
from briq.model.plan import Parametres
from briq.model.systeme import Calepinage
from briq.rules.catalogue import PIECES

SECTION_CARRELET = (80, 80)
SECTION_MADRIER = (80, 240)


@dataclass(slots=True)
class Metre:
    carrelet: Counter[int] = field(default_factory=Counter)
    """Longueur debitee -> nombre de pieces, pour le carrelet 80x80."""
    madrier: Counter[int] = field(default_factory=Counter)
    """Idem pour le 80x240 (madriers, jambages, abouts de lisse)."""
    hetre: Counter[int] = field(default_factory=Counter)
    """Idem pour le rond de hetre 20 mm."""
    lamelle: Counter[int] = field(default_factory=Counter)
    """Lamelles-colles du commerce, en ligne distincte du metre."""
    barres_pleines_de_lisse: int = 0
    """Barres de 80x240 consommees entieres par les lisses de chainage."""
    longueur_barre_madrier: int = 4000
    """Retenue pour pouvoir reconstituer le lineaire des lisses."""
    debit_carrelet: PlanDeDebit | None = None
    debit_madrier: PlanDeDebit | None = None

    def _lineaire(self, lot: Counter[int]) -> int:
        return sum(longueur * n for longueur, n in lot.items())

    @property
    def lineaire_carrelet(self) -> int:
        return self._lineaire(self.carrelet)

    @property
    def lineaire_madrier(self) -> int:
        return self._lineaire(self.madrier)

    @property
    def lineaire_hetre(self) -> int:
        return self._lineaire(self.hetre)

    @property
    def lineaire_lamelle(self) -> int:
        return self._lineaire(self.lamelle)

    def masse_kg(self, masse_volumique: int) -> Decimal:
        """Masse de l'ossature epicea, chevilles de hetre exclues."""
        volume_mm3 = (
            self.lineaire_carrelet * SECTION_CARRELET[0] * SECTION_CARRELET[1]
            + self.lineaire_madrier * SECTION_MADRIER[0] * SECTION_MADRIER[1]
        )
        return (Decimal(volume_mm3) / Decimal(1_000_000_000) * masse_volumique).quantize(
            Decimal("0.1")
        )

    def barres_carrelet(self) -> int:
        return self.debit_carrelet.nombre_de_barres if self.debit_carrelet else 0

    def barres_madrier(self) -> int:
        base = self.debit_madrier.nombre_de_barres if self.debit_madrier else 0
        return base + self.barres_pleines_de_lisse


@dataclass(frozen=True, slots=True)
class Chiffrage:
    lignes: tuple[tuple[str, str, Decimal], ...]
    """Couples (poste, quantite lisible, montant)."""

    @property
    def total(self) -> Decimal:
        return sum((montant for _, _, montant in self.lignes), Decimal(0))


def _ml(millimetres: int) -> Decimal:
    return (Decimal(millimetres) / Decimal(1000)).quantize(Decimal("0.01"))


def metrer(
    calepinage: Calepinage,
    nomenclature: Nomenclature,
    parametres: Parametres,
    solveur: Solveur | None = None,
) -> Metre:
    """Compte les longueurs a debiter, puis optimise le debit de chaque stock."""
    metre = Metre(longueur_barre_madrier=parametres.longueur_barre_madrier)

    # Pieces de longueur fixe : leur section est au catalogue.
    for ref, quantite in nomenclature.pieces.items():
        piece = PIECES.get(ref)
        if piece is None or piece.longueur is None:
            continue
        section = (piece.largeur, piece.hauteur)
        if section == SECTION_CARRELET:
            metre.carrelet[piece.longueur] += quantite
        elif section == SECTION_MADRIER:
            metre.madrier[piece.longueur] += quantite
        elif piece.largeur == 20:
            metre.hetre[piece.longueur] += quantite

    # Pieces de longueur variable : leur longueur est celle de la pose.
    barre = parametres.longueur_barre_madrier
    for mur in calepinage.murs:
        elements = [*mur.elements, *(e for r in mur.rangs for e in r.elements)]
        for element in elements:
            if element.piece == "P9-LC":
                metre.lamelle[element.longueur] += element.quantite
            elif element.piece == "LISSE":
                # Le chainage se pose « d'une piece ou mi-bois cheville » : on
                # consomme des barres entieres, et l'about rejoint le debit.
                for _ in range(element.quantite):
                    pleines, reste = divmod(element.longueur, barre)
                    metre.barres_pleines_de_lisse += pleines
                    if reste:
                        metre.madrier[reste] += 1
            else:
                metre.madrier[element.longueur] += element.quantite

    solveur = solveur or solveur_par_defaut()
    metre.debit_carrelet = solveur.resoudre(
        metre.carrelet,
        Stock(
            "carrelet 80x80",
            parametres.longueur_barre,
            parametres.trait_de_scie,
            parametres.chute_minimale_reutilisable,
        ),
    )
    metre.debit_madrier = solveur.resoudre(
        metre.madrier,
        Stock(
            "madrier 80x240",
            barre,
            parametres.trait_de_scie,
            parametres.chute_minimale_reutilisable,
        ),
    )
    return metre


def chiffrer(metre: Metre, parametres: Parametres) -> Chiffrage:
    """Chiffrage a partir des prix du plan. Aucun prix renseigne : tout a zero."""
    lignes: list[tuple[str, str, Decimal]] = []
    barres = metre.barres_carrelet()
    lignes.append(
        (
            f"carrelet 80x80, barres de {parametres.longueur_barre} mm",
            f"{barres} barres",
            (Decimal(barres) * parametres.prix_barre).quantize(Decimal("0.01")),
        )
    )
    ml_madrier = _ml(
        metre.barres_pleines_de_lisse * parametres.longueur_barre_madrier
        + (metre.debit_madrier.longueur_achetee if metre.debit_madrier else 0)
    )
    lignes.append(
        (
            "madrier 80x240 (linteaux, jambages, lisses)",
            f"{ml_madrier} ml",
            (ml_madrier * parametres.prix_ml_madrier).quantize(Decimal("0.01")),
        )
    )
    ml_hetre = _ml(metre.lineaire_hetre)
    lignes.append(
        (
            "rond de hetre 20 mm",
            f"{ml_hetre} ml",
            (ml_hetre * parametres.prix_ml_hetre).quantize(Decimal("0.01")),
        )
    )
    if metre.lamelle:
        ml_lamelle = _ml(metre.lineaire_lamelle)
        lignes.append(
            (
                "lamelle-colle du commerce 80x240",
                f"{ml_lamelle} ml",
                (ml_lamelle * parametres.prix_ml_lamelle).quantize(Decimal("0.01")),
            )
        )
    return Chiffrage(tuple(lignes))
