"""Interface web : routes, fragments et dossier telechargeable."""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from briq.web.app import app
from briq.web.etude import Depot, EchecDeValidation, empreinte

RACINE = Path(__file__).resolve().parents[1]
EXEMPLE = (RACINE / "exemples" / "maison.json").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def cle(client: TestClient) -> str:
    reponse = client.post("/etude", json={"plan": EXEMPLE})
    assert reponse.status_code == 200, reponse.text
    trouve = re.search(r'data-cle="([0-9a-f]+)"', reponse.text)
    assert trouve is not None
    return trouve.group(1)


def test_l_accueil_prefigure_le_plan_d_exemple(client: TestClient) -> None:
    reponse = client.get("/")
    assert reponse.status_code == 200
    assert "hauteur_sous_chainage" in reponse.text
    assert "Document de calepinage" in reponse.text, "la mention obligatoire est partout"


def test_l_etude_renvoie_la_nomenclature_et_le_metre(client: TestClient) -> None:
    reponse = client.post("/etude", json={"plan": EXEMPLE})
    assert reponse.status_code == 200
    assert "480-ANR" in reponse.text
    assert "1141" in reponse.text
    assert "Débit carrelet 80x80" in reponse.text


def test_un_plan_fautif_renvoie_les_constats_et_pas_de_resultat(client: TestClient) -> None:
    fautif = json.loads(EXEMPLE)
    fautif["ouvertures"][0]["position"] = 2890  # hors grille
    reponse = client.post("/etude", json={"plan": json.dumps(fautif)})
    assert reponse.status_code == 422
    assert "HORS-GRILLE" in reponse.text
    assert "data-cle" not in reponse.text


def test_un_json_casse_est_explique_sans_trace(client: TestClient) -> None:
    reponse = client.post("/etude", json={"plan": "{ ceci n'est pas du JSON"})
    assert reponse.status_code == 422
    assert "n'est pas lisible" in reponse.text
    assert "Traceback" not in reponse.text


def test_la_planche_est_servie_en_html_et_en_svg(client: TestClient, cle: str) -> None:
    fragment = client.get(f"/etude/{cle}/planche/0")
    assert fragment.status_code == 200
    assert "<svg" in fragment.text
    assert "viewBox" in fragment.text

    fichier = client.get(f"/etude/{cle}/planche/0.svg")
    assert fichier.status_code == 200
    assert fichier.headers["content-type"].startswith("image/svg+xml")
    assert "420.0mm" in fichier.text, "le fichier telecharge garde l'echelle exacte"


def test_la_planche_a_l_ecran_s_adapte_a_son_conteneur(client: TestClient, cle: str) -> None:
    """Sans dimensions en millimetres, le SVG suit la largeur de la page."""
    fragment = client.get(f"/etude/{cle}/planche/0")
    assert 'width="420.0mm"' not in fragment.text


def test_une_planche_inconnue_repond_404(client: TestClient, cle: str) -> None:
    assert client.get(f"/etude/{cle}/planche/999").status_code == 404
    assert client.get("/etude/inexistante/planche/0").status_code == 404


def test_le_dossier_zip_contient_tous_les_livrables(client: TestClient, cle: str) -> None:
    reponse = client.get(f"/etude/{cle}/dossier.zip")
    assert reponse.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(reponse.content))
    noms = set(archive.namelist())
    assert {"calepinage.json", "nomenclature.csv", "metre.csv", "debit.csv", "dossier.pdf"} <= noms
    assert len([n for n in noms if n.endswith(".svg")]) == 17
    assert archive.read("dossier.pdf").startswith(b"%PDF")
    modele = json.loads(archive.read("calepinage.json"))
    assert sum(modele["totaux"]["briques"].values()) == 1141


def test_le_schema_est_servi(client: TestClient) -> None:
    document = client.get("/schema.json").json()
    assert document["title"] == "Plan BRIQ, version 1"


# --- depot d'etudes -----------------------------------------------------------


def test_la_meme_source_donne_la_meme_cle() -> None:
    assert empreinte(EXEMPLE, False) == empreinte(EXEMPLE, False)
    assert empreinte(EXEMPLE, False) != empreinte(EXEMPLE, True), "le solveur fait partie de la cle"


def test_le_depot_reutilise_l_etude_deja_calculee() -> None:
    depot = Depot()
    premiere = depot.etudier(EXEMPLE)
    assert depot.etudier(EXEMPLE) is premiere


def test_le_depot_oublie_les_plus_anciennes() -> None:
    depot = Depot(capacite=2)
    cles = []
    for hauteur in (2640, 2880, 3120):
        plan = json.loads(EXEMPLE)
        plan["hauteur_sous_chainage"] = hauteur
        cles.append(depot.etudier(json.dumps(plan)).cle)
    assert depot.get(cles[0]) is None, "la plus ancienne a ete oubliee"
    assert depot.get(cles[-1]) is not None


def test_un_plan_fautif_leve_un_echec_de_validation() -> None:
    fautif = json.loads(EXEMPLE)
    fautif["ouvertures"][0]["largeur"] = 130
    with pytest.raises(EchecDeValidation) as echec:
        Depot().etudier(json.dumps(fautif))
    assert echec.value.rapport.erreurs
