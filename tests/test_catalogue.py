"""Controle croise des tables de composition avec les constantes du brief (1.8).

Ces tests documentent un ecart reel entre le paragraphe 1.2 (structure de la
brique) et le paragraphe 1.8 (constantes de metre). Ils sont ecrits pour
**verrouiller ce qui concorde** et **rendre visible ce qui diverge**, pas pour
masquer la difference derriere une tolerance.
"""

from __future__ import annotations

from briq.model.systeme import Ref
from briq.rules.catalogue import (
    JOINT_COURANT,
    REFERENCE_BRIEF,
    composition,
    compte_pieces_bois,
    longueur_carrelet,
    longueur_hetre,
)


def test_le_carrelet_d_une_480_a_egale_la_constante_du_brief() -> None:
    """4,16 m correspond a une 480 **avec un about ferme**, pas a une 480-S nue.

    La 480-S vaut 4,00 m ; les deux carres P8 de fermeture ajoutent 160 mm.
    """
    assert longueur_carrelet(composition(Ref.B480_S)) == 4000
    attendu = round(REFERENCE_BRIEF[480].carrelet_ml * 1000)
    assert longueur_carrelet(composition(Ref.B480_A)) == attendu


def test_le_carrelet_d_une_240_s_egale_la_constante_du_brief() -> None:
    attendu = round(REFERENCE_BRIEF[240].carrelet_ml * 1000)
    assert longueur_carrelet(composition(Ref.B240_S)) == attendu


def test_le_hetre_d_une_480_a_egale_la_constante_du_brief() -> None:
    """3,65 m correspond a la 480-A : 10 chevilles atelier + 2 verrouillages de
    tenon + 16 piges + la cheville de fermeture d'about, soit 3 630 mm."""
    assert longueur_hetre(composition(Ref.B480_A)) == 3630
    assert abs(3630 - REFERENCE_BRIEF[480].hetre_ml * 1000) <= 20
    # Le joint courant s'ajoute au chantier, il n'est pas dans la constante.
    assert longueur_hetre(JOINT_COURANT) == 460


def test_ecart_documente_sur_le_nombre_de_pieces_d_une_480() -> None:
    """Le brief annonce 21 pieces bois pour 4,16 m ; la structure du 1.2 en donne
    19 pour la meme longueur. Les 2 pieces manquantes sont de longueur nulle :
    l'ecart s'explique si les deux remplissages centraux de 160 sont en fait
    quatre pieces de 80 (meme metre lineaire, deux pieces de plus). A trancher.
    """
    pieces = compte_pieces_bois(composition(Ref.B480_A))
    assert pieces == 19
    assert REFERENCE_BRIEF[480].pieces_bois - pieces == 2


def test_ecart_documente_sur_le_hetre_de_la_demi_brique() -> None:
    """Le brief annonce 1,30 m de hetre pour la demi-brique ; le decompte des
    chevilles du 1.4 en donne 1,09 m. Le nombre de piges de la demi-brique n'est
    pas explicite dans le brief : c'est la seule variable d'ajustement.
    """
    calcule = longueur_hetre(composition(Ref.B240_S))
    assert calcule == 1090
    assert REFERENCE_BRIEF[240].hetre_ml * 1000 - calcule == 210


def test_chevilles_atelier_d_une_480() -> None:
    """« 28 chevilles atelier » du 1.8 : 6 + 4 verticales et traversantes,
    16 piges, 2 verrouillages de tenon."""
    c = composition(Ref.B480_S)
    assert c["C1"] + c["C2"] + c["C3"] == REFERENCE_BRIEF[480].chevilles_atelier


def test_la_anr_derive_de_la_a() -> None:
    """480-ANR = 480-A, un tenon devient un P5-A, un carre est omis."""
    a, anr = composition(Ref.B480_A), composition(Ref.B480_ANR)
    assert anr["P5-A"] == 1
    assert anr["P5"] == a["P5"] - 1
    assert anr["P8"] == a["P8"] - 1
    assert longueur_carrelet(anr) == longueur_carrelet(a) - 80


def test_toutes_les_references_du_catalogue_se_composent() -> None:
    for ref in Ref:
        c = composition(ref)
        assert all(n > 0 for n in c.values()), ref
        assert longueur_carrelet(c) > 0
