"""Poteaux raidisseurs : ou l'application en pose, et pourquoi la ces endroits."""

from __future__ import annotations

from itertools import pairwise

from hypothesis import given, settings
from hypothesis import strategies as st

from obqo.engine.raidissement import (
    MODULES_MAXI_PAN,
    coupures,
    positions_dans_un_pan,
    positions_manquantes,
)
from obqo.rules.catalogue import RAIDISSEUR_PAR_RANG, longueur_carrelet
from obqo.units import (
    ENTRAXE_MAXI_RAIDISSEUR,
    GRILLE,
    LARGEUR_POTEAU,
    MODULE_POTEAU,
    REMPLISSAGE_POTEAU,
)


def pans(longueur: int, poteaux: list[int]) -> list[int]:
    """Longueurs de maconnerie entre deux raidisseurs successifs."""
    bornes = [0]
    for u in poteaux:
        bornes += [u, u + MODULE_POTEAU]
    bornes.append(longueur)
    return [b - a for a, b in zip(bornes[::2], bornes[1::2], strict=True)]


def test_un_pan_qui_tient_dans_l_entraxe_ne_recoit_rien() -> None:
    assert positions_dans_un_pan(0, ENTRAXE_MAXI_RAIDISSEUR) == []
    assert positions_dans_un_pan(0, ENTRAXE_MAXI_RAIDISSEUR + GRILLE) != []


def test_le_poteau_se_pose_au_milieu_et_laisse_deux_pans_egaux() -> None:
    """Un raidisseur travaille mieux au milieu du pan qu'a son extremite."""
    poteaux = positions_dans_un_pan(0, 13920)
    assert poteaux == [4560, 9360]
    assert pans(13920, poteaux) == [4560, 4560, 4320]


def test_une_baie_et_un_ancrage_tiennent_lieu_de_raidisseur() -> None:
    """Le paragraphe 1.7 compte les jambages de baie comme raidisseurs."""
    nu = positions_manquantes(12000, [], [])
    assert nu, "12 m de mur nu demandent un poteau"
    avec_baie = positions_manquantes(12000, [5760, 6960], [])
    assert avec_baie == [], "la baie coupe le mur en deux pans de moins de 6 m"
    avec_refend = positions_manquantes(12000, [], [6000])
    assert avec_refend == []


def test_les_coupures_comptent_les_deux_extremites() -> None:
    assert coupures(9600, [2400, 3600], [7200]) == [0, 2400, 3600, 7200, 9600]
    assert coupures(9600, [], []) == [0, 9600]


@settings(max_examples=200, deadline=None)
@given(st.integers(min_value=1, max_value=200))
def test_les_poteaux_ramenent_toujours_chaque_pan_sous_l_entraxe(modules: int) -> None:
    """L'invariant qui compte, sur des murs jusqu'a 48 m."""
    longueur = modules * GRILLE
    poteaux = positions_dans_un_pan(0, longueur)
    morceaux = pans(longueur, poteaux)
    assert sum(morceaux) + len(poteaux) * MODULE_POTEAU == longueur, "couverture exacte"
    assert all(m % GRILLE == 0 for m in morceaux), "chaque pan reste un nombre entier de briques"
    if modules > MODULES_MAXI_PAN:
        assert max(morceaux) <= ENTRAXE_MAXI_RAIDISSEUR
    else:
        assert poteaux == []


@settings(max_examples=200, deadline=None)
@given(st.integers(min_value=1, max_value=200))
def test_l_application_pose_le_minimum_de_poteaux(modules: int) -> None:
    """Un poteau de moins doit laisser un pan hors entraxe : sinon il est de trop."""
    longueur = modules * GRILLE
    poteaux = positions_dans_un_pan(0, longueur)
    if not poteaux:
        return
    maconnerie = longueur - (len(poteaux) - 1) * MODULE_POTEAU
    assert maconnerie / len(poteaux) > ENTRAXE_MAXI_RAIDISSEUR, (
        f"{len(poteaux) - 1} poteaux auraient suffi sur {longueur} mm"
    )


def test_les_poteaux_ne_se_chevauchent_jamais() -> None:
    poteaux = positions_dans_un_pan(0, 48000)
    for a, b in pairwise(poteaux):
        assert b >= a + MODULE_POTEAU


def test_le_module_du_poteau_tombe_juste() -> None:
    """80 de P10 plus 160 de remplissage : le mur reste sur la grille de 240."""
    assert LARGEUR_POTEAU + REMPLISSAGE_POTEAU == MODULE_POTEAU == GRILLE


def test_le_remplissage_du_module_a_le_bon_volume() -> None:
    """Controle croise : la table de composition contre la geometrie.

    Le remplissage occupe 160 x 240 x 240 par rang. La table le batit en P6,
    du carrelet 80x80 de 160 de long. Le volume doit tomber exactement, sinon
    la nomenclature commande du bois qui n'entre pas dans le mur.
    """
    vide = REMPLISSAGE_POTEAU * GRILLE * GRILLE
    p6 = RAIDISSEUR_PAR_RANG["P6"]
    assert p6 * 80 * 80 * 160 == vide
    assert longueur_carrelet(RAIDISSEUR_PAR_RANG) == p6 * 160
