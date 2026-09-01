"""Interface en ligne de commande : codes de sortie et fichiers produits."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from briq.cli import app

RACINE = Path(__file__).resolve().parents[1]
EXEMPLE = RACINE / "exemples" / "maison.json"
runner = CliRunner()


def test_valider_un_plan_correct_sort_en_zero() -> None:
    resultat = runner.invoke(app, ["valider", str(EXEMPLE)])
    assert resultat.exit_code == 0, resultat.output
    assert "aucun constat" in resultat.output


def test_valider_un_plan_fautif_sort_en_un_et_explique(tmp_path: Path) -> None:
    fautif = json.loads(EXEMPLE.read_text())
    fautif["ouvertures"][1]["position"] = 5290  # hors grille
    fautif["ouvertures"][2]["largeur"] = 3120  # portee excessive
    chemin = tmp_path / "fautif.json"
    chemin.write_text(json.dumps(fautif), encoding="utf-8")

    resultat = runner.invoke(app, ["valider", str(chemin)])
    assert resultat.exit_code == 1
    assert "HORS-GRILLE" in resultat.output
    assert "PORTEE-EXCESSIVE" in resultat.output


def test_un_plan_inexistant_est_refuse_par_l_interface() -> None:
    resultat = runner.invoke(app, ["valider", "nulle-part.json"])
    assert resultat.exit_code != 0


@pytest.fixture(scope="module")
def dossier_produit(tmp_path_factory) -> Path:
    sortie = tmp_path_factory.mktemp("dossier")
    resultat = runner.invoke(
        app, ["calepiner", str(EXEMPLE), "-o", str(sortie), "--glouton", "-f", "svg"]
    )
    assert resultat.exit_code == 0, resultat.output
    return sortie


def test_calepiner_ecrit_tous_les_livrables(dossier_produit: Path) -> None:
    attendus = {
        "calepinage.json",
        "nomenclature.csv",
        "nomenclature-par-mur.csv",
        "metre.csv",
        "debit.csv",
        "rapport.txt",
    }
    assert attendus <= {p.name for p in dossier_produit.iterdir()}
    assert len(list((dossier_produit / "plans").glob("*.svg"))) == 17


def test_le_format_demande_est_le_seul_produit(dossier_produit: Path) -> None:
    assert not (dossier_produit / "dossier.pdf").exists()
    assert not (dossier_produit / "dxf").exists()
    assert not (dossier_produit / "3d").exists()


def test_le_modele_ecrit_est_relisible(dossier_produit: Path) -> None:
    modele = json.loads((dossier_produit / "calepinage.json").read_text())
    assert sum(modele["totaux"]["briques"].values()) == 1141
    assert {m["id"] for m in modele["murs"]} == {"M1", "M2", "M3", "M4", "R1"}


def test_deux_executions_produisent_le_meme_modele(tmp_path: Path) -> None:
    rendus = []
    for nom in ("a", "b"):
        sortie = tmp_path / nom
        resultat = runner.invoke(
            app, ["calepiner", str(EXEMPLE), "-o", str(sortie), "--glouton", "-f", "svg"]
        )
        assert resultat.exit_code == 0, resultat.output
        rendus.append((sortie / "calepinage.json").read_bytes())
    assert rendus[0] == rendus[1]


def test_sans_format_aucun_plan_n_est_produit(tmp_path: Path) -> None:
    resultat = runner.invoke(
        app, ["calepiner", str(EXEMPLE), "-o", str(tmp_path), "--glouton", "-f", "pdf"]
    )
    assert resultat.exit_code == 0, resultat.output
    assert (tmp_path / "dossier.pdf").exists()
    assert not (tmp_path / "plans").exists()


def test_nomenclature_affiche_sans_rien_ecrire(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    resultat = runner.invoke(app, ["nomenclature", str(EXEMPLE)])
    assert resultat.exit_code == 0, resultat.output
    assert "480-ANR" in resultat.output
    assert "P5-A" in resultat.output
    assert list(tmp_path.iterdir()) == []


def test_debit_affiche_le_plan_de_decoupe(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    resultat = runner.invoke(app, ["debit", str(EXEMPLE), "--glouton"])
    assert resultat.exit_code == 0, resultat.output
    assert "Debit carrelet 80x80" in resultat.output
    assert "barres de 4000" in resultat.output
    assert list(tmp_path.iterdir()) == []


def test_schema_exporte_un_schema_json_valide(tmp_path: Path) -> None:
    resultat = runner.invoke(app, ["schema", "-o", str(tmp_path)])
    assert resultat.exit_code == 0, resultat.output
    document = json.loads((tmp_path / "briq-plan-v1.schema.json").read_text())
    assert document["title"] == "Plan BRIQ, version 1"
    assert "contour" in document["properties"]
    assert "$schema" in document["properties"], "l'editeur doit pouvoir s'y accrocher"


def test_le_schema_du_depot_est_a_jour() -> None:
    """Le schema commite doit suivre le modele, sinon l'autocompletion ment."""
    from briq.model.plan import Plan

    attendu = Plan.model_json_schema(by_alias=True)
    attendu["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    attendu["title"] = "Plan BRIQ, version 1"
    publie = json.loads((RACINE / "schemas" / "briq-plan-v1.schema.json").read_text())
    assert publie == attendu, "lancer `uv run briq schema`"
