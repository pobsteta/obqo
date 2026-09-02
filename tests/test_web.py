"""Interface web : routes, fragments et dossier telechargeable."""

from __future__ import annotations

import html
import io
import json
import re
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from obqo.web.app import app
from obqo.web.etude import Depot, EchecDeValidation, empreinte

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


# --- module d'esquisse --------------------------------------------------------

DEUX_PIECES = {
    "nom": "essai",
    "hauteur_sous_chainage": 2640,
    "pas": 480,
    "pieces": [
        {"nom": "séjour", "x": 0, "y": 0, "largeur": 5000, "hauteur": 4000},
        {"nom": "cuisine", "x": 5000, "y": 0, "largeur": 3500, "hauteur": 4000},
    ],
}


def test_la_page_d_esquisse_s_affiche(client: TestClient) -> None:
    reponse = client.get("/esquisse")
    assert reponse.status_code == 200
    assert "esquisse.js" in reponse.text
    assert "Document de calepinage" in reponse.text


def test_caler_renvoie_les_pieces_recalees_et_les_ecarts(client: TestClient) -> None:
    reponse = client.post("/esquisse/caler", json=DEUX_PIECES)
    assert reponse.status_code == 200
    donnees = reponse.json()
    assert [p["largeur"] for p in donnees["pieces"]] == [4800, 3840]
    assert len(donnees["ajustements"]) == 2
    assert "5000 x 4000 -> 4800 x 3840" in donnees["ajustements"][0]


def test_le_plan_derive_contient_contour_refend_et_apercu(client: TestClient) -> None:
    reponse = client.post("/esquisse/plan", json=DEUX_PIECES)
    assert reponse.status_code == 200
    assert "contour:" in reponse.text
    assert "refends:" in reponse.text
    assert "ouvertures: []" in reponse.text, "les baies restent a poser"
    assert "<svg" in reponse.text


def test_le_plan_derive_est_relisible_par_l_application(client: TestClient) -> None:
    """Ce que l'esquisse ecrit doit repasser par la porte d'entree normale."""
    import re

    from obqo.model.lecture import depuis_texte

    reponse = client.post("/esquisse/plan", json=DEUX_PIECES)
    source = re.search(r'<textarea id="source-derivee"[^>]*>(.*?)</textarea>', reponse.text, re.S)
    assert source is not None
    plan = depuis_texte(source.group(1))
    assert plan.contour.sommets() == [(0, 0), (8640, 0), (8640, 3840), (0, 3840)]
    assert len(plan.refends) == 1


def test_des_pieces_qui_se_chevauchent_donnent_un_message_lisible(client: TestClient) -> None:
    reponse = client.post(
        "/esquisse/caler",
        json={
            "pieces": [
                {"nom": "a", "x": 0, "y": 0, "largeur": 4000, "hauteur": 4000},
                {"nom": "b", "x": 2000, "y": 2000, "largeur": 4000, "hauteur": 4000},
            ]
        },
    )
    assert reponse.status_code == 422
    message = reponse.json()["erreur"]
    assert "chevauchent" in message
    assert "pydantic" not in message and "input_value" not in message


def test_une_esquisse_en_morceaux_est_refusee_avec_ses_reperes(client: TestClient) -> None:
    reponse = client.post(
        "/esquisse/plan",
        json={
            "pieces": [
                {"nom": "avant", "x": 0, "y": 0, "largeur": 4800, "hauteur": 3840},
                {"nom": "arriere", "x": 0, "y": 4080, "largeur": 4800, "hauteur": 3840},
            ]
        },
    )
    assert reponse.status_code == 422
    assert "PLAN-EN-PLUSIEURS-MORCEAUX" in reponse.text
    assert "avant" in reponse.text


def test_les_murs_derives_suivent_le_dessin(client: TestClient) -> None:
    """Les murs renvoyes doivent tomber sur les pieces telles qu'elles sont a
    l'ecran : un decalage rendrait la pose des baies impossible."""
    reponse = client.post(
        "/esquisse/murs",
        json={
            "pieces": [
                {"nom": "a", "x": 1920, "y": 1920, "largeur": 4800, "hauteur": 3840},
                {"nom": "b", "x": 6720, "y": 1920, "largeur": 3840, "hauteur": 3840},
            ]
        },
    )
    assert reponse.status_code == 200
    murs = {m["id"]: m for m in reponse.json()["murs"]}
    assert murs["M1"]["depart"] == [1920, 1920]
    assert murs["R1"]["depart"] == [6720, 1920]


def test_le_plan_derive_reprend_les_baies_posees(client: TestClient) -> None:
    reponse = client.post(
        "/esquisse/plan",
        json={
            "pieces": [
                {"nom": "a", "x": 0, "y": 0, "largeur": 4800, "hauteur": 4800},
                {"nom": "b", "x": 4800, "y": 0, "largeur": 3840, "hauteur": 4800},
            ],
            "baies": [
                {
                    "id": "P1",
                    "type": "porte",
                    "depart": [1920, 0],
                    "arrivee": [3120, 0],
                    "allege": 0,
                    "hauteur": 2160,
                },
                {
                    "id": "F1",
                    "type": "fenetre",
                    "depart": [8640, 1920],
                    "arrivee": [8640, 3360],
                    "allege": 960,
                    "hauteur": 1200,
                },
                {
                    "id": "PF1",
                    "type": "porte_fenetre",
                    "depart": [0, 1440],
                    "arrivee": [0, 3840],
                    "allege": 0,
                    "hauteur": 2160,
                },
                {
                    "id": "P2",
                    "type": "porte",
                    "depart": [4800, 1920],
                    "arrivee": [4800, 2880],
                    "allege": 0,
                    "hauteur": 2160,
                },
            ],
        },
    )
    assert reponse.status_code == 200
    assert "ouvertures:" in reponse.text and "ouvertures: []" not in reponse.text
    assert "passage libre" in reponse.text, "la trémie n'est pas le passage"
    assert "Plan complet" in reponse.text, "ce plan doit se calepiner tel quel"


def test_le_plan_derive_avec_baies_repasse_par_la_porte_d_entree(client: TestClient) -> None:
    import re

    from obqo.engine.calepinage import calepiner
    from obqo.model.lecture import depuis_texte

    reponse = client.post(
        "/esquisse/plan",
        json={
            "pieces": [
                {"nom": "a", "x": 0, "y": 0, "largeur": 4800, "hauteur": 4800},
                {"nom": "b", "x": 4800, "y": 0, "largeur": 3840, "hauteur": 4800},
            ],
            "baies": [
                {
                    "id": "P1",
                    "type": "porte",
                    "depart": [1920, 0],
                    "arrivee": [3120, 0],
                    "allege": 0,
                    "hauteur": 2160,
                },
                {
                    "id": "F1",
                    "type": "fenetre",
                    "depart": [8640, 1920],
                    "arrivee": [8640, 3360],
                    "allege": 960,
                    "hauteur": 1200,
                },
                {
                    "id": "PF1",
                    "type": "porte_fenetre",
                    "depart": [0, 1440],
                    "arrivee": [0, 3840],
                    "allege": 0,
                    "hauteur": 2160,
                },
                {
                    "id": "P2",
                    "type": "porte",
                    "depart": [4800, 1920],
                    "arrivee": [4800, 2880],
                    "allege": 0,
                    "hauteur": 2160,
                },
            ],
        },
    )
    import html

    source = re.search(r'<textarea id="source-derivee"[^>]*>(.*?)</textarea>', reponse.text, re.S)
    assert source is not None
    plan = depuis_texte(html.unescape(source.group(1)))
    calepinage, rapport = calepiner(plan)
    assert calepinage is not None, [str(e) for e in rapport.erreurs]
    assert len(plan.ouvertures) == 4


def test_une_esquisse_s_enregistre_et_se_rouvre(client: TestClient) -> None:
    croquis = {
        "nom": "Maison Obstetar",
        "hauteur_sous_chainage": 2640,
        "pieces": [
            {"nom": "séjour", "x": 0, "y": 0, "largeur": 4800, "hauteur": 4800},
            {"nom": "cuisine", "x": 4800, "y": 0, "largeur": 3840, "hauteur": 4800},
        ],
        "baies": [
            {
                "id": "porte d'entrée",
                "type": "porte",
                "depart": [1920, 0],
                "arrivee": [3120, 0],
                "allege": 0,
                "hauteur": 2160,
            },
        ],
    }
    fichier = client.post("/esquisse/fichier", json=croquis)
    assert fichier.status_code == 200
    assert "maison-obstetar.esquisse.yaml" in fichier.headers["content-disposition"]
    # L'apostrophe est doublee : c'est ainsi qu'un scalaire YAML quote la porte.
    assert "'porte d''entrée'" in fichier.text

    rouvert = client.post("/esquisse/ouvrir", json={"source": fichier.text})
    assert rouvert.status_code == 200
    donnees = rouvert.json()
    assert donnees["nom"] == "Maison Obstetar"
    assert [p["nom"] for p in donnees["pieces"]] == ["séjour", "cuisine"]
    assert donnees["baies"][0]["id"] == "porte d'entrée"
    assert donnees["baies"][0]["depart"] == [1920, 0]


def test_un_fichier_d_esquisse_illisible_est_explique(client: TestClient) -> None:
    reponse = client.post("/esquisse/ouvrir", json={"source": "juste du texte"})
    assert reponse.status_code == 422
    assert "objet" in reponse.json()["erreur"]

    casse = client.post("/esquisse/ouvrir", json={"source": "pieces: []"})
    assert casse.status_code == 422
    assert "pydantic" not in casse.json()["erreur"]


# --- passage de l'esquisse a l'onglet Plan ------------------------------------

ESQUISSE_COMPLETE: dict[str, object] = {
    "pieces": [
        {"nom": "a", "x": 0, "y": 0, "largeur": 4800, "hauteur": 4800},
        {"nom": "b", "x": 4800, "y": 0, "largeur": 3840, "hauteur": 4800},
    ],
    "baies": [
        {
            "id": "porte d'entrée",
            "type": "porte",
            "depart": [1920, 0],
            "arrivee": [3120, 0],
            "allege": 0,
            "hauteur": 2160,
        },
        {
            "id": "F1",
            "type": "fenetre",
            "depart": [8640, 1920],
            "arrivee": [8640, 3360],
            "allege": 960,
            "hauteur": 1200,
        },
        {
            "id": "PF1",
            "type": "porte_fenetre",
            "depart": [0, 1440],
            "arrivee": [0, 3840],
            "allege": 0,
            "hauteur": 2160,
        },
        {
            "id": "P2",
            "type": "porte",
            "depart": [4800, 1920],
            "arrivee": [4800, 2880],
            "allege": 0,
            "hauteur": 2160,
        },
    ],
}


def _brouillon(client: TestClient, esquisse: dict[str, object]) -> str:
    reponse = client.post("/esquisse/plan", json=esquisse)
    assert reponse.status_code == 200, reponse.text
    trouve = re.search(r'href="/\?depuis=([0-9a-f]+)"', reponse.text)
    assert trouve is not None, reponse.text
    return trouve.group(1)


def test_un_plan_complet_propose_de_calepiner_sans_copier_coller(client: TestClient) -> None:
    reponse = client.post("/esquisse/plan", json=ESQUISSE_COMPLETE)
    assert "Plan complet" in reponse.text
    assert "Calepiner ce plan" in reponse.text
    assert "&amp;calepiner=1" in reponse.text


def test_un_plan_incomplet_ne_propose_que_de_l_ouvrir(client: TestClient) -> None:
    """Chainer un plan a completer n'afficherait que ses propres erreurs.

    Une piece de 9,60 m sans la moindre baie : aucun de ses murs n'est tenu.
    """
    reponse = client.post(
        "/esquisse/plan",
        json={"pieces": [{"nom": "a", "x": 0, "y": 0, "largeur": 9600, "hauteur": 9600}]},
    )
    assert "À compléter" in reponse.text
    assert "Calepiner ce plan" not in reponse.text
    assert "Ouvrir dans l'onglet Plan" in reponse.text


def test_le_plan_derive_se_retrouve_dans_l_onglet_plan(client: TestClient) -> None:
    from obqo.model.lecture import depuis_texte

    cle_brouillon = _brouillon(client, ESQUISSE_COMPLETE)
    page = client.get("/", params={"depuis": cle_brouillon})
    assert page.status_code == 200
    source = re.search(r'<textarea id="plan"[^>]*>(.*?)</textarea>', page.text, re.S)
    assert source is not None
    plan = depuis_texte(html.unescape(source.group(1)))
    assert len(plan.ouvertures) == 4, "les baies posees a la souris ont fait le trajet"
    assert 'data-lancer="1"' not in page.text, "sans ordre explicite, on ne lance rien"


def test_le_lien_calepiner_demande_le_lancement_automatique(client: TestClient) -> None:
    cle_brouillon = _brouillon(client, ESQUISSE_COMPLETE)
    page = client.get("/", params={"depuis": cle_brouillon, "calepiner": 1})
    assert 'data-lancer="1"' in page.text


def test_un_brouillon_oublie_le_dit_au_lieu_de_servir_l_exemple(client: TestClient) -> None:
    page = client.get("/", params={"depuis": "0" * 16, "calepiner": 1})
    assert page.status_code == 200
    assert "plus en mémoire" in page.text
    assert 'data-lancer="1"' not in page.text, "rien a lancer : ce n'est pas le plan demande"


def test_le_depot_de_brouillons_oublie_les_plus_anciens() -> None:
    from obqo.web.etude import Brouillons

    brouillons = Brouillons(capacite=2)
    premier = brouillons.deposer("un")
    brouillons.deposer("deux")
    brouillons.deposer("trois")
    assert brouillons.get(premier) is None
    assert brouillons.get(brouillons.deposer("trois")) == "trois"
