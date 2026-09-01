"""Interface web legere : FastAPI, Jinja2, et les SVG deja produits par le coeur.

Le calepinage, la nomenclature, le metre et les dessins viennent tels quels des
modules metier. Cette couche ne fait que router, rendre du HTML et servir des
fichiers : aucune regle constructive n'est reimplementee ici.

Pas de HTMX ni de framework front : l'application n'a que trois interactions
(soumettre un plan, changer de planche, telecharger le dossier). Une trentaine de
lignes de JavaScript suffisent, et evitent d'embarquer une bibliotheque a
maintenir ou de dependre d'un CDN dans un atelier hors ligne.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from briq.bom.sorties import (
    ENTETES_DEBIT,
    ENTETES_METRE,
    ENTETES_NOMENCLATURE,
    ENTETES_PAR_MUR,
    lignes_debit,
    lignes_metre,
    lignes_nomenclature,
    lignes_par_mur,
)
from briq.drawings import dxf, pdf, svg
from briq.drawings.ir import nom_de_fichier
from briq.engine.validation import Gravite
from briq.model.plan import Plan
from briq.web.etude import Depot, EchecDeValidation, Etude

RACINE = Path(__file__).parent
EXEMPLE = RACINE.parents[2] / "exemples" / "maison.json"

app = FastAPI(title="BRIQ — calepinage", docs_url="/api")
app.mount("/statique", StaticFiles(directory=RACINE / "statique"), name="statique")
gabarits = Jinja2Templates(directory=RACINE / "templates")
depot = Depot()


def plan_d_exemple() -> str:
    if EXEMPLE.exists():
        return EXEMPLE.read_text(encoding="utf-8")
    return json.dumps(
        {
            "hauteur_sous_chainage": 2640,
            "contour": {
                "trace": {
                    "segments": [
                        {"direction": "est", "longueur": 5760},
                        {"direction": "nord", "longueur": 4800},
                        {"direction": "ouest", "longueur": 5760},
                        {"direction": "sud", "longueur": 4800},
                    ]
                }
            },
        },
        indent=2,
    )


def _etude_ou_404(cle: str) -> Etude:
    etude = depot.get(cle)
    if etude is None:
        raise HTTPException(status_code=404, detail="etude inconnue ou expiree")
    return etude


@app.get("/", response_class=HTMLResponse)
def accueil(requete: Request) -> Any:
    return gabarits.TemplateResponse(
        requete, "index.html", {"plan": plan_d_exemple(), "titre": "BRIQ — calepinage"}
    )


@app.post("/etude", response_class=HTMLResponse)
def etudier(requete: Request, corps: Annotated[dict[str, Any], Body()]) -> Any:
    """Calepine le plan soumis et renvoie le fragment de resultat."""
    source = str(corps.get("plan", ""))
    exact = bool(corps.get("exact", False))
    try:
        etude = depot.etudier(source, exact)
    except EchecDeValidation as echec:
        return gabarits.TemplateResponse(
            requete,
            "fragments/constats.html",
            {"constats": echec.rapport.constats, "bloquant": True},
            status_code=422,
        )
    except ValueError as erreur:  # schema invalide, JSON casse
        return gabarits.TemplateResponse(
            requete,
            "fragments/schema-invalide.html",
            {"message": str(erreur)},
            status_code=422,
        )
    return gabarits.TemplateResponse(
        requete, "fragments/etude.html", _contexte(etude) | {"request": requete}
    )


def _contexte(etude: Etude) -> dict[str, Any]:
    metre = etude.metre
    lisses = metre.barres_pleines_de_lisse * metre.longueur_barre_madrier
    briques = etude.nomenclature.par_categorie("brique")
    return {
        "etude": etude,
        "briques": briques,
        "total_briques": sum(b.quantite for b in briques),
        "stocks": [
            ("carrelet 80x80", metre.lineaire_carrelet, metre.barres_carrelet()),
            ("madrier 80x240", metre.lineaire_madrier + lisses, metre.barres_madrier()),
            ("hetre rond 20", metre.lineaire_hetre, 0),
        ],
        "debits": [d for d in (metre.debit_carrelet, metre.debit_madrier) if d and d.barres],
        "masse": metre.masse_kg(etude.plan.parametres.masse_volumique_epicea),
        "constats": etude.rapport.constats,
        "planches": list(enumerate(etude.planches)),
    }


# Starlette teste les routes dans leur ordre de declaration : la variante
# .svg doit passer avant, sinon `{index}` capture « 0.svg » et la route HTML
# repond 422 au lieu de servir le fichier.
@app.get("/etude/{cle}/planche/{index}.svg")
def planche_svg(cle: str, index: int) -> Response:
    etude = _etude_ou_404(cle)
    if not 0 <= index < len(etude.planches):
        raise HTTPException(status_code=404, detail="planche inconnue")
    dessin = etude.planches[index]
    return Response(
        svg.rendre(dessin),
        media_type="image/svg+xml",
        headers={
            "Content-Disposition": (
                f'inline; filename="{index:02d}-{nom_de_fichier(dessin.titre)}.svg"'
            )
        },
    )


@app.get("/etude/{cle}/planche/{index}", response_class=HTMLResponse)
def planche(requete: Request, cle: str, index: int) -> Any:
    etude = _etude_ou_404(cle)
    if not 0 <= index < len(etude.planches):
        raise HTTPException(status_code=404, detail="planche inconnue")
    dessin = etude.planches[index]
    return gabarits.TemplateResponse(
        requete,
        "fragments/planche.html",
        {
            "dessin": dessin,
            "svg": svg.rendre(dessin, pour_ecran=True),
            "cle": cle,
            "index": index,
        },
    )


def _csv(entetes: tuple[str, ...], lignes: list[Any]) -> str:
    import csv

    flux = io.StringIO()
    graveur = csv.writer(flux, delimiter=";")
    graveur.writerow(entetes)
    graveur.writerows(lignes)
    return flux.getvalue()


@app.get("/etude/{cle}/dossier.zip")
def dossier_zip(cle: str) -> Response:
    """Le dossier complet, tel que l'ecrirait `briq calepiner`."""
    etude = _etude_ou_404(cle)
    from briq.cli import serialiser

    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "calepinage.json",
            json.dumps(serialiser(etude.calepinage), indent=2, ensure_ascii=False) + "\n",
        )
        for nom, entetes, lignes in (
            ("nomenclature.csv", ENTETES_NOMENCLATURE, lignes_nomenclature(etude.nomenclature)),
            ("nomenclature-par-mur.csv", ENTETES_PAR_MUR, lignes_par_mur(etude.nomenclature)),
            ("metre.csv", ENTETES_METRE, lignes_metre(etude.metre)),
            ("debit.csv", ENTETES_DEBIT, lignes_debit(etude.metre)),
        ):
            archive.writestr(nom, _csv(entetes, lignes))
        for index, dessin in enumerate(etude.planches):
            archive.writestr(
                f"plans/{index:02d}-{nom_de_fichier(dessin.titre)}.svg", svg.rendre(dessin)
            )
        papier = io.BytesIO()
        chemin = Path("/tmp") / f"briq-{etude.cle}.pdf"
        pdf.ecrire(etude.planches, chemin)
        papier.write(chemin.read_bytes())
        chemin.unlink(missing_ok=True)
        archive.writestr("dossier.pdf", papier.getvalue())

    return Response(
        tampon.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="dossier-briq.zip"'},
    )


@app.get("/schema.json")
def schema() -> JSONResponse:
    document = Plan.model_json_schema(by_alias=True)
    document["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    document["title"] = "Plan BRIQ, version 1"
    return JSONResponse(document)


# Le gabarit a besoin de reconnaitre la gravite d'un constat pour le colorer.
gabarits.env.globals["Gravite"] = Gravite
gabarits.env.globals["dxf_disponible"] = dxf is not None
