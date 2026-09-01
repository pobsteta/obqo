"""Interface en ligne de commande.

Typer pour les sous-commandes et Rich pour l'affichage. Ces deux dependances ne
vivent **que dans ce module** : `engine`, `rules` et `bom` restent importables
avec la seule bibliotheque standard, et le rapport ecrit sur disque est rendu par
`bom.sorties`, sans couleur ni dependance.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import StrEnum
from io import StringIO
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from briq.bom.debit import GloutonDecroissant, PlanDeDebit, Solveur, solveur_par_defaut
from briq.bom.metre import Metre, chiffrer, metrer
from briq.bom.nomenclature import Nomenclature, nomenclaturer
from briq.bom.sorties import (
    ENTETES_DEBIT,
    ENTETES_METRE,
    ENTETES_NOMENCLATURE,
    ENTETES_PAR_MUR,
    ecrire_csv,
    lignes_debit,
    lignes_metre,
    lignes_nomenclature,
    lignes_par_mur,
    synthese,
)
from briq.drawings import dxf, pdf, svg
from briq.drawings.ir import nom_de_fichier
from briq.drawings.planches import dossier as planches_du_dossier
from briq.engine.calepinage import calepiner as calepiner_le_plan
from briq.engine.validation import Gravite, Rapport
from briq.model.plan import Plan
from briq.model.systeme import Calepinage

app = typer.Typer(
    help="Calepinage, nomenclature et metre du systeme constructif BRIQ.",
    no_args_is_help=True,
    add_completion=True,
)
console = Console()
erreurs = Console(stderr=True)

COULEURS = {
    Gravite.ERREUR: "bold red",
    Gravite.AVERTISSEMENT: "yellow",
    Gravite.HYPOTHESE: "cyan",
}


class Format(StrEnum):
    SVG = "svg"
    PDF = "pdf"
    DXF = "dxf"
    TROIS_D = "3d"


Chemin = Annotated[Path, typer.Argument(help="Fichier de plan JSON ou YAML.", exists=True)]


# --- aides --------------------------------------------------------------------


def charger(chemin: Path) -> Plan:
    """Lit et valide un plan. Les erreurs de schema remontent telles quelles."""
    return Plan.model_validate(json.loads(chemin.read_text(encoding="utf-8")))


def _brut(objet: Any) -> Any:
    if is_dataclass(objet) and not isinstance(objet, type):
        return asdict(objet)
    raise TypeError(type(objet))


def afficher_rapport(rapport: Rapport) -> None:
    """Rapport de validation, une couleur par gravite."""
    if not rapport.constats:
        console.print("[green]Plan valide, aucun constat.[/green]")
        return
    for gravite in (Gravite.ERREUR, Gravite.AVERTISSEMENT, Gravite.HYPOTHESE):
        lot = [c for c in rapport.constats if c.gravite is gravite]
        if not lot:
            continue
        couleur = COULEURS[gravite]
        console.print(f"\n[{couleur}]{gravite.value.upper()}S ({len(lot)})[/{couleur}]")
        for constat in lot:
            console.print(
                f"  [{couleur}]{constat.code}[/{couleur}] [dim]{constat.ou}[/dim] {constat.message}"
            )


def rapport_texte(rapport: Rapport) -> str:
    """Meme rapport, sans couleur, pour le fichier ecrit sur disque."""
    flux = StringIO()
    if not rapport.constats:
        print("Plan valide, aucun constat.", file=flux)
    for gravite in (Gravite.ERREUR, Gravite.AVERTISSEMENT, Gravite.HYPOTHESE):
        lot = [c for c in rapport.constats if c.gravite is gravite]
        if lot:
            print(f"\n{gravite.value.upper()}S ({len(lot)})", file=flux)
            for constat in lot:
                print(f"  {constat.code} — {constat.ou} : {constat.message}", file=flux)
    return flux.getvalue()


def _calepiner(chemin: Path) -> tuple[Plan, Calepinage, Rapport]:
    """Charge, calepine et s'arrete proprement si le plan porte des erreurs."""
    plan = charger(chemin)
    calepinage, rapport = calepiner_le_plan(plan)
    afficher_rapport(rapport)
    if calepinage is None:
        erreurs.print("\n[bold red]Calepinage impossible[/bold red] : corriger les erreurs.")
        raise typer.Exit(code=1)
    return plan, calepinage, rapport


def _solveur(glouton: bool, secondes: float) -> Solveur:
    return GloutonDecroissant() if glouton else solveur_par_defaut(secondes)


def serialiser(calepinage: Calepinage) -> dict[str, Any]:
    """Modele de briques posees, trie pour etre stable d'une execution a l'autre."""
    return {
        "nom": calepinage.nom,
        "murs": [
            {
                "id": mur.id,
                "depart": list(mur.depart),
                "arrivee": list(mur.arrivee),
                "longueur_hors_tout": mur.longueur_hors_tout,
                "interieur": mur.interieur,
                "rangs": [
                    {
                        "indice": rang.indice,
                        "debut": rang.debut,
                        "fin": rang.fin,
                        "briques": [
                            {
                                "id": b.id,
                                "u": b.u,
                                "ref": b.ref.value,
                                "longueur": b.longueur,
                                "about_debut_ferme": b.about_debut_ferme,
                                "about_fin_ferme": b.about_fin_ferme,
                                "angle": b.angle,
                            }
                            for b in rang.briques
                        ],
                        "joints": rang.joints,
                        "quincaillerie": [asdict(q) for q in rang.quincaillerie],
                    }
                    for rang in mur.rangs
                ],
                "elements": [asdict(e) for e in mur.elements],
            }
            for mur in calepinage.murs
        ],
        "totaux": {
            "briques": {ref.value: n for ref, n in sorted(calepinage.compte_briques().items())},
            "elements": dict(sorted(calepinage.compte_elements().items())),
            "quincaillerie_chantier": dict(sorted(calepinage.compte_quincaillerie().items())),
        },
        "avertissements": calepinage.avertissements,
        "hypotheses": calepinage.hypotheses,
    }


def dessiner(calepinage: Calepinage, plan: Plan, dossier: Path, formats: list[Format]) -> list[str]:
    """Produit les planches dans les formats demandes. Retourne les intitules."""
    if not formats:
        return []
    planches = planches_du_dossier(calepinage, plan)
    ecrits: list[str] = []

    if Format.SVG in formats:
        cible = dossier / "plans"
        cible.mkdir(parents=True, exist_ok=True)
        for index, planche in enumerate(planches):
            svg.ecrire(planche, cible / f"{index:02d}-{nom_de_fichier(planche.titre)}.svg")
        ecrits.append(f"plans/*.svg ({len(planches)} planches)")
    if Format.PDF in formats:
        pdf.ecrire(planches, dossier / "dossier.pdf")
        ecrits.append(f"dossier.pdf ({len(planches)} pages A3)")
    if Format.DXF in formats:
        cible = dossier / "dxf"
        cible.mkdir(parents=True, exist_ok=True)
        dxf.ecrire(planches, cible)
        ecrits.append(f"dxf/*.dxf ({len(planches)} fichiers)")
    if Format.TROIS_D in formats:
        from briq.drawings import volume

        cible = dossier / "3d"
        cible.mkdir(parents=True, exist_ok=True)
        volume.maison(calepinage, cible / "maison.glb")
        volume.colonne_d_angle(calepinage, cible / "colonne-d-angle.glb")
        ecrits.append("3d/maison.glb, 3d/colonne-d-angle.glb")
    return ecrits


# --- tableaux Rich ------------------------------------------------------------


def _table_briques(nomenclature: Nomenclature) -> Table:
    lignes = nomenclature.par_categorie("brique")
    table = Table(
        title=f"Briques — {sum(x.quantite for x in lignes)} au total",
        title_justify="left",
        header_style="bold",
    )
    table.add_column("reference", style="cyan")
    table.add_column("designation")
    table.add_column("quantite", justify="right", style="bold")
    table.add_column("localisation", style="dim")
    for ligne in lignes:
        table.add_row(ligne.ref, ligne.designation, str(ligne.quantite), ligne.localisation)
    return table


def _table_debit(plan_de_debit: PlanDeDebit) -> Table:
    etat = "optimum prouve" if plan_de_debit.optimal else "solution approchee"
    table = Table(
        title=(
            f"Debit {plan_de_debit.stock.designation} — "
            f"{plan_de_debit.nombre_de_barres} barres de "
            f"{plan_de_debit.stock.longueur_barre} mm, "
            f"chute {100 * plan_de_debit.taux_de_chute:.2f} %, "
            f"{plan_de_debit.surproduction / 1000:.1f} m de rechange "
            f"({plan_de_debit.solveur}, {etat})"
        ),
        title_justify="left",
        header_style="bold",
    )
    table.add_column("patron de decoupe")
    table.add_column("barres", justify="right", style="bold")
    table.add_column("chute (mm)", justify="right")
    for barre in plan_de_debit.barres:
        chute = barre.patron.chute(plan_de_debit.stock)
        style = "green" if chute >= plan_de_debit.stock.chute_minimale_reutilisable else None
        table.add_row(str(barre.patron), str(barre.repetitions), str(chute), style=style)
    return table


def _table_metre(metre: Metre) -> Table:
    table = Table(title="Metre matiere", title_justify="left", header_style="bold")
    table.add_column("stock")
    table.add_column("lineaire (m)", justify="right")
    table.add_column("barres", justify="right")
    lisses = metre.barres_pleines_de_lisse * metre.longueur_barre_madrier
    for nom, millimetres, barres in (
        ("carrelet 80x80", metre.lineaire_carrelet, metre.barres_carrelet()),
        ("madrier 80x240", metre.lineaire_madrier + lisses, metre.barres_madrier()),
        ("hetre rond 20", metre.lineaire_hetre, 0),
    ):
        table.add_row(nom, f"{millimetres / 1000:.1f}", str(barres) if barres else "—")
    return table


# --- commandes ----------------------------------------------------------------


@app.command()
def valider(plan: Chemin) -> None:
    """Controler un plan sans rien produire."""
    _, rapport = calepiner_le_plan(charger(plan))
    afficher_rapport(rapport)
    raise typer.Exit(code=1 if rapport.erreurs else 0)


@app.command()
def calepiner(
    plan: Chemin,
    sortie: Annotated[Path, typer.Option("-o", "--sortie", help="Dossier de sortie.")] = Path(
        "sortie"
    ),
    formats: Annotated[
        list[Format] | None,
        typer.Option("--format", "-f", help="Format de plans ; repeter pour en cumuler."),
    ] = None,
    glouton: Annotated[
        bool, typer.Option("--glouton", help="Solveur de debit sans dependance.")
    ] = False,
    secondes: Annotated[float, typer.Option(help="Temps par phase du solveur exact.")] = 20.0,
) -> None:
    """Calepiner un plan et ecrire le dossier complet."""
    plan_valide, calepinage, rapport = _calepiner(plan)
    demandes = list(formats) if formats is not None else list(Format)

    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / "calepinage.json").write_text(
        json.dumps(serialiser(calepinage), indent=2, ensure_ascii=False, default=_brut) + "\n",
        encoding="utf-8",
    )
    nomenclature = nomenclaturer(calepinage)
    ecrire_csv(sortie / "nomenclature.csv", ENTETES_NOMENCLATURE, lignes_nomenclature(nomenclature))
    ecrire_csv(sortie / "nomenclature-par-mur.csv", ENTETES_PAR_MUR, lignes_par_mur(nomenclature))

    metre = metrer(calepinage, nomenclature, plan_valide.parametres, _solveur(glouton, secondes))
    ecrire_csv(sortie / "metre.csv", ENTETES_METRE, lignes_metre(metre))
    ecrire_csv(sortie / "debit.csv", ENTETES_DEBIT, lignes_debit(metre))

    ecrits = dessiner(calepinage, plan_valide, sortie, demandes)

    chiffrage = chiffrer(metre, plan_valide.parametres)
    (sortie / "rapport.txt").write_text(
        rapport_texte(rapport)
        + synthese(
            calepinage,
            nomenclature,
            metre,
            chiffrage,
            plan_valide.parametres.masse_volumique_epicea,
        ),
        encoding="utf-8",
    )

    console.print()
    console.print(_table_briques(nomenclature))
    console.print()
    console.print(_table_metre(metre))
    for plan_de_debit in (metre.debit_carrelet, metre.debit_madrier):
        if plan_de_debit and plan_de_debit.barres:
            console.print()
            console.print(_table_debit(plan_de_debit))
    masse = metre.masse_kg(plan_valide.parametres.masse_volumique_epicea)
    console.print(f"\nMasse d'ossature epicea : [bold]{masse} kg[/bold]")
    if chiffrage.total:
        console.print(f"Chiffrage : [bold]{chiffrage.total}[/bold]")

    fichiers = [
        "calepinage.json",
        "nomenclature.csv",
        "nomenclature-par-mur.csv",
        "metre.csv",
        "debit.csv",
        "rapport.txt",
        *ecrits,
    ]
    console.print(f"\n[green]Ecrit dans {sortie}/[/green] : " + ", ".join(fichiers))


@app.command()
def nomenclature(plan: Chemin) -> None:
    """Afficher la nomenclature sans rien ecrire."""
    _, calepinage, _ = _calepiner(plan)
    complete = nomenclaturer(calepinage)
    console.print()
    console.print(_table_briques(complete))
    table = Table(title="Pieces et chevilles", title_justify="left", header_style="bold")
    table.add_column("reference", style="cyan")
    table.add_column("designation")
    table.add_column("quantite", justify="right", style="bold")
    table.add_column("detail", style="dim")
    for ligne in complete.lignes:
        if ligne.categorie != "brique":
            table.add_row(ligne.ref, ligne.designation, str(ligne.quantite), ligne.detail)
    console.print()
    console.print(table)


@app.command()
def debit(
    plan: Chemin,
    glouton: Annotated[bool, typer.Option("--glouton")] = False,
    secondes: Annotated[float, typer.Option()] = 20.0,
) -> None:
    """Afficher le plan de debit optimise sans rien ecrire."""
    plan_valide, calepinage, _ = _calepiner(plan)
    metre = metrer(
        calepinage,
        nomenclaturer(calepinage),
        plan_valide.parametres,
        _solveur(glouton, secondes),
    )
    console.print()
    console.print(_table_metre(metre))
    for plan_de_debit in (metre.debit_carrelet, metre.debit_madrier):
        if plan_de_debit and plan_de_debit.barres:
            console.print()
            console.print(_table_debit(plan_de_debit))


@app.command()
def web(
    hote: Annotated[str, typer.Option(help="Adresse d'ecoute.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port d'ecoute.")] = 8000,
    rechargement: Annotated[
        bool, typer.Option("--rechargement", help="Recharger a chaud pendant le developpement.")
    ] = False,
) -> None:
    """Lancer l'interface web (extra « web » requis)."""
    try:
        import uvicorn
    except ImportError:
        erreurs.print(
            "[bold red]Interface web indisponible[/bold red] : "
            "installer l'extra avec [bold]uv sync --extra web[/bold]."
        )
        raise typer.Exit(code=1) from None
    console.print(
        f"[green]BRIQ[/green] sur [bold]http://{hote}:{port}[/bold] — Ctrl+C pour quitter"
    )
    uvicorn.run("briq.web.app:app", host=hote, port=port, reload=rechargement, log_level="warning")


@app.command()
def schema(
    sortie: Annotated[Path, typer.Option("-o", "--sortie")] = Path("schemas"),
) -> None:
    """Exporter le schema JSON du format de plan."""
    sortie.mkdir(parents=True, exist_ok=True)
    cible = sortie / "briq-plan-v1.schema.json"
    document = Plan.model_json_schema(by_alias=True)
    document["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    document["title"] = "Plan BRIQ, version 1"
    cible.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    console.print(f"[green]Schema ecrit dans {cible}[/green]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
