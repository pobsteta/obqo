"""La chaine de publication : ce qui decide la version et ce qu'elle ecrit.

Une version fausse ne se rattrape pas — un tag pousse, une release publiee et
un numero saute restent. Ces regles sont donc testees comme le reste du moteur.
"""

from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path

import pytest

import obqo
from outils.version import (
    Commit,
    Version,
    appliquer,
    commits_depuis,
    journal,
    notes,
    prochaine,
    version_declaree,
)

RACINE = Path(__file__).resolve().parents[1]


def commits(*sujets: str) -> list[Commit]:
    lus = [Commit.lire(sujet) for sujet in sujets]
    return [commit for commit in lus if commit is not None]


# --- lecture des messages -----------------------------------------------------


def test_un_message_conventionnel_se_relit_en_entier() -> None:
    commit = Commit.lire("feat(esquisse): redimensionner les baies\n\nun corps quelconque")
    assert commit is not None
    assert (commit.type, commit.portee, commit.sujet) == (
        "feat",
        "esquisse",
        "redimensionner les baies",
    )
    assert not commit.rupture


@pytest.mark.parametrize(
    "message",
    [
        "feat!: le format de plan change",
        "feat: le format de plan change\n\nBREAKING CHANGE: la version 1 ne se relit plus",
        "fix(model)!: refuser les cotes hors grille",
    ],
)
def test_les_deux_ecritures_de_la_rupture_sont_reconnues(message: str) -> None:
    commit = Commit.lire(message)
    assert commit is not None and commit.rupture


def test_un_message_hors_convention_ne_publie_rien_au_lieu_de_bloquer() -> None:
    """Un depot ne doit pas se figer sur un point-virgule oublie."""
    assert Commit.lire("corrige deux trois trucs") is None
    assert Commit.lire("") is None


# --- calcul de la version -----------------------------------------------------


def test_une_nouveaute_avance_la_mineure_et_remet_la_corrective_a_zero() -> None:
    assert prochaine(Version(1, 2, 3), commits("feat: dessiner les baies")) == Version(1, 3, 0)


def test_une_correction_avance_la_corrective() -> None:
    assert prochaine(Version(1, 2, 3), commits("fix: recaler la baie")) == Version(1, 2, 4)
    assert prochaine(Version(1, 2, 3), commits("perf: debiter plus vite")) == Version(1, 2, 4)


def test_la_documentation_seule_ne_publie_pas() -> None:
    assert prochaine(Version(0, 1, 0), commits("docs: relire le README", "chore: menage")) is None
    assert prochaine(Version(0, 1, 0), []) is None


def test_une_rupture_en_version_zero_avance_la_mineure_et_pas_la_majeure() -> None:
    """Une version 0 ne promet rien : le passage en 1.0 se decide a la main."""
    assert prochaine(Version(0, 4, 2), commits("feat!: nouveau format")) == Version(0, 5, 0)


def test_une_rupture_en_version_stable_avance_la_majeure() -> None:
    assert prochaine(Version(1, 4, 2), commits("feat!: nouveau format")) == Version(2, 0, 0)


def test_la_rupture_l_emporte_sur_la_nouveaute_et_la_correction() -> None:
    lot = commits("fix: un detail", "feat!: nouveau format", "feat: une nouveaute")
    assert prochaine(Version(1, 0, 0), lot) == Version(2, 0, 0)


# --- notes et journal ---------------------------------------------------------


def test_les_notes_groupent_par_section_et_gardent_la_portee() -> None:
    corps = notes(
        commits(
            "fix(web): rendre la redirection permanente",
            "feat(esquisse): redimensionner les baies",
            "docs: relire le README",
        )
    )
    assert corps.index("### Nouveautés") < corps.index("### Corrections")
    assert "- **esquisse** — redimensionner les baies" in corps
    assert "README" not in corps, "un commit qui ne publie pas ne figure pas aux notes"


def test_le_journal_recoit_la_version_en_tete_et_garde_les_anciennes() -> None:
    ancien = "# Journal des versions\n\n## 0.1.0 — 2026-01-02\n\n### Nouveautés\n\n- le début\n"
    neuf = journal(ancien, Version(0, 2, 0), date(2026, 9, 2), "### Corrections\n\n- un détail")
    assert neuf.index("## 0.2.0 — 2026-09-02") < neuf.index("## 0.1.0 — 2026-01-02")
    assert neuf.startswith("# Journal des versions")
    assert "- le début" in neuf


def test_un_journal_vide_se_cree_sans_perdre_son_titre() -> None:
    neuf = journal("# Journal des versions\n", Version(0, 1, 0), date(2026, 9, 2), "### x\n\n- y")
    assert neuf.count("# Journal des versions") == 1
    assert "## 0.1.0 — 2026-09-02" in neuf


# --- ecriture dans le depot ---------------------------------------------------


def test_appliquer_ecrit_la_meme_version_dans_les_trois_fichiers(tmp_path: Path) -> None:
    (tmp_path / "src" / "obqo").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "obqo"\nversion = "0.1.0"\n')
    (tmp_path / "src" / "obqo" / "__init__.py").write_text('__version__ = "0.1.0"\n')
    (tmp_path / "CHANGELOG.md").write_text("# Journal des versions\n")

    ecrits = appliquer(Version(0, 2, 0), "### Nouveautés\n\n- une baie", date(2026, 9, 2), tmp_path)

    assert len(ecrits) == 3
    assert 'version = "0.2.0"' in (tmp_path / "pyproject.toml").read_text()
    assert '__version__ = "0.2.0"' in (tmp_path / "src" / "obqo" / "__init__.py").read_text()
    assert "## 0.2.0 — 2026-09-02" in (tmp_path / "CHANGELOG.md").read_text()


# --- garde-fous sur le depot lui-meme -----------------------------------------


def test_les_trois_versions_du_depot_concordent() -> None:
    """pyproject, le module et le paquet installe disent la meme chose.

    C'est ce qui rend `obqo --version` digne de foi : la chaine de publication
    les ecrit ensemble, ce test verifie qu'aucune main ne les a separees.
    """
    declaree = version_declaree()
    with (RACINE / "pyproject.toml").open("rb") as flux:
        assert str(declaree) == tomllib.load(flux)["project"]["version"]
    assert str(declaree) == obqo.__version__


def test_les_commits_du_depot_se_relisent() -> None:
    """L'outil tourne sur le vrai historique, pas seulement sur des exemples."""
    for commit in commits_depuis(None):
        assert commit.type
        assert commit.sujet
