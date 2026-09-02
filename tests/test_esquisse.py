"""Du dessin au plan : calage sur la grille, contour, refends."""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from briq.engine.calepinage import calepiner
from briq.engine.esquisse import PAS_RECOMMANDE, caler, vers_plan
from briq.model.esquisse import Baie, Esquisse, Piece
from briq.model.plan import Ouverture
from briq.units import GRILLE


def esquisse(*pieces: dict[str, Any], **extra: Any) -> Esquisse:
    return Esquisse(pieces=[Piece(**p) for p in pieces], **extra)


def codes(rapport) -> set[str]:
    return {c.code for c in rapport.constats}


# --- calage -------------------------------------------------------------------


def test_le_calage_ramene_tout_sur_le_pas() -> None:
    croquis = esquisse(
        {"nom": "a", "x": 0, "y": 0, "largeur": 5100, "hauteur": 4300},
        {"nom": "b", "x": 5100, "y": 0, "largeur": 3700, "hauteur": 4300},
    )
    cale, ajustements = caler(croquis)
    for piece in cale.pieces:
        assert piece.x % PAS_RECOMMANDE == 0
        assert piece.largeur % PAS_RECOMMANDE == 0
        assert piece.hauteur % PAS_RECOMMANDE == 0
    assert len(ajustements) == 2
    assert "5100 x 4300 -> 5280 x 4320" in str(ajustements[0])


def test_le_calage_preserve_l_adjacence() -> None:
    """C'est tout l'interet de caler les lignes plutot que les pieces.

    Deux pieces qui se touchaient doivent se toucher encore apres calage, sinon
    le batiment se coupe en deux sans que personne l'ait demande.
    """
    croquis = esquisse(
        {"nom": "a", "x": 0, "y": 0, "largeur": 5100, "hauteur": 4300},
        {"nom": "b", "x": 5100, "y": 0, "largeur": 3700, "hauteur": 4300},
        {"nom": "c", "x": 0, "y": 4300, "largeur": 8800, "hauteur": 3100},
    )
    cale, _ = caler(croquis)
    a, b, c = cale.pieces
    assert a.droite == b.x, "les voisines de gauche et de droite se sont ecartees"
    assert a.haut == c.y, "la piece du dessus s'est decollee"
    assert c.largeur == a.largeur + b.largeur


def test_le_calage_ne_rend_jamais_une_piece_plate() -> None:
    croquis = esquisse(
        {"nom": "a", "x": 0, "y": 0, "largeur": 100, "hauteur": 4800},
        {"nom": "b", "x": 100, "y": 0, "largeur": 100, "hauteur": 4800},
    )
    cale, _ = caler(croquis)
    assert all(p.largeur >= PAS_RECOMMANDE for p in cale.pieces)
    assert cale.pieces[0].droite == cale.pieces[1].x


def test_deux_pieces_qui_se_chevauchent_sont_refusees_des_le_modele() -> None:
    with pytest.raises(ValueError, match="chevauchent"):
        esquisse(
            {"nom": "a", "x": 0, "y": 0, "largeur": 4800, "hauteur": 4800},
            {"nom": "b", "x": 2400, "y": 2400, "largeur": 4800, "hauteur": 4800},
        )


# --- contour et refends -------------------------------------------------------


def test_deux_pieces_donnent_un_contour_et_un_refend() -> None:
    plan, rapport = vers_plan(
        esquisse(
            {"nom": "séjour", "x": 0, "y": 0, "largeur": 4800, "hauteur": 3840},
            {"nom": "cuisine", "x": 4800, "y": 0, "largeur": 3840, "hauteur": 3840},
        )
    )
    assert plan is not None
    assert plan.contour.sommets() == [(0, 0), (8640, 0), (8640, 3840), (0, 3840)]
    assert len(plan.refends) == 1
    assert (plan.refends[0].depart, plan.refends[0].arrivee) == ((4800, 0), (4800, 3840))
    assert rapport.valide


def test_un_refend_ne_traverse_jamais_une_piece() -> None:
    """Une ligne du treillis nait du bord d'une piece et peut couper la voisine.

    Sans distinguer les deux, l'application posait un mur porteur au milieu du
    sejour, que personne n'avait dessine.
    """
    plan, _ = vers_plan(
        esquisse(
            {"nom": "séjour", "x": 0, "y": 1920, "largeur": 4800, "hauteur": 3840},
            {"nom": "ch1", "x": 0, "y": 0, "largeur": 2880, "hauteur": 1920},
            {"nom": "ch2", "x": 2880, "y": 0, "largeur": 1920, "hauteur": 1920},
        )
    )
    assert plan is not None
    for refend in plan.refends:
        assert refend.depart[0] != 2880 or refend.arrivee[1] <= 1920


def test_un_mur_qui_ne_traverse_pas_devient_une_cloison() -> None:
    plan, rapport = vers_plan(
        esquisse(
            {"nom": "séjour", "x": 0, "y": 0, "largeur": 4800, "hauteur": 7680},
            {"nom": "ch1", "x": 4800, "y": 0, "largeur": 3840, "hauteur": 3840},
            {"nom": "ch2", "x": 4800, "y": 3840, "largeur": 3840, "hauteur": 3840},
        )
    )
    assert plan is not None
    assert "CLOISON-NON-PORTEUSE" in codes(rapport)
    assert len(plan.refends) == 1, "seul le refend traversant est retenu"


def test_deux_refends_qui_se_croisent_sont_departages() -> None:
    """Le systeme ne decrit pas de jonction en croix : un sens doit ceder."""
    plan, rapport = vers_plan(
        esquisse(
            {"nom": "a", "x": 0, "y": 0, "largeur": 4800, "hauteur": 3840},
            {"nom": "b", "x": 4800, "y": 0, "largeur": 3840, "hauteur": 3840},
            {"nom": "c", "x": 0, "y": 3840, "largeur": 4800, "hauteur": 3840},
            {"nom": "d", "x": 4800, "y": 3840, "largeur": 3840, "hauteur": 3840},
        )
    )
    assert plan is not None
    assert "CLOISON-NON-PORTEUSE" in codes(rapport)
    assert len(plan.refends) == 1
    horizontaux = [r for r in plan.refends if r.depart[1] == r.arrivee[1]]
    assert horizontaux, "le sens le plus long est conserve"


def test_un_plan_en_deux_morceaux_est_refuse_et_localise() -> None:
    plan, rapport = vers_plan(
        esquisse(
            {"nom": "avant", "x": 0, "y": 0, "largeur": 4800, "hauteur": 3840},
            {"nom": "arriere", "x": 0, "y": 4080, "largeur": 4800, "hauteur": 3840},
        )
    )
    assert plan is None
    constat = next(c for c in rapport.constats if c.code == "PLAN-EN-PLUSIEURS-MORCEAUX")
    assert "avant" in constat.ou and "arriere" in constat.ou


def test_deux_pieces_qui_ne_se_touchent_que_par_un_coin_sont_refusees() -> None:
    plan, rapport = vers_plan(
        esquisse(
            {"nom": "a", "x": 0, "y": 0, "largeur": 2880, "hauteur": 2880},
            {"nom": "b", "x": 2880, "y": 2880, "largeur": 2880, "hauteur": 2880},
        )
    )
    assert plan is None
    assert "PIECES-EN-POINTE" in codes(rapport)


def test_une_esquisse_hors_grille_est_refusee_avec_le_remede() -> None:
    plan, rapport = vers_plan(
        esquisse({"nom": "a", "x": 0, "y": 0, "largeur": 5100, "hauteur": 4300})
    )
    assert plan is None
    constat = next(c for c in rapport.constats if c.code == "PIECE-HORS-GRILLE")
    assert "caler l'esquisse" in constat.message


def test_une_piece_plus_petite_que_ses_murs_est_refusee() -> None:
    plan, rapport = vers_plan(
        esquisse({"nom": "placard", "x": 0, "y": 0, "largeur": 240, "hauteur": 4800})
    )
    assert plan is None
    assert "PIECE-TROP-PETITE" in codes(rapport)


def test_une_esquisse_en_L_donne_un_contour_a_six_sommets() -> None:
    plan, _ = vers_plan(
        esquisse(
            {"nom": "séjour", "x": 0, "y": 0, "largeur": 4800, "hauteur": 7680},
            {"nom": "cuisine", "x": 4800, "y": 0, "largeur": 3840, "hauteur": 3840},
        )
    )
    assert plan is not None
    assert len(plan.contour.sommets()) == 6


# --- bout en bout -------------------------------------------------------------


def test_le_plan_derive_se_calepine_une_fois_ses_baies_posees() -> None:
    """L'esquisse s'arrete au gros oeuvre : les baies restent a poser."""
    plan, _ = vers_plan(
        esquisse(
            {"nom": "séjour", "x": 0, "y": 0, "largeur": 4800, "hauteur": 4800},
            {"nom": "cuisine", "x": 4800, "y": 0, "largeur": 3840, "hauteur": 4800},
        )
    )
    assert plan is not None
    porte = Ouverture(
        id="P-couloir", mur="R1", type="porte", position=1920, largeur=960, hauteur=2160
    )
    complet = plan.model_copy(update={"ouvertures": [porte]})
    calepinage, rapport = calepiner(complet)
    assert calepinage is not None, [str(e) for e in rapport.erreurs]
    assert len(calepinage.briques) > 100


cotes = st.integers(min_value=2000, max_value=9000)


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(cotes, cotes, cotes)
def test_deux_pieces_quelconques_donnent_toujours_un_plan(a: int, b: int, h: int) -> None:
    """Quelles que soient les cotes tapees, le calage doit produire un plan."""
    cale, _ = caler(
        esquisse(
            {"nom": "a", "x": 0, "y": 0, "largeur": a, "hauteur": h},
            {"nom": "b", "x": a, "y": 0, "largeur": b, "hauteur": h},
        )
    )
    plan, rapport = vers_plan(cale)
    assert plan is not None, [str(e) for e in rapport.erreurs]
    assert all(
        abs(x2 - x1) % GRILLE == 0 or abs(y2 - y1) % GRILLE == 0
        for (x1, y1), (x2, y2) in zip(
            plan.contour.sommets(), plan.contour.sommets()[1:], strict=False
        )
    )
    assert len(plan.refends) == 1


# --- baies posees sur l'esquisse ----------------------------------------------


def baie(**champs: Any) -> Baie:
    defauts = {"id": "B1", "type": "fenetre", "allege": 960, "hauteur": 1200}
    return Baie(**{**defauts, **champs})


def deux_pieces(*baies: Baie) -> Esquisse:
    return Esquisse(
        pieces=[
            Piece(nom="séjour", x=0, y=0, largeur=4800, hauteur=4800),
            Piece(nom="cuisine", x=4800, y=0, largeur=3840, hauteur=4800),
        ],
        baies=list(baies),
    )


def test_une_baie_est_rattachee_au_mur_qui_la_porte() -> None:
    plan, rapport = vers_plan(
        deux_pieces(
            baie(id="P1", type="porte", depart=(1920, 0), arrivee=(3120, 0), hauteur=2160),
            baie(id="F1", depart=(8640, 1920), arrivee=(8640, 3360)),
            baie(id="P2", type="porte", depart=(4800, 1920), arrivee=(4800, 2880), hauteur=2160),
        )
    )
    assert plan is not None, [str(e) for e in rapport.erreurs]
    par_id = {o.id: o for o in plan.ouvertures}
    assert par_id["P1"].mur == "M1" and par_id["P1"].position == 1920
    assert par_id["F1"].mur == "M2", "le mur de droite"
    assert par_id["P2"].mur == "R1", "une baie peut aussi se poser sur un refend"


def test_les_trois_types_de_baie_sont_acceptes() -> None:
    plan, _ = vers_plan(
        deux_pieces(
            baie(id="P1", type="porte", depart=(960, 0), arrivee=(1920, 0), hauteur=2160),
            baie(id="F1", type="fenetre", depart=(2880, 0), arrivee=(4320, 0)),
            baie(
                id="PF1",
                type="porte_fenetre",
                depart=(5760, 0),
                arrivee=(8160, 0),
                hauteur=2160,
            ),
        )
    )
    assert plan is not None
    assert {o.type for o in plan.ouvertures} == {"porte", "fenetre", "porte_fenetre"}


def test_une_porte_n_a_jamais_d_allege() -> None:
    """Le formulaire peut laisser une allege : le modele du plan la refuserait."""
    plan, _ = vers_plan(
        deux_pieces(
            baie(
                id="P1", type="porte", depart=(1920, 0), arrivee=(3120, 0), allege=960, hauteur=2160
            )
        )
    )
    assert plan is not None
    assert plan.ouvertures[0].allege == 0


def test_une_baie_posee_dans_le_vide_est_signalee() -> None:
    plan, rapport = vers_plan(deux_pieces(baie(id="F1", depart=(2400, 2400), arrivee=(3840, 2400))))
    assert plan is None
    constat = next(c for c in rapport.constats if c.code == "BAIE-SANS-MUR")
    assert "reposez-la" in constat.message


def test_une_baie_oblique_est_refusee_des_le_modele() -> None:
    with pytest.raises(ValueError, match="ni horizontale ni verticale"):
        baie(id="F1", depart=(0, 0), arrivee=(1440, 1440))


def test_une_baie_se_cale_sur_240_et_non_sur_480() -> None:
    """Une porte de 1 200 est valide : l'arrondir a 960 lui coute 24 cm de passage.

    Seules les longueurs de murs gagnent a tomber sur 480.
    """
    cale, ajustements = caler(
        deux_pieces(
            baie(id="P-entree", type="porte", depart=(1920, 0), arrivee=(3120, 0), hauteur=2160)
        )
    )
    assert cale.baies[0].largeur == 1200
    assert not [a for a in ajustements if a.quoi == "P-entree"]


def test_le_calage_signale_les_baies_retrecies() -> None:
    """Une baie hors grille bouge : il faut que ca se voie."""
    _, ajustements = caler(deux_pieces(baie(id="F-cuisine", depart=(1900, 0), arrivee=(3030, 0))))
    resume = [str(a) for a in ajustements if a.quoi == "F-cuisine"]
    assert resume and "largeur 1130 -> 1200" in resume[0]


def test_le_calage_ne_deplace_pas_le_dessin_dans_le_coin() -> None:
    """Recaler ne doit pas ramener le plan a l'origine : les murs sauteraient
    sous les baies posees, et le dessin bougerait sous la souris."""
    croquis = Esquisse(
        pieces=[
            Piece(nom="a", x=1920, y=1920, largeur=4800, hauteur=3840),
            Piece(nom="b", x=6720, y=1920, largeur=3840, hauteur=3840),
        ]
    )
    cale, ajustements = caler(croquis)
    assert ajustements == []
    assert (cale.pieces[0].x, cale.pieces[0].y) == (1920, 1920)


def test_une_esquisse_complete_se_calepine_sans_retouche() -> None:
    """Le bout du bout : du dessin au calepinage, sans passer par le YAML."""
    plan, rapport = vers_plan(
        deux_pieces(
            baie(id="P1", type="porte", depart=(1920, 0), arrivee=(3120, 0), hauteur=2160),
            baie(id="F1", depart=(8640, 1920), arrivee=(8640, 3360)),
            baie(id="PF1", type="porte_fenetre", depart=(0, 1440), arrivee=(0, 3840), hauteur=2160),
            baie(id="P2", type="porte", depart=(4800, 1920), arrivee=(4800, 2880), hauteur=2160),
        )
    )
    assert plan is not None, [str(e) for e in rapport.erreurs]
    calepinage, controle = calepiner(plan)
    assert calepinage is not None, [str(e) for e in controle.erreurs]
    assert len(calepinage.briques) > 400
