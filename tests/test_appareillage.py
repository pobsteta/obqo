"""Proprietes de l'appareillage : le filet de securite du moteur.

Ces tests ne verifient pas des cas choisis a la main mais des **invariants**, sur
des milliers de courses tirees au hasard. C'est ce qui attrape les cas limites
qu'on n'ecrit jamais soi-meme.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from briq.engine.appareillage import decouper, joints, parite_du_rang
from briq.units import GRILLE, LONGUEUR_BRIQUE, LONGUEUR_DEMI

courses = st.tuples(
    st.integers(min_value=0, max_value=40).map(lambda n: n * GRILLE),
    st.integers(min_value=1, max_value=60).map(lambda n: n * GRILLE),
)


@given(courses, st.integers(0, 1))
def test_la_course_est_exactement_remplie(course: tuple[int, int], parite: int) -> None:
    debut, longueur = course
    assert sum(decouper(debut, longueur, parite)) == longueur


@given(courses, st.integers(0, 1))
def test_les_joints_ont_tous_la_parite_demandee(course: tuple[int, int], parite: int) -> None:
    debut, longueur = course
    decoupe = decouper(debut, longueur, parite)
    assert all((j // GRILLE) % 2 == parite for j in joints(debut, decoupe))


@given(courses, st.integers(0, 1))
def test_au_plus_une_demi_brique_par_bout_de_course(course: tuple[int, int], parite: int) -> None:
    debut, longueur = course
    decoupe = decouper(debut, longueur, parite)
    demis = [i for i, x in enumerate(decoupe) if x == LONGUEUR_DEMI]
    assert all(x in (LONGUEUR_BRIQUE, LONGUEUR_DEMI) for x in decoupe)
    assert len(demis) <= 2
    # Une demi-brique ne peut se trouver qu'a une extremite de la course :
    # la placer au milieu inverserait la parite des joints suivants.
    assert all(i in (0, len(decoupe) - 1) for i in demis)


@given(courses)
def test_les_deux_parites_sont_toujours_realisables(course: tuple[int, int]) -> None:
    debut, longueur = course
    assert decouper(debut, longueur, 0) != [] or longueur == 0
    assert decouper(debut, longueur, 1) != [] or longueur == 0


@given(st.integers(0, 40).map(lambda n: n * GRILLE), st.integers(0, 30))
def test_la_parite_alterne_a_chaque_rang(debut: int, rang: int) -> None:
    assert parite_du_rang(debut, rang) != parite_du_rang(debut, rang + 1)


def test_la_course_partant_de_l_origine_commence_par_une_480() -> None:
    """Le catalogue exige une 480 a l'angle : la parite est ancree pour cela."""
    for rang in range(6):
        for debut0 in (0, GRILLE):
            debut = debut0 if rang % 2 == 0 else GRILLE - debut0
            decoupe = decouper(debut, 4800, parite_du_rang(debut0, rang))
            assert decoupe[0] == LONGUEUR_BRIQUE


@pytest.mark.parametrize("longueur", [100, 250, 479])
def test_une_course_hors_grille_est_refusee(longueur: int) -> None:
    with pytest.raises(ValueError, match="multiple de 240"):
        decouper(0, longueur, 0)
