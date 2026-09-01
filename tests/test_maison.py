"""Test d'integration : la maison d'exemple doit calepiner sans erreur."""

from __future__ import annotations

import json
from itertools import pairwise

from briq.cli import serialiser
from briq.engine.calepinage import calepiner
from briq.model.plan import Plan
from briq.units import HAUTEUR_RANG


def test_la_maison_d_exemple_calepine_sans_erreur(maison: Plan) -> None:
    calepinage, rapport = calepiner(maison)
    assert calepinage is not None, [str(e) for e in rapport.erreurs]
    assert rapport.erreurs == []


def test_ordres_de_grandeur_attendus(maison: Plan) -> None:
    """Critere d'acceptation 2.5 : ~1 000 briques, ~110 m2, ~8,7 briques/m2."""
    calepinage, _ = calepiner(maison)
    assert calepinage is not None
    briques = calepinage.briques
    surface = sum(b.longueur * HAUTEUR_RANG for b in briques) / 1_000_000
    assert 900 <= len(briques) <= 1300, len(briques)
    assert 100 <= surface <= 140, surface
    # Une 480 couvre 0,1152 m2, une 240 moitie moins : la densite reste proche
    # de 8,7 tant que les demi-briques restent minoritaires.
    assert 8.5 <= len(briques) / surface <= 9.5


def test_toutes_les_baies_sont_equipees(maison: Plan) -> None:
    calepinage, _ = calepiner(maison)
    assert calepinage is not None
    elements = [e for m in calepinage.murs for e in m.elements]
    madriers = {e.ouverture for e in elements if e.piece in ("P9", "P9-LC")}
    jambages = {e.ouverture for e in elements if e.piece == "P10"}
    attendues = {o.id for o in maison.ouvertures}
    assert madriers == attendues
    assert jambages == attendues


def test_le_chainage_couvre_tous_les_murs(maison: Plan) -> None:
    calepinage, _ = calepiner(maison)
    assert calepinage is not None
    lisses = {e.mur: e for m in calepinage.murs for e in m.elements if e.piece == "LISSE"}
    assert set(lisses) == {m.id for m in calepinage.murs}
    for mur in calepinage.murs:
        assert lisses[mur.id].longueur == mur.longueur_hors_tout


def test_invariants_globaux_sur_la_maison(maison: Plan) -> None:
    calepinage, _ = calepiner(maison)
    assert calepinage is not None
    for mur in calepinage.murs:
        for rang in mur.rangs:
            for a, b in pairwise(rang.briques):
                assert a.fin <= b.u, f"recouvrement en {mur.id}/R{rang.indice}"
        for bas, haut in pairwise(mur.rangs):
            assert set(bas.joints).isdisjoint(haut.joints), (
                f"joints alignes entre R{bas.indice} et R{haut.indice} de {mur.id}"
            )


def test_la_sortie_est_deterministe(maison: Plan) -> None:
    """Sans cela, aucun test de non-regression n'est possible sur les dessins."""
    premier, second = (calepiner(maison)[0] for _ in range(2))
    assert premier is not None and second is not None
    rendu = [
        json.dumps(serialiser(c), sort_keys=False, ensure_ascii=False) for c in (premier, second)
    ]
    assert rendu[0] == rendu[1]


def test_quincaillerie_d_angle_de_la_maison(maison: Plan) -> None:
    calepinage, _ = calepiner(maison)
    assert calepinage is not None
    coins, rangs = 4, maison.rangs
    dangle = [
        q
        for mur in calepinage.murs
        for rang in mur.rangs
        for q in rang.quincaillerie
        if q.role.startswith("angle")
    ]
    assert len(dangle) == coins * rangs
    assert calepinage.compte_quincaillerie()["P8"] == coins * rangs
