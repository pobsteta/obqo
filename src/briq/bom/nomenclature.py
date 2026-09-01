"""Nomenclature : combien de briques, de pieces et de chevilles, et ou.

Tout se derive du calepinage et des tables de `rules/catalogue.py`. Rien n'est
recompte a partir des dessins : le modele de briques posees est la seule source.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from briq.model.systeme import Calepinage, MurCalepine, Ref
from briq.rules.catalogue import PIECES, composition

DESIGNATIONS: dict[str, str] = {
    "480-S": "brique standard, deux abouts ouverts",
    "480-A": "brique a un about ferme",
    "480-AA": "brique a deux abouts fermes",
    "480-ANR": "brique d'angle filante",
    "240-S": "demi-brique standard",
    "240-A": "demi-brique a un about ferme",
    "240-AA": "demi-brique a deux abouts fermes",
    "240-ANR": "demi-brique d'angle filante",
    "P9-LC": "lamelle-colle du commerce, en substitution du madrier cheville",
}


@dataclass(frozen=True, slots=True)
class Ligne:
    categorie: str
    ref: str
    designation: str
    quantite: int
    localisation: str
    detail: str = ""

    def __str__(self) -> str:
        base = f"{self.ref} | {self.designation} | {self.quantite} pieces | {self.localisation}"
        return f"{base} | {self.detail}" if self.detail else base


@dataclass(slots=True)
class Nomenclature:
    lignes: list[Ligne] = field(default_factory=list)
    briques_par_mur: dict[str, Counter[str]] = field(default_factory=dict)
    pieces_par_mur: dict[str, Counter[str]] = field(default_factory=dict)

    @property
    def pieces(self) -> Counter[str]:
        """Total de chaque piece P1..P10 et cheville C1..C3, atelier et chantier."""
        total: Counter[str] = Counter()
        for mur in self.pieces_par_mur.values():
            total.update(mur)
        return total

    def par_categorie(self, categorie: str) -> list[Ligne]:
        return [ligne for ligne in self.lignes if ligne.categorie == categorie]


def _localisation_briques(calepinage: Calepinage, ref: Ref) -> str:
    murs = sorted({b.mur for b in calepinage.briques if b.ref is ref})
    rangs = sorted({b.rang for b in calepinage.briques if b.ref is ref})
    if not rangs:
        return ""
    pairs = all(r % 2 == 0 for r in rangs)
    impairs = all(r % 2 == 1 for r in rangs)
    quels = "rangs pairs" if pairs else "rangs impairs" if impairs else "tous rangs"
    return f"murs {'/'.join(murs)}, {quels}"


def _detail_brique(ref: Ref, quantite: int) -> str:
    parts = []
    for piece, n in sorted(composition(ref).items()):
        if piece in ("P5-A", "P8"):
            parts.append(f"{n * quantite} x {piece}")
    if ref.value.endswith("ANR"):
        parts.append(f"{quantite} x percage de montant traversant")
    return "inclut " + ", ".join(parts) if parts else ""


def _pieces_du_mur(mur: MurCalepine) -> Counter[str]:
    """Pieces et chevilles imputables a un mur : atelier des briques + chantier."""
    total: Counter[str] = Counter()
    for brique in mur.briques:
        total.update(composition(brique.ref))
    for rang in mur.rangs:
        for q in rang.quincaillerie:
            for ref, n in q.pieces:
                total[ref] += n
    for element in [*mur.elements, *(e for r in mur.rangs for e in r.elements)]:
        total[element.piece] += element.quantite
    return total


def nomenclaturer(calepinage: Calepinage) -> Nomenclature:
    """Construit la nomenclature complete du calepinage."""
    nomenclature = Nomenclature()

    for mur in calepinage.murs:
        nomenclature.briques_par_mur[mur.id] = Counter(b.ref.value for b in mur.briques)
        nomenclature.pieces_par_mur[mur.id] = _pieces_du_mur(mur)

    for ref, quantite in sorted(calepinage.compte_briques().items()):
        nomenclature.lignes.append(
            Ligne(
                categorie="brique",
                ref=ref.value,
                designation=DESIGNATIONS[ref.value],
                quantite=quantite,
                localisation=_localisation_briques(calepinage, ref),
                detail=_detail_brique(ref, quantite),
            )
        )

    total = nomenclature.pieces
    longueurs_variables: dict[str, Counter[int]] = {}
    for mur in calepinage.murs:
        for element in [*mur.elements, *(e for r in mur.rangs for e in r.elements)]:
            if PIECES.get(element.piece, None) is None or PIECES[element.piece].longueur is None:
                longueurs_variables.setdefault(element.piece, Counter())[element.longueur] += (
                    element.quantite
                )

    for nom, quantite in sorted(total.items()):
        piece = PIECES.get(nom)
        if piece is None:  # P9-LC : substitution, decrite par sa longueur
            longueurs = longueurs_variables.get(nom, Counter())
            nomenclature.lignes.append(
                Ligne(
                    categorie="element",
                    ref=nom,
                    designation=DESIGNATIONS.get(nom, nom),
                    quantite=quantite,
                    localisation="voir metre",
                    detail=", ".join(f"{n} x {L} mm" for L, n in sorted(longueurs.items())),
                )
            )
            continue
        categorie = "cheville" if piece.largeur == 20 else "piece"
        if piece.longueur is None:
            categorie = "element"
            longueurs = longueurs_variables.get(nom, Counter())
            detail = ", ".join(f"{n} x {L} mm" for L, n in sorted(longueurs.items()))
            section = f"{piece.largeur}x{piece.hauteur}"
        else:
            detail = ""
            section = f"{piece.largeur}x{piece.hauteur}x{piece.longueur}"
        murs = sorted(m for m, c in nomenclature.pieces_par_mur.items() if c.get(nom))
        nomenclature.lignes.append(
            Ligne(
                categorie=categorie,
                ref=nom,
                designation=f"{piece.designation} ({section})",
                quantite=quantite,
                localisation=f"murs {'/'.join(murs)}" if murs else "",
                detail=detail,
            )
        )

    return nomenclature
