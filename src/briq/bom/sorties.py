"""Rendu des livrables : CSV pour l'exploitation, tableaux lisibles pour l'ecran."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from io import StringIO
from pathlib import Path

from briq.bom.metre import Chiffrage, Metre
from briq.bom.nomenclature import Nomenclature
from briq.model.systeme import Calepinage

Ligne = Sequence[object]


def ecrire_csv(chemin: Path, entetes: Sequence[str], lignes: Iterable[Ligne]) -> None:
    with chemin.open("w", encoding="utf-8", newline="") as flux:
        graveur = csv.writer(flux, delimiter=";")
        graveur.writerow(entetes)
        graveur.writerows(lignes)


def tableau(entetes: Sequence[str], lignes: Sequence[Ligne], titre: str = "") -> str:
    """Tableau texte aligne, sans dependance."""
    cellules = [[str(c) for c in ligne] for ligne in lignes]
    largeurs = [
        max(len(entetes[i]), *(len(ligne[i]) for ligne in cellules))
        if cellules
        else len(entetes[i])
        for i in range(len(entetes))
    ]
    numerique = [
        all(
            ligne[i].replace(" ", "").replace(",", "").replace("%", "").isdigit()
            for ligne in cellules
        )
        if cellules
        else False
        for i in range(len(entetes))
    ]

    def rendre(valeurs: Sequence[str]) -> str:
        return "  ".join(
            v.rjust(largeurs[i]) if numerique[i] else v.ljust(largeurs[i])
            for i, v in enumerate(valeurs)
        )

    sortie = StringIO()
    if titre:
        print(f"\n{titre}", file=sortie)
    print(rendre(entetes), file=sortie)
    print("  ".join("-" * largeur for largeur in largeurs), file=sortie)
    for ligne in cellules:
        print(rendre(ligne), file=sortie)
    return sortie.getvalue()


# --- nomenclature -------------------------------------------------------------

ENTETES_NOMENCLATURE = (
    "categorie",
    "reference",
    "designation",
    "quantite",
    "localisation",
    "detail",
)


def lignes_nomenclature(nomenclature: Nomenclature) -> list[Ligne]:
    return [
        (
            ligne.categorie,
            ligne.ref,
            ligne.designation,
            ligne.quantite,
            ligne.localisation,
            ligne.detail,
        )
        for ligne in nomenclature.lignes
    ]


ENTETES_PAR_MUR = ("mur", "reference", "quantite")


def lignes_par_mur(nomenclature: Nomenclature) -> list[Ligne]:
    lignes: list[Ligne] = []
    for mur in sorted(nomenclature.briques_par_mur):
        for ref, n in sorted(nomenclature.briques_par_mur[mur].items()):
            lignes.append((mur, ref, n))
        for ref, n in sorted(nomenclature.pieces_par_mur[mur].items()):
            lignes.append((mur, ref, n))
    return lignes


# --- metre --------------------------------------------------------------------

ENTETES_METRE = ("stock", "longueur_mm", "pieces", "lineaire_mm")


def lignes_metre(metre: Metre) -> list[Ligne]:
    lignes: list[Ligne] = []
    for stock, lot in (
        ("carrelet 80x80", metre.carrelet),
        ("madrier 80x240", metre.madrier),
        ("hetre rond 20", metre.hetre),
        ("lamelle-colle 80x240", metre.lamelle),
    ):
        for longueur, n in sorted(lot.items()):
            lignes.append((stock, longueur, n, longueur * n))
    return lignes


# --- debit --------------------------------------------------------------------

ENTETES_DEBIT = ("stock", "patron", "barres", "utile_mm", "chute_mm", "chute_reutilisable")


def lignes_debit(metre: Metre) -> list[Ligne]:
    lignes: list[Ligne] = []
    for plan in (metre.debit_carrelet, metre.debit_madrier):
        if plan is None:
            continue
        for barre in plan.barres:
            chute = barre.patron.chute(plan.stock)
            lignes.append(
                (
                    plan.stock.designation,
                    str(barre.patron),
                    barre.repetitions,
                    barre.patron.utile,
                    chute,
                    "oui" if chute >= plan.stock.chute_minimale_reutilisable else "non",
                )
            )
    for plan in (metre.debit_carrelet, metre.debit_madrier):
        if plan is None:
            continue
        for longueur, n in sorted(plan.pieces_en_trop.items()):
            lignes.append(
                (
                    plan.stock.designation,
                    f"piece en trop de {longueur} mm",
                    0,
                    longueur * n,
                    0,
                    "rechange",
                )
            )
    if metre.barres_pleines_de_lisse:
        lignes.append(
            (
                "madrier 80x240",
                "barre entiere de lisse de chainage",
                metre.barres_pleines_de_lisse,
                0,
                0,
                "non",
            )
        )
    return lignes


# --- synthese ecran -----------------------------------------------------------


def synthese(
    calepinage: Calepinage,
    nomenclature: Nomenclature,
    metre: Metre,
    chiffrage: Chiffrage,
    masse_volumique: int,
) -> str:
    sortie = StringIO()
    briques = nomenclature.par_categorie("brique")
    print(
        tableau(
            ("reference", "designation", "quantite", "localisation"),
            [(b.ref, b.designation, b.quantite, b.localisation) for b in briques],
            titre=f"BRIQUES ({sum(b.quantite for b in briques)} au total)",
        ),
        file=sortie,
        end="",
    )

    lisses = metre.barres_pleines_de_lisse * metre.longueur_barre_madrier
    lots = [
        ("carrelet 80x80", metre.lineaire_carrelet, metre.barres_carrelet()),
        ("madrier 80x240", metre.lineaire_madrier + lisses, metre.barres_madrier()),
        ("hetre rond 20", metre.lineaire_hetre, 0),
    ]
    print(
        tableau(
            ("stock", "lineaire (m)", "barres"),
            [(nom, f"{ml / 1000:.1f}", barres or "-") for nom, ml, barres in lots],
            titre="METRE MATIERE",
        ),
        file=sortie,
        end="",
    )

    for plan in (metre.debit_carrelet, metre.debit_madrier):
        if plan is None or not plan.barres:
            continue
        etat = "optimum prouve" if plan.optimal else "solution approchee"
        print(
            tableau(
                ("patron de decoupe", "barres", "chute (mm)"),
                [(str(b.patron), b.repetitions, b.patron.chute(plan.stock)) for b in plan.barres],
                titre=(
                    f"DEBIT {plan.stock.designation} — {plan.nombre_de_barres} barres de "
                    f"{plan.stock.longueur_barre} mm, chute {100 * plan.taux_de_chute:.2f} %, "
                    f"{plan.patrons_distincts} patrons, "
                    f"{plan.surproduction / 1000:.1f} m de rechange "
                    f"({plan.solveur}, {etat})"
                ),
            ),
            file=sortie,
            end="",
        )

    print(f"\nMasse d'ossature epicea : {metre.masse_kg(masse_volumique)} kg", file=sortie)
    if chiffrage.total:
        print(
            tableau(
                ("poste", "quantite", "montant"),
                [(poste, quantite, f"{montant}") for poste, quantite, montant in chiffrage.lignes],
                titre="CHIFFRAGE",
            ),
            file=sortie,
            end="",
        )
        print(f"\nTotal : {chiffrage.total}", file=sortie)
    return sortie.getvalue()
