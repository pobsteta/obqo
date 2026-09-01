"""Un plan fautif doit produire les bons messages, pas un calepinage approximatif."""

from __future__ import annotations

import pytest

from briq.engine.calepinage import calepiner
from briq.engine.validation import Gravite

from .conftest import plan_rectangle


def codes(plan) -> set[str]:
    _, rapport = calepiner(plan)
    return {c.code for c in rapport.constats}


def test_baie_hors_grille_refusee_par_defaut() -> None:
    plan = plan_rectangle(
        5760,
        4800,
        ouvertures=[
            {
                "id": "F1",
                "mur": "M1",
                "type": "fenetre",
                "position": 1850,
                "largeur": 1130,
                "allege": 900,
                "hauteur": 1200,
            }
        ],
    )
    calepinage, rapport = calepiner(plan)
    assert calepinage is None
    hors_grille = [c for c in rapport.erreurs if c.code == "HORS-GRILLE"]
    assert {c.message.split(" =")[0] for c in hors_grille} == {
        "position",
        "largeur",
        "allege",
    }


def test_baie_hors_grille_recalee_en_mode_arrondir() -> None:
    plan = plan_rectangle(
        5760,
        4800,
        parametres={"hors_grille": "arrondir"},
        ouvertures=[
            {
                "id": "F1",
                "mur": "M1",
                "type": "fenetre",
                "position": 1850,
                "largeur": 1130,
                "allege": 900,
                "hauteur": 1200,
            }
        ],
    )
    calepinage, rapport = calepiner(plan)
    assert calepinage is not None
    recales = [c for c in rapport.avertissements if c.code == "HORS-GRILLE-RECALE"]
    assert len(recales) == 3
    assert "1850 mm recale a 1920 mm" in recales[0].message


def test_portee_de_3_m_prescrit_un_lamelle_colle() -> None:
    plan = plan_rectangle(
        5760,
        4800,
        ouvertures=[
            {
                "id": "PF1",
                "mur": "M1",
                "type": "porte_fenetre",
                "position": 1200,
                "largeur": 3120,
                "hauteur": 2160,
            }
        ],
    )
    calepinage, rapport = calepiner(plan)
    assert calepinage is not None, "une portee excessive n'est pas une erreur bloquante"
    assert "PORTEE-EXCESSIVE" in {c.code for c in rapport.avertissements}
    assert "LINTEAU-LAMELLE" in {c.code for c in rapport.avertissements}
    lamelles = [e for e in calepinage.murs[0].elements if e.piece == "P9-LC"]
    assert len(lamelles) == 1
    assert lamelles[0].longueur == 3120 + 480
    assert not [e for e in calepinage.murs[0].elements if e.piece == "P9"]


def test_baie_collee_a_l_angle_refusee() -> None:
    plan = plan_rectangle(
        5760,
        4800,
        ouvertures=[
            {
                "id": "F1",
                "mur": "M1",
                "type": "fenetre",
                "position": 240,
                "largeur": 1200,
                "allege": 960,
                "hauteur": 1200,
            }
        ],
    )
    assert "BAIE-TROP-PRES-ANGLE" in codes(plan)


def test_mur_de_plus_de_6_m_sans_raidisseur_refuse() -> None:
    assert "RAIDISSEUR-MANQUANT" in codes(plan_rectangle(6240, 4800))
    assert "RAIDISSEUR-MANQUANT" not in codes(plan_rectangle(5760, 4800))


def test_baie_plus_haute_que_le_mur_refusee() -> None:
    plan = plan_rectangle(
        5760,
        4800,
        hauteur=2640,
        ouvertures=[
            {
                "id": "P1",
                "mur": "M1",
                "type": "porte",
                "position": 1440,
                "largeur": 1200,
                "hauteur": 2640,
            }
        ],
    )
    assert "BAIE-TROP-HAUTE" in codes(plan)


def test_trumeau_insuffisant_entre_deux_baies() -> None:
    plan = plan_rectangle(
        5760,
        4800,
        ouvertures=[
            {
                "id": f"F{i}",
                "mur": "M1",
                "type": "fenetre",
                "position": p,
                "largeur": 960,
                "allege": 960,
                "hauteur": 1200,
            }
            for i, p in enumerate((1440, 2640))
        ],
    )
    assert "TRUMEAU-INSUFFISANT" in codes(plan)


def test_contour_non_ferme_refuse() -> None:
    from briq.model.plan import Plan

    with pytest.raises(ValueError, match="ne se referme pas"):
        Plan.model_validate(
            {
                "hauteur_sous_chainage": 2640,
                "contour": {
                    "trace": {
                        "segments": [
                            {"direction": "est", "longueur": 4800},
                            {"direction": "nord", "longueur": 4800},
                            {"direction": "ouest", "longueur": 4560},
                            {"direction": "sud", "longueur": 4800},
                        ]
                    }
                },
            }
        ).contour.sommets()


def test_mur_hors_grille_refuse_sans_recalage() -> None:
    plan = plan_rectangle(4850, 4800, parametres={"hors_grille": "arrondir"})
    _, rapport = calepiner(plan)
    erreur = next(c for c in rapport.erreurs if c.code == "MUR-HORS-GRILLE")
    assert erreur.gravite is Gravite.ERREUR
    assert "romprait sa fermeture" in erreur.message
