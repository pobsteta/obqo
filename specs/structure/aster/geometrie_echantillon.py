"""obqo -> JSON : la geometrie d'un echantillon d'essai, tiree des tables du depot.

Rien n'est redessine a la main. Les boites viennent de `rules/geometrie_brique`,
les quantites de chevilles de `rules/catalogue` : si la composition d'une brique
change dans obqo, le JSON change avec, et le maillage se refait. **Ne corrigez
jamais un maillage a la main — corrigez ce script et regenerez.**

    uv run python specs/structure/aster/geometrie_echantillon.py rang --briques 3 -o rang.json
    uv run python specs/structure/aster/geometrie_echantillon.py cheville -o cheville.json
    uv run python specs/structure/aster/geometrie_echantillon.py poteau -o poteau.json

Repere, le meme que celui du module `structure` : **x** le long du mur, **y**
dans l'epaisseur (parement exterieur en y = 0), **z** en hauteur.

Ce que ce script **ne fait pas** : il ne maille pas, ne calcule pas, et ne
decide d'aucune hypothese. Chaque objet qu'il ecrit porte le code de
l'hypothese qui l'a place (`H-A1` a `H-A7`), pour qu'on puisse les contester
une par une plutot qu'en bloc.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "src"))

from obqo.model.systeme import Ref  # noqa: E402
from obqo.rules.catalogue import CORPS_480, PIECES, RAIDISSEUR_PAR_RANG  # noqa: E402
from obqo.rules.geometrie_brique import (  # noqa: E402
    MODULE,
    PENETRATION_CHEVILLE_POTEAU,
    PiecePlacee,
    pieces_de,
)
from obqo.units import EPAISSEUR_MUR, HAUTEUR_RANG, LARGEUR_POTEAU  # noqa: E402

# --- Direction du fil ----------------------------------------------------------
# Deduite des designations du catalogue, pas d'un gout : « couche traversant »
# traverse l'epaisseur, « bois debout » se tient vertical, ame et raccords
# courent le long du mur. C'est l'hypothese qui decide de tout le calcul
# orthotrope, et c'est celle a confirmer en premier.

FIL: dict[str, str] = {
    "P1": "y",  # bois couche traversant perce
    "P2": "y",  # bois couche traversant
    "P3": "x",  # ame, file le long du mur
    "P4": "z",  # montant bois debout
    "P5": "z",  # tenon, plante debout sur l'ame
    "P5-A": "z",
    "P6": "x",  # remplissage / raccord inter-briques
    "P7": "x",  # ame courte
    "P8": "y",  # carre de fermeture, ferme un parement comme un traversant
    "P9": "x",  # madrier de linteau
    "P10": "z",  # poteau, d'un seul tenant du pied au chainage
    "LISSE": "x",
}

HYPOTHESES: dict[str, str] = {
    "H-A1": (
        "chevilles de joint courant : 2 C1 verticales, une par raccord P6, "
        "chacune dans la brique dont le raccord depasse (x = joint +/- 40, "
        "y = 40 et 200). Le paragraphe 1.2 dit « 1 cheville par brique » sans "
        "donner la position."
    ),
    "H-A2": (
        "chevilles d'atelier d'une 480 : 6 C1 verticales au centre de "
        "l'epaisseur (y = 120), une par ligne ; 4 C1 traversantes selon y dans "
        "les 4 montants P4, a deux hauteurs (z = 60 et 180). Lecture de "
        "« 6 verticales + 4 traversantes de montants »."
    ),
    "H-A3": (
        "piges C3 de 40 mm : 2 par montant et par couche, de part et d'autre de "
        "l'interface avec le traversant voisin, selon x. 4 montants x 2 couches "
        "x 2 = 16 par brique, comme le catalogue."
    ),
    "H-A4": (
        "liaison poteau-rang : 2 C1 par rang, decalees, y = 120, z = 40 et 200 "
        "dans le rang, 80 mm dans le poteau et 150 dans l'about voisin. C'est la "
        "regle D7, desormais au catalogue."
    ),
    "H-A5": "jeu fut/trou nul, pas de serrage a l'humidite.",
    "H-A6": "frottement bois/bois 0,35.",
    "H-A7": (
        "echantillon E1 : le brief decrit deux traversants P2 exterieurs « fil "
        "selon y » et une cheville selon y, donc parallele a leur fil — ce qui "
        "ne peut pas se batir, un P2 ne faisant que 80 mm en y. La configuration "
        "reellement percee dans la brique est retenue : la cheville selon y "
        "traverse deux montants P4 (fil z) et l'ame P3 (fil x) entre eux, et "
        "c'est elle qui donne les conditions aux limites du brief (appuis en "
        "x = 0 des pieces exterieures, DX impose sur la piece centrale)."
    ),
}

DIAMETRE_CHEVILLE = 20
"""Diametre d'une C1 comme d'une C3, mm (catalogue)."""


def _boite(p: PiecePlacee, dx: int = 0, dy: int = 0, dz: int = 0) -> dict[str, Any]:
    """Une piece bois, translatee, avec sa reference et sa direction de fil."""
    return {
        "ref": p.ref,
        "groupe": f"P_{p.ref.replace('-', '')}",
        "fil": FIL[p.ref],
        "origine": [p.x + dx, p.y + dy, p.z + dz],
        "dimensions": [p.dx, p.dy, p.dz],
    }


def _cheville(
    ref: str, axe: str, origine: tuple[int, int, int], longueur: int, hypothese: str
) -> dict[str, Any]:
    """Une cheville : un axe, pas une boite — Salome la percera.

    Le nom definitif est pose a la fin, quand l'echantillon est complet : c'est
    lui qui donnera les groupes de faces `FUT_<nom>` et `TROU_<nom>` du maillage.
    """
    return {
        "ref": ref,
        "groupe": "CHEVILLES",
        "axe": axe,
        "origine": list(origine),
        "longueur": longueur,
        "diametre": DIAMETRE_CHEVILLE,
        "hypothese": hypothese,
    }


def _face(nom: str, normale: str, coordonnee: int, commentaire: str) -> dict[str, Any]:
    """Un groupe de faces : un plan, et ce qu'on en fait dans le .comm."""
    return {
        "nom": nom,
        "normale": normale,
        "coordonnee": coordonnee,
        "role": commentaire,
    }


# --- Echantillon E2 : un rang de briques ---------------------------------------


def _chevilles_d_atelier(u: int) -> list[dict[str, Any]]:
    """Les 10 C1 d'une brique 480 (H-A2), dans le repere du mur."""
    chevilles = [_cheville("C1", "z", (u + 40 + MODULE * i, 120, 5), 230, "H-A2") for i in range(6)]
    chevilles += [
        _cheville("C1", "y", (u + x, 5, z), 230, "H-A2") for x in (120, 360) for z in (60, 180)
    ]
    return chevilles


def _piges(u: int) -> list[dict[str, Any]]:
    """Les 16 piges C3 d'une brique 480 (H-A3) : 2 par montant et par couche."""
    piges = []
    for x0 in (MODULE, 4 * MODULE):  # montants des lignes 2 et 5
        for y0 in (0, 160):
            for z0 in (0, 160):  # couches 1 et 3
                for face in (x0, x0 + MODULE):
                    piges.append(
                        _cheville("C3", "x", (u + face - 20, y0 + 40, z0 + 40), 40, "H-A3")
                    )
    return piges[:16]


def rang(briques: int) -> dict[str, Any]:
    """E2 — un rang de N briques 480 bout a bout, abouts fermes, joints chevilles."""
    pieces: list[dict[str, Any]] = []
    chevilles: list[dict[str, Any]] = []
    longueur = briques * 480

    for i in range(briques):
        u = i * 480
        pieces += [_boite(p, dx=u) for p in pieces_de(Ref.B480_S)]
        chevilles += _chevilles_d_atelier(u)
        chevilles += _piges(u)

    # Raccords P6 a cheval sur chaque joint courant, et leurs 2 C1 (H-A1).
    for i in range(1, briques):
        joint = i * 480
        for y in (0, 160):
            pieces.append(
                {
                    "ref": "P6",
                    "groupe": "P_P6",
                    "fil": FIL["P6"],
                    "origine": [joint - MODULE, y, MODULE],
                    "dimensions": [2 * MODULE, MODULE, MODULE],
                }
            )
        chevilles.append(_cheville("C1", "z", (joint - 40, 40, 5), 230, "H-A1"))
        chevilles.append(_cheville("C1", "z", (joint + 40, 200, 5), 230, "H-A1"))

    # Fermeture des deux abouts du rang : 2 carres P8 par about.
    for x in (0, longueur - MODULE):
        for y in (0, 160):
            pieces.append(
                {
                    "ref": "P8",
                    "groupe": "P_P8",
                    "fil": FIL["P8"],
                    "origine": [x, y, MODULE],
                    "dimensions": [MODULE, MODULE, MODULE],
                }
            )

    return {
        "echantillon": "rang",
        "essai": "E2 — rang en flexion hors plan",
        "briques": briques,
        "encombrement": [longueur, EPAISSEUR_MUR, HAUTEUR_RANG],
        "pieces": pieces,
        "chevilles": chevilles,
        "faces": [
            _face("APPUI_GAUCHE", "x", 0, "bloque DY (appui simple), libre en x et z"),
            _face("APPUI_DROIT", "x", longueur, "bloque DY (appui simple)"),
            _face("PAREMENT_EXT", "y", 0, "pression uniforme du vent, 0 a 5 kN/m2"),
        ],
        "lecture": (
            "fleche au milieu de la ligne mediane du parement interieur, "
            "sigma_LL dans les ames P3 et les raccords P6, sigma_TT autour des "
            "chevilles de joint, glissement fut/trou."
        ),
    }


# --- Echantillon E1 : une cheville en double cisaillement ----------------------


def cheville() -> dict[str, Any]:
    """E1 — la configuration reellement percee dans la brique (voir H-A7).

    Trois carrelets empiles selon y, la cheville selon y les traversant tous :
    deux montants P4 (fil z) de part et d'autre, l'ame P3 (fil x) au centre. Les
    montants sont tenus par leur face x = 0, l'ame poussee par sa face x = 240.
    """
    longueur = 240
    pieces = [
        {
            "ref": "P4",
            "groupe": "P_P4",
            "fil": FIL["P4"],
            "origine": [0, y, 0],
            "dimensions": [longueur, MODULE, MODULE],
        }
        for y in (0, 160)
    ]
    pieces.append(
        {
            "ref": "P3",
            "groupe": "P_P3",
            "fil": FIL["P3"],
            "origine": [0, MODULE, 0],
            "dimensions": [longueur, MODULE, MODULE],
        }
    )
    return {
        "echantillon": "cheville",
        "essai": "E1 — cheville en double cisaillement",
        "encombrement": [longueur, EPAISSEUR_MUR, MODULE],
        "pieces": pieces,
        "chevilles": [_cheville("C1", "y", (120, 5, 40), 230, "H-A7")],
        "faces": [
            _face("APPUI_EXT", "x", 0, "faces x = 0 des deux montants : bloquees"),
            _face("CHARGE_CENTRE", "x", longueur, "face x = 240 de l'ame : DX impose 0 a 15 mm"),
        ],
        "lecture": (
            "F(u) au point de charge, 30 pas jusqu'a 15 mm. K_ser = pente entre "
            "0,1 et 0,4 F_max (EN 26891) ; F_v,R = min(F_max, F a 15 mm)."
        ),
    }


# --- Echantillon E3 : liaison poteau-rang -------------------------------------


def poteau(rangs: int = 3) -> dict[str, Any]:
    """E3 — un P10 sur 3 rangs, une brique fermee de chaque cote a chaque rang."""
    hauteur = rangs * HAUTEUR_RANG
    aile = 480  # une brique de chaque cote du module de poteau
    module = 240
    pieces: list[dict[str, Any]] = [
        {
            "ref": "P10",
            "groupe": "P_P10",
            "fil": FIL["P10"],
            "origine": [aile, 0, 0],
            "dimensions": [LARGEUR_POTEAU, EPAISSEUR_MUR, hauteur],
        }
    ]
    chevilles: list[dict[str, Any]] = []
    for r in range(rangs):
        z = r * HAUTEUR_RANG
        # A gauche du module, une brique fermee ; a droite, une autre.
        for u in (0, aile + module):
            pieces += [_boite(p, dx=u, dz=z) for p in pieces_de(Ref.B480_AA)]
        # Remplissage du module : 9 P6 par rang (D6), en 3 rangees de 3 lignes.
        for iy in range(3):
            for iz in range(3):
                pieces.append(
                    {
                        "ref": "P6",
                        "groupe": "P_P6",
                        "fil": FIL["P6"],
                        "origine": [aile + LARGEUR_POTEAU, iy * MODULE, z + iz * MODULE],
                        "dimensions": [module - LARGEUR_POTEAU, MODULE, MODULE],
                    }
                )
        # D7 / H-A4 : deux C1 decalees, l'une vers la gauche, l'autre vers la droite.
        chevilles.append(
            _cheville(
                "C1",
                "x",
                (aile - PENETRATION_CHEVILLE_POTEAU, 120, z + 40),
                LARGEUR_POTEAU + PENETRATION_CHEVILLE_POTEAU,
                "H-A4",
            )
        )
        chevilles.append(
            _cheville(
                "C1",
                "x",
                (aile, 120, z + 200),
                LARGEUR_POTEAU + PENETRATION_CHEVILLE_POTEAU,
                "H-A4",
            )
        )
    return {
        "echantillon": "poteau",
        "essai": "E3 — liaison poteau-rang",
        "rangs": rangs,
        "chevilles_par_rang_au_catalogue": int(RAIDISSEUR_PAR_RANG["C1"]),
        "encombrement": [2 * aile + module, EPAISSEUR_MUR, hauteur],
        "pieces": pieces,
        "chevilles": chevilles,
        "faces": [
            _face("PIED", "z", 0, "pied du poteau : DX DY DZ bloques"),
            _face("TETE", "z", hauteur, "tete du poteau : DX DY DZ bloques"),
            _face("PAREMENT_EXT", "y", 0, "pression sur les briques, 0 a 3 kN/m2"),
            _face("BORD_GAUCHE", "x", 0, "le mur continue : DX bloque"),
            _face("BORD_DROIT", "x", 2 * aile + module, "le mur continue : DX bloque"),
        ],
        "lecture": (
            "deplacement relatif brique/poteau en y a chaque rang, resultante "
            "sur chaque FUT_*, contraintes de fendage dans le P10 autour des trous."
        ),
        "notes": [
            "Les chevilles d'atelier et les piges des briques ne sont pas percees "
            "ici : E3 mesure la liaison poteau-rang, et un contact de plus par "
            "cheville doublerait le maillage sans rien changer a ce qu'on lit. "
            "Les interfaces bois/bois interieures aux briques sont donc collees.",
        ],
    }


ECHANTILLONS = {"rang": rang, "cheville": cheville, "poteau": poteau}


def _nommer(document: dict[str, Any]) -> None:
    """Numerote les chevilles : `FUT_C007` et `TROU_C007` en decoulent."""
    for indice, cheville_posee in enumerate(document["chevilles"], start=1):
        cheville_posee["nom"] = f"C{indice:03d}"


def _controler(document: dict[str, Any]) -> None:
    """Garde-fou : toute piece ecrite doit exister au catalogue et avoir un fil."""
    for piece in document["pieces"]:
        if piece["ref"] not in PIECES:
            raise SystemExit(f"piece {piece['ref']} absente du catalogue")
        if piece["fil"] not in ("x", "y", "z"):
            raise SystemExit(f"fil {piece['fil']} inconnu pour {piece['ref']}")


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analyseur.add_argument("echantillon", choices=sorted(ECHANTILLONS))
    analyseur.add_argument("--briques", type=int, default=3, help="rang : nombre de briques")
    analyseur.add_argument("--rangs", type=int, default=3, help="poteau : nombre de rangs")
    analyseur.add_argument("-o", "--sortie", type=Path, help="fichier JSON a ecrire")
    args = analyseur.parse_args(argv)

    if args.echantillon == "rang":
        document = rang(args.briques)
    elif args.echantillon == "poteau":
        document = poteau(args.rangs)
    else:
        document = cheville()

    document = {
        "unite": "mm",
        "repere": {
            "x": "le long du mur",
            "y": "dans l'epaisseur, parement exterieur en y = 0",
            "z": "en hauteur",
        },
        "briques_de_reference": {"corps_480": dict(sorted(CORPS_480.items()))},
        **document,
        "hypotheses": HYPOTHESES,
    }
    _nommer(document)
    _controler(document)

    texte = json.dumps(document, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    if args.sortie:
        args.sortie.write_text(texte, encoding="utf-8", newline="\n")
        print(
            f"{args.sortie} : {len(document['pieces'])} pieces, "
            f"{len(document['chevilles'])} chevilles"
        )
    else:
        print(texte, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
