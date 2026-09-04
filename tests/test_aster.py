"""Les echantillons Code_Aster suivent-ils encore les tables du depot ?

`specs/structure/aster/geometrie_echantillon.py` derive la geometrie des essais
des tables de `rules/`. Les JSON commites sont donc des **sorties**, pas des
sources : s'ils divergent, c'est qu'une regle a change sans que le maillage
suive, et un maillage qui ne suit plus la brique qu'il represente ne prouve
rien. Ce test verrouille exactement cela.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from obqo.rules.catalogue import PIECES, RAIDISSEUR_PAR_RANG

ASTER = Path(__file__).resolve().parents[1] / "specs" / "structure" / "aster"


def _generateur() -> object:
    """Charge le script de `specs/`, qui n'est pas un module du paquet."""
    chemin = ASTER / "geometrie_echantillon.py"
    specification = importlib.util.spec_from_file_location("geometrie_echantillon", chemin)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


ECHANTILLONS = {"rang": ["rang", "--briques", "3"], "cheville": ["cheville"], "poteau": ["poteau"]}


@pytest.mark.parametrize("nom", sorted(ECHANTILLONS))
def test_le_json_commite_est_bien_celui_que_produit_le_script(
    nom: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Aucune retouche a la main : le JSON se regenere, il ne s'edite pas."""
    cible = tmp_path / f"{nom}.json"
    _generateur().main([*ECHANTILLONS[nom], "-o", str(cible)])  # type: ignore[attr-defined]
    capsys.readouterr()
    assert json.loads(cible.read_text(encoding="utf-8")) == json.loads(
        (ASTER / f"{nom}.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("nom", sorted(ECHANTILLONS))
def test_chaque_piece_d_echantillon_existe_au_catalogue(nom: str) -> None:
    document = json.loads((ASTER / f"{nom}.json").read_text(encoding="utf-8"))
    for piece in document["pieces"]:
        assert piece["ref"] in PIECES
        assert piece["fil"] in ("x", "y", "z")
    noms = [cheville["nom"] for cheville in document["chevilles"]]
    assert len(noms) == len(set(noms)), "un nom de cheville en double casserait FUT_/TROU_"


def test_l_echantillon_de_poteau_pose_autant_de_chevilles_que_le_catalogue() -> None:
    """H-A4 et D7 doivent dire la meme chose, sinon l'essai mesure autre chose."""
    document = json.loads((ASTER / "poteau.json").read_text(encoding="utf-8"))
    par_rang = len(document["chevilles"]) / document["rangs"]
    assert par_rang == RAIDISSEUR_PAR_RANG["C1"] == 2
    assert document["chevilles_par_rang_au_catalogue"] == 2
