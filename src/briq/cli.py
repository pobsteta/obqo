"""Interface en ligne de commande (jalon 1 : valider, calepiner, schema)."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

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
    calepinage, rapport = calepiner(charger(args.plan))
    afficher_rapport(rapport)
    if calepinage is None:
        print("\nCalepinage impossible : corriger les erreurs ci-dessus.", file=sys.stderr)
        return 1
    dossier: Path = args.sortie
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / "calepinage.json"
    cible.write_text(
        json.dumps(serialiser(calepinage), indent=2, ensure_ascii=False, default=_brut) + "\n",
        encoding="utf-8",
    )
    total = len(calepinage.briques)
    print(f"\n{total} briques posees sur {len(calepinage.murs)} murs -> {cible}")
    for ref, n in sorted(calepinage.compte_briques().items()):
        print(f"  {ref.value:8} {n:5}")
    return 0


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
    p.set_defaults(fonction=cmd_calepiner)

    p = sous.add_parser("schema", help="exporter le schema JSON du format de plan")
    p.add_argument("-o", "--sortie", type=Path, default=Path("schemas"))
    p.set_defaults(fonction=cmd_schema)

    args = parseur.parse_args(argv)
    return int(args.fonction(args))


if __name__ == "__main__":
    raise SystemExit(main())
