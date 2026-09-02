"""Interface web legere : FastAPI, Jinja2, et les SVG deja produits par le coeur.

Le calepinage, la nomenclature, le metre et les dessins viennent tels quels des
modules metier. Cette couche ne fait que router, rendre du HTML et servir des
fichiers : aucune regle constructive n'est reimplementee ici.

Pas de HTMX ni de framework front : l'application n'a que trois interactions
(soumettre un plan, changer de planche, telecharger le dossier). Une trentaine de
lignes de JavaScript suffisent, et evitent d'embarquer une bibliotheque a
maintenir ou de dependre d'un CDN dans un atelier hors ligne.

Deux pages, dans l'ordre du travail : « / » dessine l'esquisse, « /plan »
calepine. La seconde s'atteint aussi depuis la premiere, chargee du plan derive.
"""

from __future__ import annotations

import io
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from obqo.bom.sorties import (
    ENTETES_DEBIT,
    ENTETES_METRE,
    ENTETES_NOMENCLATURE,
    ENTETES_PAR_MUR,
    lignes_debit,
    lignes_metre,
    lignes_nomenclature,
    lignes_par_mur,
)
from obqo.drawings import svg
from obqo.drawings.ir import nom_de_fichier
from obqo.drawings.mise_en_page import Feuille
from obqo.drawings.planches import apercu
from obqo.engine.calepinage import calepiner
from obqo.engine.esquisse import PAS_RECOMMANDE, caler, murs_du_plan, vers_plan
from obqo.engine.validation import Gravite
from obqo.model.ecriture import esquisse_en_yaml, texte
from obqo.model.esquisse import Baie, Esquisse, Piece
from obqo.model.lecture import esquisse_depuis_texte
from obqo.model.plan import Plan
from obqo.web.etude import Brouillons, Depot, EchecDeValidation, Etude

RACINE = Path(__file__).parent
EXEMPLE = RACINE.parents[2] / "exemples" / "maison.json"

app = FastAPI(title="obqo — calepinage", docs_url="/api")
app.mount("/statique", StaticFiles(directory=RACINE / "statique"), name="statique")
gabarits = Jinja2Templates(directory=RACINE / "templates")
depot = Depot()
brouillons = Brouillons()

FEUILLE_APERCU = Feuille(largeur=240.0, hauteur=170.0, marge=6.0, cartouche=18.0, legende=0.0)
"""Feuille compacte pour l'apercu a l'ecran : le dessin remplit son cadre au lieu
de flotter au milieu d'un A3 destine a l'impression."""


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


@app.get("/plan", response_class=HTMLResponse)
def page_de_plan(requete: Request, depuis: str = "", calepiner: int = 0) -> Any:
    """La page de calepinage, eventuellement chargee d'un plan derive d'esquisse.

    `depuis` porte la cle d'un brouillon depose par `/esquisse/plan` : c'est ce
    qui evite le copier-coller entre les deux onglets.
    """
    avis = ""
    source = plan_d_exemple()
    if depuis:
        brouillon = brouillons.get(depuis)
        if brouillon is None:
            avis = (
                "Ce plan dérivé n'est plus en mémoire — le serveur n'en garde "
                "que les huit derniers. Repassez par l'esquisse."
            )
        else:
            source = brouillon
    return gabarits.TemplateResponse(
        requete,
        "index.html",
        {
            "plan": source,
            "titre": "obqo — calepinage",
            "avis": avis,
            "lancer": bool(calepiner) and not avis,
        },
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
    """Le dossier complet, tel que l'ecrirait `obqo calepiner`."""
    etude = _etude_ou_404(cle)
    from obqo.cli import serialiser

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
        try:
            from obqo.drawings import pdf
        except ImportError:  # extra « dessins » absent : le zip garde les SVG
            pass
        else:
            chemin = Path(tempfile.gettempdir()) / f"obqo-{etude.cle}.pdf"
            pdf.ecrire(etude.planches, chemin)
            archive.writestr("dossier.pdf", chemin.read_bytes())
            chemin.unlink(missing_ok=True)

    return Response(
        tampon.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="dossier-obqo.zip"'},
    )


# --- module d'esquisse --------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def accueil(requete: Request) -> Any:
    """L'editeur d'esquisse est la page d'accueil : on dessine, puis on calepine.

    C'est l'ordre du travail reel. Arriver sur un plan JSON deja rempli suppose
    qu'on en a un ; arriver sur une feuille a dessiner ne suppose rien, et le
    plan derive mene ensuite a la page de calepinage tout seul.
    """
    return gabarits.TemplateResponse(
        requete, "esquisse.html", {"titre": "obqo — esquisse", "pas": PAS_RECOMMANDE}
    )


@app.get("/esquisse", include_in_schema=False)
def esquisse_deplacee() -> RedirectResponse:
    """L'ancienne adresse de l'editeur : un signet ne doit pas tomber sur un 404."""
    return RedirectResponse("/", status_code=308)


def _esquisse_depuis(corps: dict[str, Any]) -> Esquisse:
    """Construit l'esquisse, en traduisant les erreurs de schema en francais.

    Le message brut de Pydantic cite le type d'entree et une URL de
    documentation : illisible dans une barre d'etat.
    """
    try:
        return Esquisse(
            nom=str(corps.get("nom") or "esquisse"),
            hauteur_sous_chainage=int(corps.get("hauteur_sous_chainage") or 2640),
            pieces=[Piece(**p) for p in corps.get("pieces", [])],
            baies=[Baie(**b) for b in corps.get("baies", [])],
        )
    except ValidationError as erreur:
        details = "; ".join(
            str(d.get("msg", "")).removeprefix("Value error, ") for d in erreur.errors()
        )
        raise ValueError(details or "esquisse invalide") from erreur


@app.post("/esquisse/caler")
def caler_esquisse(corps: Annotated[dict[str, Any], Body()]) -> JSONResponse:
    """Recale le dessin sur le pas demande et dit ce qui a bouge."""
    try:
        esquisse = _esquisse_depuis(corps)
    except ValueError as erreur:
        return JSONResponse({"erreur": str(erreur)}, status_code=422)
    pas = int(corps.get("pas") or PAS_RECOMMANDE)
    calee, ajustements = caler(esquisse, pas)
    return JSONResponse(
        {
            "pieces": [p.model_dump() for p in calee.pieces],
            "ajustements": [str(a) for a in ajustements],
        }
    )


@app.post("/esquisse/murs")
def murs_de_l_esquisse(corps: Annotated[dict[str, Any], Body()]) -> JSONResponse:
    """Murs deduits du dessin, pour que l'editeur y accroche les baies.

    La geometrie reste cote serveur : l'editeur ne redevine pas ou tombent les
    murs, il demande. Une seule source de verite pour les regles.
    """
    try:
        esquisse = _esquisse_depuis(corps)
    except ValueError as erreur:
        return JSONResponse({"erreur": str(erreur), "murs": []}, status_code=422)
    plan, rapport = vers_plan(esquisse)
    if plan is None:
        premiere = rapport.erreurs[0]
        return JSONResponse(
            {"erreur": f"{premiere.code} — {premiere.message}", "murs": []}, status_code=422
        )
    return JSONResponse(
        {
            "murs": [
                {
                    "id": m.id,
                    "depart": list(m.depart),
                    "arrivee": list(m.arrivee),
                    "interieur": m.interieur,
                    "longueur": m.longueur,
                }
                for m in murs_du_plan(plan)
            ]
        }
    )


@app.post("/esquisse/fichier")
def enregistrer_esquisse(corps: Annotated[dict[str, Any], Body()]) -> Response:
    """Rend l'esquisse en YAML, a garder et a rouvrir plus tard."""
    try:
        esquisse = _esquisse_depuis(corps)
    except ValueError as erreur:
        return JSONResponse({"erreur": str(erreur)}, status_code=422)
    nom = nom_de_fichier(esquisse.nom) or "esquisse"
    return Response(
        esquisse_en_yaml(esquisse),
        media_type="application/yaml",
        headers={"Content-Disposition": f'attachment; filename="{nom}.esquisse.yaml"'},
    )


@app.post("/esquisse/ouvrir")
def ouvrir_esquisse(corps: Annotated[dict[str, Any], Body()]) -> JSONResponse:
    """Relit une esquisse enregistree et la rend a l'editeur."""
    try:
        esquisse = esquisse_depuis_texte(str(corps.get("source", "")))
    except ValidationError as erreur:
        details = "; ".join(
            str(d.get("msg", "")).removeprefix("Value error, ") for d in erreur.errors()
        )
        return JSONResponse({"erreur": details or "esquisse invalide"}, status_code=422)
    except ValueError as erreur:
        return JSONResponse({"erreur": str(erreur)}, status_code=422)
    return JSONResponse(
        {
            "nom": esquisse.nom,
            "hauteur_sous_chainage": esquisse.hauteur_sous_chainage,
            "pieces": [p.model_dump() for p in esquisse.pieces],
            "baies": [
                {**b.model_dump(), "depart": list(b.depart), "arrivee": list(b.arrivee)}
                for b in esquisse.baies
            ],
        }
    )


@app.post("/esquisse/plan", response_class=HTMLResponse)
def plan_depuis_esquisse(requete: Request, corps: Annotated[dict[str, Any], Body()]) -> Any:
    """Convertit le dessin en plan obqo et rend le fragment de resultat."""
    try:
        esquisse = _esquisse_depuis(corps)
    except ValueError as erreur:
        return gabarits.TemplateResponse(
            requete, "fragments/schema-invalide.html", {"message": str(erreur)}, status_code=422
        )
    calee, ajustements = caler(esquisse, int(corps.get("pas") or PAS_RECOMMANDE))
    plan, rapport = vers_plan(calee)
    if plan is None:
        return gabarits.TemplateResponse(
            requete,
            "fragments/constats.html",
            {"constats": rapport.constats, "bloquant": True},
            status_code=422,
        )

    _, controle = calepiner(plan)
    source = _en_yaml(plan, calee)
    return gabarits.TemplateResponse(
        requete,
        "fragments/esquisse-resultat.html",
        {
            "ajustements": [str(a) for a in ajustements],
            "constats": rapport.constats,
            "controle": controle.constats,
            "pret": not controle.erreurs,
            "source": source,
            "brouillon": brouillons.deposer(source),
            "apercu": svg.rendre(apercu(plan), FEUILLE_APERCU, pour_ecran=True),
        },
    )


def _en_yaml(plan: Plan, esquisse: Esquisse) -> str:
    """Plan derive, ecrit en YAML commente et pret a etre complete."""
    sommets = plan.contour.sommets()
    lignes = [
        f"# Plan derive de l'esquisse « {esquisse.nom} ».",
        "# Les cotes des baies portent sur la tremie, pas sur le passage libre :",
        "# les jambages en retirent 160 mm, 320 au-dela de 1800.",
        "# Voir docs/saisir-un-plan.md.",
        f"nom: {texte(plan.nom)}",
        f"hauteur_sous_chainage: {plan.hauteur_sous_chainage}",
        "contour:",
        "  points:",
    ]
    for i, (x, y) in enumerate(sommets):
        suivant = sommets[(i + 1) % len(sommets)]
        longueur = abs(suivant[0] - x) + abs(suivant[1] - y)
        lignes.append(f"    - [{x}, {y}]      # M{i + 1} — {longueur} mm")
    if plan.refends:
        lignes.append("refends:")
        for refend in plan.refends:
            lignes.append(
                f"  - {{id: {refend.id}, depart: [{refend.depart[0]}, {refend.depart[1]}], "
                f"arrivee: [{refend.arrivee[0]}, {refend.arrivee[1]}]}}"
            )
    if plan.ouvertures:
        lignes.append("ouvertures:")
        for o in plan.ouvertures:
            passage = o.largeur - (320 if o.largeur > 1800 else 160)
            allege = f", allege: {o.allege}" if o.allege else ""
            lignes.append(
                f"  - {{id: {texte(o.id)}, mur: {o.mur}, type: {o.type}, "
                f"position: {o.position}, largeur: {o.largeur}{allege}, "
                f"hauteur: {o.hauteur}}}   # passage libre {passage} mm"
            )
    else:
        lignes.append("ouvertures: []   # a completer : au moins une par mur de plus de 6 m")
    return "\n".join(lignes) + "\n"


@app.get("/schema.json")
def schema() -> JSONResponse:
    document = Plan.model_json_schema(by_alias=True)
    document["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    document["title"] = "Plan obqo, version 1"
    return JSONResponse(document)


# Le gabarit a besoin de reconnaitre la gravite d'un constat pour le colorer.
gabarits.env.globals["Gravite"] = Gravite
