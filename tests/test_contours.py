"""Contours non rectangulaires : angles rentrants, et invariants sur cinq familles.

Un angle **rentrant** (270 degres a l'interieur) n'est pas le symetrique d'un
angle convexe : les deux bandes de mur ne s'y recouvrent pas, elles ne se
touchent que par un point. La colonne de 240 que le mur filant doit occuper se
trouve **au-dela** du sommet, et non en deca. Tant que ce n'etait pas traite,
une maison en L avait un trou de 240 x 240 a chaque rang, dans le mur.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from briq.drawings.volume import tenons_sans_reception
from briq.engine.calepinage import calepiner, vide_du_rang
from briq.engine.geometrie import squelette
from briq.model.plan import Plan
from briq.model.systeme import Calepinage
from briq.units import EPAISSEUR_MUR, GRILLE


def plan(nom: str, segments: list[tuple[str, int]], **extra: Any) -> Plan:
    return Plan.model_validate(
        {
            "nom": nom,
            "hauteur_sous_chainage": extra.pop("hauteur", 1440),
            "contour": {
                "trace": {"segments": [{"direction": d, "longueur": n} for d, n in segments]}
            },
            **extra,
        }
    )


def en_l(a: int = 5760, b: int = 4800, c: int = 2880, d: int = 1920) -> Plan:
    """Rectangle a x b ampute d'une encoche c x d dans l'angle nord-est."""
    return plan(
        "L",
        [("est", a), ("nord", b - d), ("ouest", c), ("nord", d), ("ouest", a - c), ("sud", b)],
    )


def en_u(bras: int = 1920, entre: int = 1920, a: int = 4800, encoche: int = 2880) -> Plan:
    return plan(
        "U",
        [
            ("est", 2 * bras + entre),
            ("nord", a),
            ("ouest", bras),
            ("sud", encoche),
            ("ouest", entre),
            ("nord", encoche),
            ("ouest", bras),
            ("sud", a),
        ],
    )


FAMILLES = {
    "rectangle": plan("R", [("est", 5760), ("nord", 4800), ("ouest", 5760), ("sud", 4800)]),
    "L": en_l(),
    "U": en_u(),
    "T": plan(
        "T",
        [
            ("est", 1920),
            ("sud", 1920),
            ("est", 1920),
            ("nord", 1920),
            ("est", 1920),
            ("nord", 2880),
            ("ouest", 5760),
            ("sud", 2880),
        ],
    ),
    "escalier": plan(
        "escalier",
        [
            ("est", 1920),
            ("nord", 1920),
            ("est", 1920),
            ("nord", 1920),
            ("est", 1920),
            ("nord", 1920),
            ("ouest", 5760),
            ("sud", 5760),
        ],
    ),
}


def verifier(calepinage: Calepinage, plan_source: Plan) -> None:
    """Invariants que tout calepinage doit respecter, quelle que soit la forme."""
    par_mur: dict[str, list[Any]] = {}
    for o in plan_source.ouvertures:
        par_mur.setdefault(o.mur, []).append(o)

    for mur in calepinage.murs:
        for rang in mur.rangs:
            vides = [v for o in par_mur.get(mur.id, []) if (v := vide_du_rang(o, rang.indice))]
            retire = sum(
                min(b, rang.fin) - max(a, rang.debut)
                for a, b in vides
                if b > rang.debut and a < rang.fin
            )
            assert sum(b.longueur for b in rang.briques) == (rang.fin - rang.debut) - retire, (
                f"couverture incomplete en {mur.id}/R{rang.indice}"
            )
            for a, b in pairwise(rang.briques):
                assert a.fin <= b.u, f"recouvrement en {mur.id}/R{rang.indice}"
        for bas, haut in pairwise(mur.rangs):
            assert set(bas.joints).isdisjoint(haut.joints), (
                f"joints alignes entre R{bas.indice} et R{haut.indice} de {mur.id}"
            )


@pytest.mark.parametrize("nom", sorted(FAMILLES))
def test_les_cinq_familles_de_contour_tiennent_les_invariants(nom: str) -> None:
    source = FAMILLES[nom]
    calepinage, rapport = calepiner(source)
    assert calepinage is not None, [str(e) for e in rapport.erreurs]
    verifier(calepinage, source)


@pytest.mark.parametrize("nom", sorted(FAMILLES))
def test_aucun_tenon_orphelin_sur_un_contour_sans_baie(nom: str) -> None:
    """Sans baie, tout tenon doit trouver sa reception : c'est la preuve que le
    harpage tombe juste, y compris a un angle rentrant."""
    calepinage, _ = calepiner(FAMILLES[nom])
    assert calepinage is not None
    assert tenons_sans_reception(calepinage) == []


def test_les_angles_rentrants_sont_reconnus() -> None:
    sq = squelette(en_l())
    rentrants = [a for a in sq.angles if not a.convexe]
    assert len(rentrants) == 1, "un L a exactement un angle rentrant"
    assert len([a for a in sq.angles if a.convexe]) == 5
    assert len([a for a in squelette(en_u()).angles if not a.convexe]) == 2


def test_a_un_angle_rentrant_le_mur_filant_deborde_du_sommet() -> None:
    """C'est la difference avec un angle convexe, et tout le bug d'origine.

    A 90 degres la colonne d'angle tombe en deca du sommet : le mur en butee
    recule de 240. A 270 elle tombe au-dela : c'est le mur filant qui avance.
    """
    source = en_l()
    sq = squelette(source)
    rentrant = next(a for a in sq.angles if not a.convexe)
    entrant = sq.mur(rentrant.entrant)
    sortant = sq.mur(rentrant.sortant)

    for rang in (0, 1):
        fin = sq.course(entrant, rang)[1]
        debut = sq.course(sortant, rang)[0]
        if rentrant.filant(rang) == entrant.id:
            assert fin == entrant.longueur + EPAISSEUR_MUR
            assert debut == 0
        else:
            assert fin == entrant.longueur
            assert debut == -EPAISSEUR_MUR


def test_la_colonne_d_un_angle_rentrant_est_occupee_a_chaque_rang() -> None:
    """Sans cela, une maison en L a un trou de 240 x 240 dans le mur."""
    source = en_l()
    sq = squelette(source)
    rentrant = next(a for a in sq.angles if not a.convexe)
    calepinage, _ = calepiner(source)
    assert calepinage is not None

    for rang in range(source.rangs):
        occupants = 0
        for identifiant in (rentrant.entrant, rentrant.sortant):
            mur = sq.mur(identifiant)
            debut, fin = sq.course(mur, rang)
            depasse = fin > mur.longueur or debut < 0
            occupants += int(depasse)
        assert occupants == 1, f"rang {rang} : la colonne d'angle doit avoir un occupant"


def test_l_angle_rentrant_est_signale_comme_hypothese() -> None:
    _, rapport = calepiner(en_l())
    codes = {c.code for c in rapport.constats}
    assert "ANGLE-RENTRANT" in codes, "le brief ne decrit le harpage qu'a 90 degres"
    _, sans = calepiner(FAMILLES["rectangle"])
    assert "ANGLE-RENTRANT" not in {c.code for c in sans.constats}


def test_un_mur_trop_court_pour_le_harpage_est_refuse() -> None:
    """Un mur de 240 en butee aux deux bouts n'aurait plus de course du tout."""
    trop_court = plan(
        "pointe",
        [("est", 4800), ("nord", 240), ("ouest", 4800), ("sud", 240)],
    )
    calepinage, rapport = calepiner(trop_court)
    assert calepinage is None
    assert "MUR-TROP-COURT" in {c.code for c in rapport.erreurs}


def test_un_contour_oblique_est_refuse() -> None:
    source = Plan.model_validate(
        {
            "hauteur_sous_chainage": 1440,
            "contour": {"points": [[0, 0], [4800, 0], [4800, 4800], [1200, 3600]]},
        }
    )
    _, rapport = calepiner(source)
    assert "ANGLE-NON-DROIT" in {c.code for c in rapport.erreurs}


cotes = st.integers(min_value=2, max_value=12).map(lambda n: n * GRILLE)


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(cotes, cotes, cotes, cotes)
def test_invariants_sur_des_L_quelconques(a: int, b: int, c: int, d: int) -> None:
    """Le L couvre tous les cas : encoche large, etroite, profonde, minuscule."""
    if c >= a or d >= b:
        return
    source = en_l(a + GRILLE, b + GRILLE, c, d)
    calepinage, rapport = calepiner(source)
    if calepinage is None:  # murs trop courts ou trop longs : le refus est explicite
        assert rapport.erreurs
        return
    verifier(calepinage, source)
    assert tenons_sans_reception(calepinage) == []


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(cotes, cotes, cotes)
def test_invariants_sur_des_U_quelconques(bras: int, entre: int, encoche: int) -> None:
    source = en_u(bras, entre, encoche + GRILLE, encoche)
    calepinage, rapport = calepiner(source)
    if calepinage is None:
        assert rapport.erreurs
        return
    verifier(calepinage, source)
    assert tenons_sans_reception(calepinage) == []
