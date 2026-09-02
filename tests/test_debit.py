"""Le plan de debit doit couvrir la demande, tenir dans la barre, et etre optimal."""

from __future__ import annotations

from collections import Counter

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from obqo.bom.debit import (
    CpSat,
    GloutonDecroissant,
    PlanDeDebit,
    Stock,
    patrons_maximaux,
)

CARRELET = Stock("carrelet 80x80", 4000, trait_de_scie=4, chute_minimale_reutilisable=240)
SOLVEURS = [GloutonDecroissant(), CpSat(secondes_par_phase=10.0)]


def verifier(plan: PlanDeDebit, demandes: Counter[int]) -> None:
    """Invariants que tout plan de debit doit respecter, quel que soit le solveur."""
    produit = plan.produit()
    for longueur, besoin in demandes.items():
        assert produit[longueur] >= besoin, f"{longueur} mm : {produit[longueur]} < {besoin}"
    for barre in plan.barres:
        assert barre.repetitions > 0
        assert barre.patron.chute(plan.stock) >= 0, "patron plus long que la barre"
    # Le bois achete se repartit en exactement trois categories.
    assert plan.longueur_utile + plan.surproduction + plan.chute == plan.longueur_achetee
    assert plan.surproduction >= 0
    assert plan.longueur_utile == sum(longueur * n for longueur, n in demandes.items() if n > 0)


@pytest.mark.parametrize("solveur", SOLVEURS, ids=lambda s: s.nom)
def test_le_plan_couvre_la_demande_et_tient_dans_la_barre(solveur) -> None:
    demandes = Counter({240: 500, 480: 40, 160: 210, 80: 12})
    plan = solveur.resoudre(demandes, CARRELET)
    verifier(plan, demandes)


def test_le_trait_de_scie_est_bien_compte() -> None:
    """Dix pieces de 240 ne tiennent pas dans 2 400 mm : neuf traits font 36 mm."""
    barre = Stock("essai", 2400, trait_de_scie=4)
    assert barre.tient((240,), (9,))
    assert not barre.tient((240,), (10,))
    sans_trait = Stock("essai", 2400, trait_de_scie=0)
    assert sans_trait.tient((240,), (10,))


def test_l_optimum_exact_bat_le_glouton() -> None:
    demandes = Counter({240: 12_700, 480: 1_000, 160: 6_100, 80: 300})
    glouton = GloutonDecroissant().resoudre(demandes, CARRELET)
    exact = CpSat(secondes_par_phase=20.0).resoudre(demandes, CARRELET)
    verifier(glouton, demandes)
    verifier(exact, demandes)
    assert exact.optimal
    assert exact.nombre_de_barres < glouton.nombre_de_barres
    # L'objectif lexicographique donne aussi un plan d'atelier plus simple.
    assert exact.patrons_distincts <= glouton.patrons_distincts


@pytest.mark.lent
def test_la_chute_suit_la_loi_des_80_sur_L() -> None:
    """Le trait de scie fait perdre un module de 80 par barre : chute ~ 80/L.

    C'est la raison pour laquelle une barre de 2,40 m est le pire choix, alors
    qu'elle serait parfaite sans trait de scie. Voir docs/etudes/.
    """
    demandes = Counter({240: 2000, 160: 900, 480: 150, 80: 40})
    mesures = {}
    for longueur in (2400, 4000, 4800):
        stock = Stock("essai", longueur, trait_de_scie=4)
        plan = CpSat(secondes_par_phase=10.0).resoudre(demandes, stock)
        verifier(plan, demandes)
        mesures[longueur] = plan.taux_de_chute
    assert mesures[2400] > mesures[4000] > mesures[4800]
    for longueur, taux in mesures.items():
        assert abs(taux - 80 / longueur) < 0.005, (longueur, taux)


def test_sans_trait_de_scie_la_barre_de_2400_ne_perd_rien() -> None:
    demandes = Counter({240: 2000, 480: 150})
    stock = Stock("essai", 2400, trait_de_scie=0)
    plan = CpSat(secondes_par_phase=10.0).resoudre(demandes, stock)
    assert plan.taux_de_chute == 0.0


def test_enumeration_des_patrons_du_carrelet() -> None:
    patrons = patrons_maximaux((480, 240, 160, 80), CARRELET)
    assert patrons is not None
    assert len(patrons) == 761
    assert all(p.chute(CARRELET) >= 0 for p in patrons)
    # Maximal : plus aucune piece, meme la plus courte, ne rentre.
    assert all(p.chute(CARRELET) < 80 + CARRELET.trait_de_scie for p in patrons)


def test_une_piece_trop_longue_est_signalee() -> None:
    with pytest.raises(ValueError, match="ne tient pas dans une barre"):
        GloutonDecroissant().resoudre(Counter({5000: 1}), CARRELET)


def test_demande_vide() -> None:
    for solveur in SOLVEURS:
        plan = solveur.resoudre(Counter(), CARRELET)
        assert plan.nombre_de_barres == 0
        assert plan.taux_de_chute == 0.0


demandes_aleatoires = st.dictionaries(
    st.sampled_from([80, 160, 240, 480]),
    st.integers(min_value=1, max_value=400),
    min_size=1,
)


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(demandes_aleatoires)
def test_le_glouton_est_toujours_valide(demandes: dict[int, int]) -> None:
    compte = Counter(demandes)
    verifier(GloutonDecroissant().resoudre(compte, CARRELET), compte)


def test_le_solveur_exact_est_deterministe() -> None:
    """CP-SAT cherche en parallele par defaut, donc de facon non reproductible.

    Le solveur est bride a un fil et une graine fixe : sans cela deux executions
    sur le meme plan donneraient des plans de debit differents a objectif egal,
    et aucun test de non-regression ne serait possible sur les livrables.
    """
    # Une demande modeste suffit a prouver le determinisme : ce qui varie d'une
    # execution a l'autre est le chemin de recherche, pas la taille du probleme.
    demandes = Counter({240: 400, 480: 35, 160: 190, 80: 9})
    rendus = [
        [
            (str(b.patron), b.repetitions)
            for b in CpSat(secondes_par_phase=10.0).resoudre(demandes, CARRELET).barres
        ]
        for _ in range(2)
    ]
    assert rendus[0] == rendus[1]
