"""Interface en ligne de commande (jalon 1 : valider, calepiner, schema)."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from briq.bom.debit import GloutonDecroissant, solveur_par_defaut
from briq.bom.metre import chiffrer, metrer
from briq.bom.nomenclature import nomenclaturer
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
from briq.engine.calepinage import calepiner
from briq.engine.validation import Constat, Gravite, Rapport
from briq.model.plan import Plan
from briq.model.systeme import Calepinage


def charger(chemin: Path) -> Plan:
    return Plan.model_validate(json.loads(chemin.read_text(encoding="utf-8")))


def _brut(objet: Any) -> Any:
    if is_dataclass(objet) and not isinstance(objet, type):
        return asdict(objet)
    raise TypeError(type(objet))


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


def afficher_rapport(rapport: Rapport, sortie: Any = sys.stdout) -> None:
    if not rapport.constats:
        print("Plan valide, aucun constat.", file=sortie)
        return
    ordre = (Gravite.ERREUR, Gravite.AVERTISSEMENT, Gravite.HYPOTHESE)
    for gravite in ordre:
        lot: list[Constat] = [c for c in rapport.constats if c.gravite is gravite]
        if lot:
            print(f"\n{gravite.value.upper()}S ({len(lot)})", file=sortie)
            for c in lot:
                print(f"  {c.code} — {c.ou} : {c.message}", file=sortie)


def cmd_valider(args: argparse.Namespace) -> int:
    _, rapport = calepiner(charger(args.plan))
    afficher_rapport(rapport)
    return 1 if rapport.erreurs else 0


def cmd_calepiner(args: argparse.Namespace) -> int:
    plan = charger(args.plan)
    calepinage, rapport = calepiner(plan)
    afficher_rapport(rapport)
    if calepinage is None:
        print("\nCalepinage impossible : corriger les erreurs ci-dessus.", file=sys.stderr)
        return 1

    dossier: Path = args.sortie
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "calepinage.json").write_text(
        json.dumps(serialiser(calepinage), indent=2, ensure_ascii=False, default=_brut) + "\n",
        encoding="utf-8",
    )

    nomenclature = nomenclaturer(calepinage)
    ecrire_csv(
        dossier / "nomenclature.csv", ENTETES_NOMENCLATURE, lignes_nomenclature(nomenclature)
    )
    ecrire_csv(dossier / "nomenclature-par-mur.csv", ENTETES_PAR_MUR, lignes_par_mur(nomenclature))

    solveur = GloutonDecroissant() if args.glouton else solveur_par_defaut(args.secondes)
    metre = metrer(calepinage, nomenclature, plan.parametres, solveur)
    ecrire_csv(dossier / "metre.csv", ENTETES_METRE, lignes_metre(metre))
    ecrire_csv(dossier / "debit.csv", ENTETES_DEBIT, lignes_debit(metre))

    ecrits = _dessiner(calepinage, plan, dossier, args.formats)

    chiffrage = chiffrer(metre, plan.parametres)
    rendu = synthese(
        calepinage, nomenclature, metre, chiffrage, plan.parametres.masse_volumique_epicea
    )
    print(rendu)
    (dossier / "rapport.txt").write_text(_rapport_texte(rapport) + rendu, encoding="utf-8")
    fichiers = [
        "calepinage.json",
        "nomenclature.csv",
        "nomenclature-par-mur.csv",
        "metre.csv",
        "debit.csv",
        "rapport.txt",
        *ecrits,
    ]
    print(f"Ecrit dans {dossier}/ : " + ", ".join(fichiers))
    return 0


FORMATS = ("svg", "pdf", "dxf", "3d")


def _dessiner(calepinage: Calepinage, plan: Plan, dossier: Path, formats: str) -> list[str]:
    """Produit les planches dans les formats demandes. Retourne les intitules."""
    demandes = [f.strip() for f in formats.split(",") if f.strip()]
    if not demandes:
        return []
    planches = planches_du_dossier(calepinage, plan)
    ecrits: list[str] = []

    if "svg" in demandes:
        cible = dossier / "plans"
        cible.mkdir(parents=True, exist_ok=True)
        for i, planche in enumerate(planches):
            svg.ecrire(planche, cible / f"{i:02d}-{nom_de_fichier(planche.titre)}.svg")
        ecrits.append(f"plans/*.svg ({len(planches)} planches)")
    if "pdf" in demandes:
        pdf.ecrire(planches, dossier / "dossier.pdf")
        ecrits.append(f"dossier.pdf ({len(planches)} pages A3)")
    if "dxf" in demandes:
        cible = dossier / "dxf"
        cible.mkdir(parents=True, exist_ok=True)
        dxf.ecrire(planches, cible)
        ecrits.append(f"dxf/*.dxf ({len(planches)} fichiers)")
    if "3d" in demandes:
        from briq.drawings import volume

        cible = dossier / "3d"
        cible.mkdir(parents=True, exist_ok=True)
        volume.maison(calepinage, cible / "maison.glb")
        volume.colonne_d_angle(calepinage, cible / "colonne-d-angle.glb")
        ecrits.append("3d/maison.glb, 3d/colonne-d-angle.glb")
    return ecrits


def _rapport_texte(rapport: Rapport) -> str:
    from io import StringIO

    flux = StringIO()
    afficher_rapport(rapport, flux)
    return flux.getvalue()


def cmd_schema(args: argparse.Namespace) -> int:
    dossier: Path = args.sortie
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / "briq-plan-v1.schema.json"
    schema = Plan.model_json_schema(by_alias=True)
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "Plan BRIQ, version 1"
    cible.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Schema ecrit dans {cible}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(
        prog="briq",
        description="Calepinage, nomenclature et metre du systeme constructif BRIQ.",
    )
    sous = parseur.add_subparsers(dest="commande", required=True)

    p = sous.add_parser("valider", help="controler un plan sans rien produire")
    p.add_argument("plan", type=Path)
    p.set_defaults(fonction=cmd_valider)

    p = sous.add_parser("calepiner", help="calepiner un plan et ecrire le modele")
    p.add_argument("plan", type=Path)
    p.add_argument("-o", "--sortie", type=Path, default=Path("sortie"))
    p.add_argument(
        "--glouton",
        action="store_true",
        help="forcer le solveur de debit sans dependance au lieu de l'optimum exact",
    )
    p.add_argument(
        "--secondes",
        type=float,
        default=20.0,
        help="temps maximal accorde a chaque phase du solveur exact",
    )
    p.add_argument(
        "--formats",
        default=",".join(FORMATS),
        help="formats de plans a produire parmi svg, pdf, dxf, 3d ; vide pour aucun",
    )
    p.set_defaults(fonction=cmd_calepiner)

    p = sous.add_parser("schema", help="exporter le schema JSON du format de plan")
    p.add_argument("-o", "--sortie", type=Path, default=Path("schemas"))
    p.set_defaults(fonction=cmd_schema)

    args = parseur.parse_args(argv)
    return int(args.fonction(args))


if __name__ == "__main__":
    raise SystemExit(main())
