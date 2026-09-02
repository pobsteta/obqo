"""Comptages verifiables a la main et invariants du calepinage complet."""

from __future__ import annotations

from itertools import pairwise

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from obqo.engine.calepinage import calepiner
from obqo.model.plan import Plan
from obqo.model.systeme import Ref
from obqo.rules.catalogue import ANGLE_PAR_RANG
from obqo.units import EPAISSEUR_MUR, GRILLE, LONGUEUR_BRIQUE

from .conftest import plan_rectangle


def calepine(plan: Plan):
    calepinage, rapport = calepiner(plan)
    assert calepinage is not None, [str(e) for e in rapport.erreurs]
    return calepinage, rapport


# --- mur droit, comptage a la main -------------------------------------------


def test_comptage_a_la_main_d_un_carre_de_4800() -> None:
    """Carre de 4 800 (20 modules), 2 rangs.

    A chaque rang un mur file aux deux angles (20 modules, 10 briques), un mur
    est en butee aux deux angles (18 modules, 9 briques) et les deux autres
    filent d'un cote seulement (19 modules, 9 briques + 1 demi). Soit 39 briques
    par rang, dont 2 demi-briques.
    """
    calepinage, _ = calepine(plan_rectangle(4800, 4800, hauteur=2 * GRILLE))
    compte = calepinage.compte_briques()
    assert sum(compte.values()) == 2 * 39
    assert sum(n for ref, n in compte.items() if ref.longueur == 240) == 2 * 2
    for mur in calepinage.murs:
        for rang in mur.rangs:
            longueurs = [b.longueur for b in rang.briques]
            assert longueurs[0] == LONGUEUR_BRIQUE, "l'angle exige une brique de 480"
            assert longueurs.count(240) <= 1


def test_un_rang_remplit_exactement_sa_course() -> None:
    calepinage, _ = calepine(plan_rectangle(5760, 4800))
    for mur in calepinage.murs:
        for rang in mur.rangs:
            assert sum(b.longueur for b in rang.briques) == rang.fin - rang.debut
            assert rang.briques[0].u == rang.debut
            assert rang.briques[-1].fin == rang.fin


def test_les_briques_ne_se_recouvrent_jamais() -> None:
    calepinage, _ = calepine(plan_rectangle(5760, 4800))
    for mur in calepinage.murs:
        for rang in mur.rangs:
            for a, b in pairwise(rang.briques):
                assert a.fin <= b.u


# --- angles ------------------------------------------------------------------


def test_quincaillerie_d_angle_par_rang() -> None:
    """Critere d'acceptation 2.5 : 1 P5-A, 1 raccord, 1 carre, 2 chevilles."""
    rangs = 4
    calepinage, _ = calepine(plan_rectangle(4800, 4800, hauteur=rangs * GRILLE))
    coins = 4
    quincaillerie = calepinage.compte_quincaillerie()
    assert quincaillerie["P8"] == coins * rangs * ANGLE_PAR_RANG["P8"]
    # Exactement une brique filante par angle et par rang. Elle est une 480-ANR
    # sauf quand la course impose la demi-brique a cet about (cas signale en
    # hypothese : le catalogue du brief ne definit pas de 240-ANR).
    compte = calepinage.compte_briques()
    assert compte[Ref.B480_ANR] + compte[Ref.B240_ANR] == coins * rangs
    assert len([b for b in calepinage.briques if b.angle is not None]) == coins * rangs

    dangle = [
        q
        for mur in calepinage.murs
        for rang in mur.rangs
        for q in rang.quincaillerie
        if q.role.startswith("angle")
    ]
    assert len(dangle) == coins * rangs
    for q in dangle:
        assert dict(q.pieces) == {"P6": 1, "P8": 1, "C1": 2}


def test_le_harpage_alterne_le_mur_filant() -> None:
    calepinage, _ = calepine(plan_rectangle(5760, 4800))
    long_, court = calepinage.murs[0], calepinage.murs[1]
    # Le plus long file au rang 0 : il occupe la colonne d'angle et part de 0.
    assert (long_.rangs[0].debut, long_.rangs[1].debut) == (0, EPAISSEUR_MUR)
    assert (court.rangs[0].debut, court.rangs[1].debut) == (EPAISSEUR_MUR, 0)
    # La brique d'angle est une 480 a chaque rang, filante ou en butee.
    for mur in (long_, court):
        for rang in mur.rangs:
            assert rang.briques[0].longueur == LONGUEUR_BRIQUE


def test_la_filante_d_angle_est_une_anr_et_la_butee_une_a() -> None:
    calepinage, _ = calepine(plan_rectangle(5760, 4800))
    long_, court = calepinage.murs[0], calepinage.murs[1]
    assert long_.rangs[0].briques[0].ref is Ref.B480_ANR
    assert long_.rangs[0].briques[0].angle is not None
    assert court.rangs[0].briques[0].ref is Ref.B480_A
    assert court.rangs[0].briques[0].about_debut_ferme


# --- decalage des joints : l'invariant central -------------------------------


def test_les_joints_se_decalent_de_240_entre_rangs() -> None:
    calepinage, _ = calepine(plan_rectangle(5760, 4800))
    for mur in calepinage.murs:
        for bas, haut in pairwise(mur.rangs):
            assert set(bas.joints).isdisjoint(haut.joints)
            for j in bas.joints:
                assert (j - GRILLE) in haut.joints or (j + GRILLE) in haut.joints


rectangles = st.integers(min_value=8, max_value=24).map(lambda n: n * GRILLE)


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(rectangles, rectangles, st.integers(2, 11))
def test_invariants_sur_rectangles_quelconques(largeur: int, profondeur: int, rangs: int) -> None:
    plan = plan_rectangle(largeur, profondeur, hauteur=rangs * GRILLE)
    calepinage, rapport = calepiner(plan)
    if calepinage is None:  # murs trop longs sans raidisseur : refus attendu
        assert rapport.erreurs
        return
    for mur in calepinage.murs:
        for rang in mur.rangs:
            assert sum(b.longueur for b in rang.briques) == rang.fin - rang.debut
            for a, b in pairwise(rang.briques):
                assert a.fin == b.u
        for bas, haut in pairwise(mur.rangs):
            assert set(bas.joints).isdisjoint(haut.joints)


# --- baies -------------------------------------------------------------------


def baie(**champs: object) -> dict[str, object]:
    return {"id": "B1", "mur": "M1", "type": "fenetre", **champs}


def test_une_baie_interrompt_les_rangs_qu_elle_traverse() -> None:
    plan = plan_rectangle(
        5760,
        4800,
        ouvertures=[baie(position=1920, largeur=1440, allege=960, hauteur=1200)],
    )
    calepinage, _ = calepine(plan)
    mur = calepinage.murs[0]
    assert [b.u for b in mur.rangs[0].briques if b.u >= 1920]  # allege maconnee
    traverse = mur.rangs[4]  # z = 960, premier rang de la baie
    assert all(b.fin <= 1920 or b.u >= 3360 for b in traverse.briques)
    # Les briques de tableau ferment leur about cote baie.
    gauche = max((b for b in traverse.briques if b.fin <= 1920), key=lambda b: b.fin)
    assert gauche.about_fin_ferme
    assert gauche.ref in (Ref.B480_A, Ref.B480_AA, Ref.B240_A, Ref.B240_AA)


def test_le_linteau_degage_ses_appuis_et_sort_ses_pieces() -> None:
    plan = plan_rectangle(
        5760,
        4800,
        ouvertures=[baie(position=1920, largeur=1440, allege=960, hauteur=1200)],
    )
    calepinage, _ = calepine(plan)
    mur = calepinage.murs[0]
    rang_linteau = mur.rangs[9]  # (960 + 1200) / 240
    assert all(b.fin <= 1680 or b.u >= 3600 for b in rang_linteau.briques)
    madriers = [e for e in mur.elements if e.piece == "P9"]
    assert len(madriers) == 1 and madriers[0].quantite == 2
    assert madriers[0].longueur == 1440 + 2 * 240
    jambages = [e for e in mur.elements if e.piece == "P10"]
    assert sum(e.quantite for e in jambages) == 2
    assert all(e.longueur == 1200 for e in jambages)


def test_jambages_doubles_au_dela_de_1800() -> None:
    plan = plan_rectangle(5760, 4800, ouvertures=[baie(position=1440, largeur=2400, hauteur=2160)])
    calepinage, _ = calepine(plan)
    jambages = [e for e in calepinage.murs[0].elements if e.piece == "P10"]
    assert sum(e.quantite for e in jambages) == 4
