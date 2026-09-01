"""Nomenclature et metre : coherence croisee avec le calepinage et le brief."""

from __future__ import annotations

from collections import Counter

import pytest

from briq.bom.debit import GloutonDecroissant
from briq.bom.metre import chiffrer, metrer
from briq.bom.nomenclature import nomenclaturer
from briq.bom.sorties import lignes_debit, lignes_metre, lignes_nomenclature, tableau
from briq.engine.calepinage import calepiner
from briq.model.plan import Plan
from briq.rules.catalogue import PIECES, REFERENCE_BRIEF, composition, longueur_carrelet


@pytest.fixture(scope="module")
def dossier(maison: Plan):
    calepinage, _ = calepiner(maison)
    assert calepinage is not None
    nomenclature = nomenclaturer(calepinage)
    metre = metrer(calepinage, nomenclature, maison.parametres, GloutonDecroissant())
    return calepinage, nomenclature, metre


def test_les_sous_totaux_par_mur_font_le_total(dossier) -> None:
    calepinage, nomenclature, _ = dossier
    briques: Counter[str] = Counter()
    for compte in nomenclature.briques_par_mur.values():
        briques.update(compte)
    assert briques == Counter({r.value: n for r, n in calepinage.compte_briques().items()})


def test_le_metre_egale_la_somme_des_pieces_de_la_nomenclature(dossier) -> None:
    """Controle croise exige au paragraphe 2.3.3 du brief."""
    _, nomenclature, metre = dossier
    attendu = sum(
        n * piece.longueur
        for ref, n in nomenclature.pieces.items()
        if (piece := PIECES.get(ref)) is not None
        and piece.longueur is not None
        and (piece.largeur, piece.hauteur) == (80, 80)
    )
    assert metre.lineaire_carrelet == attendu


def test_le_carrelet_par_brique_reste_proche_de_la_constante_du_brief(dossier) -> None:
    """4,16 m par brique 480 au paragraphe 1.8 : garde-fou sur le total."""
    calepinage, _, metre = dossier
    briques = len(calepinage.briques)
    par_brique = metre.lineaire_carrelet / briques / 1000
    assert 3.9 <= par_brique <= 4.4, par_brique
    assert abs(par_brique - REFERENCE_BRIEF[480].carrelet_ml) < 0.3


def test_le_debit_couvre_exactement_le_metre(dossier) -> None:
    _, _, metre = dossier
    for plan, demande in (
        (metre.debit_carrelet, metre.carrelet),
        (metre.debit_madrier, metre.madrier),
    ):
        assert plan is not None
        produit = plan.produit()
        for longueur, besoin in demande.items():
            assert produit[longueur] >= besoin


def test_les_jambages_font_la_hauteur_de_la_baie(maison: Plan, dossier) -> None:
    """Regle actee D1 : le jambage court du dessus de l'allege au linteau.

    Deux jambages par baie, quatre au-dela de 1 800 mm de tremie (doubles).
    """
    from briq.units import LARGEUR_BAIE_JAMBAGE_DOUBLE

    calepinage, _, _ = dossier
    attendues: Counter[int] = Counter()
    for o in maison.ouvertures:
        attendues[o.hauteur] += 4 if o.largeur > LARGEUR_BAIE_JAMBAGE_DOUBLE else 2
    posees: Counter[int] = Counter()
    for mur in calepinage.murs:
        for element in mur.elements:
            if element.piece == "P10":
                posees[element.longueur] += element.quantite
    assert posees == attendues


def test_les_madriers_font_la_portee_plus_480(maison: Plan, dossier) -> None:
    calepinage, _, _ = dossier
    attendues = Counter(o.largeur + 480 for o in maison.ouvertures)
    posees: Counter[int] = Counter()
    for mur in calepinage.murs:
        for element in mur.elements:
            if element.piece in ("P9", "P9-LC"):
                posees[element.longueur] += element.quantite // 2
    assert posees == attendues


def test_la_masse_est_coherente_avec_le_brief(maison: Plan, dossier) -> None:
    """12,3 kg par brique 480 au paragraphe 1.8, madriers et lisses en plus."""
    calepinage, _, metre = dossier
    masse = float(metre.masse_kg(maison.parametres.masse_volumique_epicea))
    par_brique = masse / len(calepinage.briques)
    assert 11.0 <= par_brique <= 14.0, par_brique


def test_le_chiffrage_est_nul_sans_prix(maison: Plan, dossier) -> None:
    _, _, metre = dossier
    assert chiffrer(metre, maison.parametres).total == 0


def test_le_chiffrage_suit_les_prix(maison: Plan, dossier) -> None:
    _, _, metre = dossier
    parametres = maison.parametres.model_copy(update={"prix_barre": 32})
    chiffrage = chiffrer(metre, parametres)
    assert chiffrage.total == metre.barres_carrelet() * 32


def test_les_sorties_csv_sont_completes(dossier) -> None:
    _, nomenclature, metre = dossier
    assert len(lignes_nomenclature(nomenclature)) == len(nomenclature.lignes)
    assert lignes_metre(metre) and lignes_debit(metre)
    rendu = tableau(("a", "b"), [("x", 1), ("yy", 22)], titre="essai")
    assert "essai" in rendu and "yy" in rendu


def test_toutes_les_briques_du_catalogue_ont_une_designation() -> None:
    from briq.bom.nomenclature import DESIGNATIONS
    from briq.model.systeme import Ref

    for ref in Ref:
        assert ref.value in DESIGNATIONS
        assert longueur_carrelet(composition(ref)) > 0
