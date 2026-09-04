"""Justification structurale : le modele dit-il ce que la RDM dit ?

Un module de calcul qui ne se compare a rien n'est qu'une opinion en Python. Le
grillage de PyNite est donc confronte, chiffre par chiffre, aux formules
fermees de la poutre sur deux appuis — la seule verification qui prouve que les
axes, les unites et les combinaisons sont ceux qu'on croit.

`materiaux` et `eurocode5` se testent sans PyNite : c'est la contrepartie de la
regle qui les garde importables avec la seule bibliotheque standard.
"""

from __future__ import annotations

import importlib.util
import sys
from itertools import pairwise
from pathlib import Path

import pytest
from typer.testing import CliRunner

from obqo.cli import app
from obqo.rules.catalogue import RAIDISSEUR_PAR_RANG
from obqo.structure.entraxe import (
    CHEVILLAGE,
    FLECHE_RANG,
    HAUTEUR_PAR_DEFAUT,
    entraxe_maxi,
    note,
    verifier,
)
from obqo.structure.eurocode5 import (
    Section,
    coefficient_flambement,
    elancement,
    elancement_relatif,
    resistance_de_calcul,
    taux_fleche,
)
from obqo.structure.materiaux import BETA_C, CLASSES, GAMMA_M, Hypotheses, k_mod
from obqo.structure.modele import Pan, calculer
from obqo.units import EPAISSEUR_MUR, GRILLE, HAUTEUR_RANG

RACINE = Path(__file__).resolve().parents[1]
EXEMPLE = RACINE / "exemples" / "maison.json"
runner = CliRunner()

sans_pynite = pytest.mark.skipif(
    importlib.util.find_spec("Pynite") is None,
    reason="extra « structure » absent : uv sync --extra structure",
)


# --- tables et formules, sans PyNite ------------------------------------------


def test_les_tables_de_norme_s_importent_sans_l_extra() -> None:
    """`materiaux` ne doit rien devoir a PyNite : c'est une table, pas un calcul."""
    assert CLASSES["C24"].f_m_k == 24.0
    assert CLASSES["C24"].e_0_mean == 11000.0
    assert GAMMA_M["bois massif"] == 1.3
    assert k_mod(2, "court terme") == 0.90


def test_le_k_mod_refuse_une_classe_de_service_inconnue() -> None:
    with pytest.raises(ValueError, match="classe de service 4"):
        k_mod(4, "court terme")


def test_la_section_donne_les_grandeurs_de_la_rdm() -> None:
    """Une section 80 x 240 vue dans son plan de flexion, a la main."""
    section = Section(80, 240)
    assert section.aire == 19200
    assert section.inertie == pytest.approx(80 * 240**3 / 12)
    assert section.module_de_flexion == pytest.approx(80 * 240**2 / 6)
    assert section.rayon_de_giration == pytest.approx(240 / 12**0.5)


def test_la_resistance_de_calcul_suit_2_14() -> None:
    assert resistance_de_calcul(24.0, 0.9, 1.3) == pytest.approx(24 * 0.9 / 1.3)


def test_un_element_court_ne_flambe_pas() -> None:
    """En dessous de 0,3 d'elancement relatif, (6.25) rend k_c = 1 exactement."""
    assert coefficient_flambement(0.3, BETA_C) == 1.0
    assert coefficient_flambement(0.1, BETA_C) == 1.0


def test_le_coefficient_de_flambement_decroit_avec_l_elancement() -> None:
    valeurs = [coefficient_flambement(x / 10, BETA_C) for x in range(4, 20)]
    assert all(a > b for a, b in pairwise(valeurs))
    assert all(0 < v <= 1 for v in valeurs)


def test_le_poteau_de_la_maison_d_exemple_a_l_elancement_attendu() -> None:
    """Controle a la main : 80 x 240, 2 640 de haut, flambement hors plan."""
    bois = CLASSES["C24"]
    section = Section(80, EPAISSEUR_MUR)
    lambda_ = elancement(2640, section.rayon_de_giration)
    assert lambda_ == pytest.approx(38.1, abs=0.1)
    relatif = elancement_relatif(lambda_, bois.f_c_0_k, bois.e_0_05)
    assert relatif == pytest.approx(0.646, abs=0.01)
    assert coefficient_flambement(relatif, BETA_C) == pytest.approx(0.90, abs=0.01)


def test_la_fleche_admissible_est_la_portee_divisee() -> None:
    assert taux_fleche(10.0, 5000, 250) == pytest.approx(0.5)


def test_les_hypotheses_lisent_le_nombre_de_chevilles_au_catalogue() -> None:
    """Une seule source de verite : changer le catalogue change le calcul."""
    assert Hypotheses().chevilles_par_rang == RAIDISSEUR_PAR_RANG["C1"] == 2


# --- le grillage face aux formules fermees ------------------------------------


@sans_pynite
def test_le_rang_se_comporte_comme_une_poutre_sur_deux_appuis() -> None:
    """M = qL2/8, V = qL/2, w = 5qL4/384EI : le grillage doit les retrouver.

    C'est le test qui prouve que les axes, les unites et les combinaisons sont
    ceux qu'on croit. S'il tombe, tout le reste du module est faux sans le dire.
    """
    hyp = Hypotheses()
    pan = Pan(longueur=6000, hauteur=HAUTEUR_PAR_DEFAUT)
    efforts = calculer(pan, hyp)

    portee = pan.portee
    q_elu = 1.5 * hyp.pression_vent / 1000 * HAUTEUR_RANG
    assert efforts.moment_rang == pytest.approx(q_elu * portee**2 / 8, rel=1e-3)
    assert efforts.tranchant_rang == pytest.approx(q_elu * portee / 2, rel=1e-3)
    assert efforts.reaction_rang == pytest.approx(q_elu * portee / 2, rel=1e-3)

    q_els = hyp.pression_vent / 1000 * HAUTEUR_RANG
    inertie = EPAISSEUR_MUR * HAUTEUR_RANG**3 / 12 * hyp.efficacite_rang
    attendue = 5 * q_els * portee**4 / (384 * CLASSES[hyp.classe].e_0_mean * inertie)
    assert efforts.fleche_rang == pytest.approx(attendue, rel=1e-3)


@sans_pynite
def test_le_poteau_reprend_la_charge_verticale_ponderee() -> None:
    """1,35 x charge x part x portee, et rien d'autre : le modele n'invente pas."""
    hyp = Hypotheses()
    pan = Pan(longueur=6000, hauteur=HAUTEUR_PAR_DEFAUT)
    efforts = calculer(pan, hyp)
    attendu = 1.35 * hyp.charge_verticale * hyp.part_poteau * pan.portee
    assert efforts.normal_poteau == pytest.approx(attendu, rel=1e-3)


@sans_pynite
def test_le_poteau_recoit_bien_plus_que_son_propre_module_de_vent() -> None:
    """Le grillage a un interet : les rangs deversent leur reaction dans le poteau.

    Un poteau charge de son seul module de 240 aurait un moment de qH2/8 avec
    q = p x 240. Le moment reel doit etre plusieurs fois plus grand, sinon les
    rangs ne sont pas connectes et le modele ne sert a rien.
    """
    hyp = Hypotheses()
    pan = Pan(longueur=6000, hauteur=HAUTEUR_PAR_DEFAUT)
    efforts = calculer(pan, hyp)
    seul = 1.5 * hyp.pression_vent / 1000 * GRILLE * pan.hauteur**2 / 8
    assert efforts.moment_poteau > 10 * seul


@sans_pynite
def test_deux_executions_donnent_le_meme_verdict() -> None:
    """Sortie deterministe : sans cela, aucune note n'est comparable a la suivante."""
    hyp = Hypotheses()
    pan = Pan(longueur=6000, hauteur=HAUTEUR_PAR_DEFAUT)
    assert note(verifier(pan, hyp), hyp) == note(verifier(pan, hyp), hyp)


# --- ce que le module conclut --------------------------------------------------


@sans_pynite
def test_le_pan_de_six_metres_du_brief_est_admis() -> None:
    """Le paragraphe 1.7 fixe 6 m : le calcul doit au moins le confirmer."""
    verification = verifier(Pan(longueur=6000, hauteur=HAUTEUR_PAR_DEFAUT), Hypotheses())
    assert verification.admis
    assert verification.taux_maxi < 0.5


@sans_pynite
def test_l_entraxe_maximal_depasse_celui_du_brief_et_la_fleche_le_commande() -> None:
    """Avec les defauts, le 6 m du brief est prudent — et c'est la fleche qui borne."""
    maxi = entraxe_maxi(Hypotheses(), HAUTEUR_PAR_DEFAUT)
    assert maxi % GRILLE == 0
    assert maxi > 6000
    assert verifier(Pan(longueur=maxi, hauteur=HAUTEUR_PAR_DEFAUT), Hypotheses()).critere == (
        FLECHE_RANG
    )


@sans_pynite
def test_un_rang_deux_fois_moins_efficace_raccourcit_l_entraxe() -> None:
    """L'efficacite du rang commande l'entraxe : c'est pourquoi l'essai E2 presse."""
    souple = entraxe_maxi(Hypotheses(efficacite_rang=0.1), HAUTEUR_PAR_DEFAUT)
    raide = entraxe_maxi(Hypotheses(efficacite_rang=0.3), HAUTEUR_PAR_DEFAUT)
    assert souple < raide


@sans_pynite
def test_une_cheville_trop_faible_fait_du_chevillage_le_critere() -> None:
    """A 0,3 kN par C1, ce n'est plus le bois qui commande mais la liaison."""
    hyp = Hypotheses(resistance_cheville_k=0.3)
    assert verifier(Pan(longueur=6000, hauteur=HAUTEUR_PAR_DEFAUT), hyp).critere == CHEVILLAGE


@sans_pynite
def test_un_pan_hors_grille_est_refuse_a_la_construction() -> None:
    with pytest.raises(ValueError, match="multiple positif"):
        Pan(longueur=6001, hauteur=HAUTEUR_PAR_DEFAUT)


# --- la commande ---------------------------------------------------------------


@sans_pynite
def test_la_commande_sur_un_pan_donne_sort_en_zero() -> None:
    resultat = runner.invoke(app, ["entraxe", "--pan", "6000"])
    assert resultat.exit_code == 0, resultat.output
    assert "admis" in resultat.output
    assert "Hypotheses" in resultat.output


@sans_pynite
def test_la_commande_sur_un_pan_impossible_sort_en_un() -> None:
    """Vingt metres de pan sous un vent double : le refus doit se voir au code."""
    resultat = runner.invoke(app, ["entraxe", "--pan", "20160", "--vent", "1.6"])
    assert resultat.exit_code == 1, resultat.output
    assert "REFUSE" in resultat.output


@sans_pynite
def test_la_commande_sur_un_plan_note_chaque_pan_exterieur() -> None:
    """Un pan par ligne, et deux executions donnent le meme tableau."""
    premiere = runner.invoke(app, ["entraxe", str(EXEMPLE)])
    assert premiere.exit_code == 0, premiere.output
    assert "M1 [0-2880]" in premiere.output
    assert "R1" in premiere.output  # le refend est nomme comme non verifie
    seconde = runner.invoke(app, ["entraxe", str(EXEMPLE)])
    assert seconde.output == premiere.output


@sans_pynite
def test_le_dossier_calepine_porte_la_note_de_structure(tmp_path: Path) -> None:
    """§5.3 : quand l'extra est la, le dossier gagne structure.txt."""
    resultat = runner.invoke(
        app, ["calepiner", str(EXEMPLE), "-o", str(tmp_path), "-f", "svg", "--glouton"]
    )
    assert resultat.exit_code == 0, resultat.output
    note_ecrite = (tmp_path / "structure.txt").read_text(encoding="utf-8")
    assert "pans exterieurs verifies" in note_ecrite
    assert "non produite" not in (tmp_path / "rapport.txt").read_text(encoding="utf-8")


# --- sans l'extra ---------------------------------------------------------------
# Ces deux tests simulent l'absence de PyNite plutot que de l'exiger : ils
# tournent donc dans les deux installations, et c'est ce comportement-la qui
# doit etre verrouille, puisque c'est celui que verra la plupart des gens.


def test_sans_l_extra_la_commande_sort_en_deux_et_dit_quoi_installer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "Pynite", None)
    resultat = runner.invoke(app, ["entraxe", "--pan", "6000"])
    assert resultat.exit_code == 2
    sortie = resultat.output + str(resultat.stderr)
    assert "Justification structurale indisponible" in sortie
    assert "obqo[structure]" in sortie  # Rich ne doit pas manger le nom de l'extra


def test_sans_l_extra_le_dossier_sort_entier_et_le_rapport_le_dit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Une piece manque au dossier, le calepinage n'en est pas arrete pour autant."""
    monkeypatch.setitem(sys.modules, "Pynite", None)
    resultat = runner.invoke(
        app, ["calepiner", str(EXEMPLE), "-o", str(tmp_path), "-f", "svg", "--glouton"]
    )
    assert resultat.exit_code == 0, resultat.output
    assert not (tmp_path / "structure.txt").exists()
    assert "non produite" in (tmp_path / "rapport.txt").read_text(encoding="utf-8")
