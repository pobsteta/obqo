"""Export 3D : chaque piece du systeme est une boite alignee sur les axes.

C'est le cas le plus simple qui existe en 3D, donc le rendu est presque gratuit
— et il repond a la seule question que les elevations 2D ne savent pas trancher :
**le harpage croise alterne des angles tombe-t-il juste ?** Une vue eclatee de la
colonne d'angle, rang par rang, montre en dix secondes si le tenon P5-A de la
filante coincide avec sa reception au rang suivant.

A traiter comme un outil de debogage du moteur, pas comme un livrable.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from briq.model.systeme import BriquePosee, Calepinage, MurCalepine, Rang
from briq.rules.geometrie_brique import MODULE, PiecePlacee, cellules_vides, pieces_de
from briq.units import EPAISSEUR_MUR, HAUTEUR_RANG

COULEURS: dict[str, tuple[int, int, int, int]] = {
    "P1": (196, 178, 148, 255),
    "P2": (214, 199, 172, 255),
    "P3": (150, 128, 96, 255),
    "P4": (176, 156, 122, 255),
    "P5": (196, 84, 52, 255),
    "P5-A": (232, 108, 60, 255),
    "P6": (166, 148, 118, 255),
    "P7": (150, 128, 96, 255),
    "P8": (120, 104, 80, 255),
}


def _repere(mur: MurCalepine) -> tuple[tuple[int, int], tuple[int, int], int]:
    (x0, y0), (x1, y1) = mur.depart, mur.arrivee
    dx = (x1 > x0) - (x1 < x0)
    dy = (y1 > y0) - (y1 < y0)
    v0 = -EPAISSEUR_MUR // 2 if mur.interieur else 0
    return (dx, dy), (-dy, dx), v0


def _coin(
    mur: MurCalepine,
    direction: tuple[int, int],
    normale: tuple[int, int],
    u: float,
    v: float,
    du: float,
    dv: float,
) -> tuple[float, float]:
    """Coin **minimum** d'une boite, dans le repere du plan.

    Un mur oriente vers l'ouest ou vers le sud a une direction negative : le
    point de depart de la boite y devient son bord maximum. Prendre le minimum
    composante par composante est la seule facon correcte de placer la boite.
    """
    (dx, dy), (nx, ny) = direction, normale
    a = (mur.depart[0] + dx * u + nx * v, mur.depart[1] + dy * u + ny * v)
    b = (
        mur.depart[0] + dx * (u + du) + nx * (v + dv),
        mur.depart[1] + dy * (u + du) + ny * (v + dv),
    )
    return (min(a[0], b[0]), min(a[1], b[1]))


def _angle_au_debut(brique: BriquePosee, rang: Rang) -> bool:
    """La filante d'angle porte son angle a son about de depart ou d'arrivee ?"""
    return brique.u == rang.debut


def pieces_globales(
    brique: BriquePosee, mur: MurCalepine, rang: Rang
) -> list[tuple[PiecePlacee, tuple[float, float, float], tuple[float, float, float]]]:
    """Boites de toutes les pieces d'une brique posee, en coordonnees du plan.

    Retourne des triplets (piece, coin bas, dimensions). Le repere local d'une
    brique d'angle est oriente angle en x = 0 : quand l'angle tombe a l'autre
    about, la brique est retournee.
    """
    (dx, dy), (nx, ny) = _repere(mur)[:2]
    v0 = _repere(mur)[2]
    retourner = brique.angle is not None and not _angle_au_debut(brique, rang)
    resultat: list[tuple[PiecePlacee, tuple[float, float, float], tuple[float, float, float]]] = []
    for piece in pieces_de(brique.ref):
        x = brique.longueur - piece.x - piece.dx if retourner else piece.x
        ux, uy = brique.u + x, v0 + piece.y
        plan = _coin(mur, (dx, dy), (nx, ny), ux, uy, piece.dx, piece.dy)
        coin = (plan[0], plan[1], float(brique.rang * HAUTEUR_RANG + piece.z))
        # Les axes du mur sont alignes sur X ou Y : les dimensions permutent.
        taille = (
            (float(piece.dx), float(piece.dy), float(piece.dz))
            if dx
            else (float(piece.dy), float(piece.dx), float(piece.dz))
        )
        resultat.append((piece, coin, taille))
    return resultat


def tenons_globaux(
    brique: BriquePosee, mur: MurCalepine, rang: Rang
) -> list[tuple[int, tuple[int, int]]]:
    """Tenons d'une brique : abscisse le long du mur et empreinte au sol.

    Un tenon deborde de 80 vers le haut : son empreinte doit se retrouver en
    reception dans la sous-face de la brique du rang superieur.
    """
    (dx, dy), (nx, ny), v0 = _repere(mur)
    retourner = brique.angle is not None and not _angle_au_debut(brique, rang)
    tenons = []
    for piece in pieces_de(brique.ref):
        if piece.ref not in ("P5", "P5-A"):
            continue
        x = brique.longueur - piece.x - piece.dx if retourner else piece.x
        ux, uy = brique.u + x, v0 + piece.y
        coin = _coin(mur, (dx, dy), (nx, ny), ux, uy, piece.dx, piece.dy)
        tenons.append((ux, (int(coin[0]), int(coin[1]))))
    return sorted(tenons)


def receptions_globales(brique: BriquePosee, mur: MurCalepine, rang: Rang) -> set[tuple[int, int]]:
    """Empreintes des trous de reception en sous-face d'une brique posee."""
    (dx, dy), (nx, ny), v0 = _repere(mur)
    retourner = brique.angle is not None and not _angle_au_debut(brique, rang)
    empreintes = set()
    for x, y, z in cellules_vides(brique.ref):
        if z:  # seules les cellules de la couche 1 sont des receptions
            continue
        xl = brique.longueur - x - MODULE if retourner else x
        ux, uy = brique.u + xl, v0 + y
        coin = _coin(mur, (dx, dy), (nx, ny), ux, uy, MODULE, MODULE)
        empreintes.add((int(coin[0]), int(coin[1])))
    return empreintes


def tenons_sans_reception(calepinage: Calepinage) -> list[tuple[str, int, int]]:
    """Tenons qui ne trouvent pas de trou en face au rang superieur.

    C'est la verification que les elevations 2D ne savent pas faire : dans un
    angle en harpage croise alterne, le tenon de la filante doit coincider avec
    la reception de la filante du rang suivant, tournee de 90 degres.
    """
    receptions: dict[int, set[tuple[int, int]]] = {}
    for mur in calepinage.murs:
        for rang in mur.rangs:
            cible = receptions.setdefault(rang.indice, set())
            for brique in rang.briques:
                cible |= receptions_globales(brique, mur, rang)

    orphelins: list[tuple[str, int, int]] = []
    dernier = max(receptions, default=0)
    for mur in calepinage.murs:
        for rang in mur.rangs:
            if rang.indice == dernier:  # le chainage haut remplace la reception
                continue
            au_dessus = receptions.get(rang.indice + 1, set())
            for brique in rang.briques:
                for u, empreinte in tenons_globaux(brique, mur, rang):
                    if empreinte not in au_dessus:
                        orphelins.append((brique.mur, rang.indice, u))
    return sorted(orphelins)


def _scene(
    boites: Sequence[tuple[str, tuple[float, float, float], tuple[float, float, float]]],
) -> Any:
    import numpy
    import trimesh

    scene = trimesh.Scene()
    for index, (ref, coin, taille) in enumerate(boites):
        maillage = trimesh.creation.box(extents=taille)
        maillage.apply_translation(
            [coin[i] + taille[i] / 2 for i in range(3)]  # trimesh centre ses boites
        )
        # Couleur posee directement aux sommets : la conversion faces ->
        # sommets de trimesh passerait par scipy, dependance inutile ici.
        couleur = numpy.array(COULEURS.get(ref, (180, 180, 180, 255)), dtype=numpy.uint8)
        maillage.visual.vertex_colors = numpy.tile(couleur, (len(maillage.vertices), 1))
        scene.add_geometry(maillage, node_name=f"{ref}-{index:05d}")
    return scene


def maison(calepinage: Calepinage, chemin: Path) -> int:
    """Vue d'ensemble : une boite par brique posee. Retourne le nombre de boites."""
    boites = []
    for mur in calepinage.murs:
        (dx, dy), (nx, ny), v0 = _repere(mur)
        for rang in mur.rangs:
            for brique in rang.briques:
                plan = _coin(mur, (dx, dy), (nx, ny), brique.u, v0, brique.longueur, EPAISSEUR_MUR)
                coin = (*plan, float(brique.rang * HAUTEUR_RANG))
                taille = (
                    (brique.longueur, EPAISSEUR_MUR, HAUTEUR_RANG)
                    if dx
                    else (EPAISSEUR_MUR, brique.longueur, HAUTEUR_RANG)
                )
                ref = "P5-A" if brique.angle else "P1"
                boites.append((ref, coin, taille))
    _scene(boites).export(chemin)
    return len(boites)


def colonne_d_angle(
    calepinage: Calepinage,
    chemin: Path,
    angle: str | None = None,
    rangs: int = 4,
    eclatement: int = 240,
) -> int:
    """Detail piece par piece autour d'un angle, les rangs ecartes en hauteur.

    `eclatement` ecarte verticalement les rangs pour rendre visibles les tenons
    et leurs receptions ; a zero, la colonne est assemblee telle qu'elle sera.
    """
    briques: list[tuple[BriquePosee, MurCalepine, Rang]] = []
    coins = sorted({b.angle for b in calepinage.briques if b.angle})
    if not coins:
        return 0
    cible = angle or coins[0]
    for mur in calepinage.murs:
        for rang in mur.rangs:
            if rang.indice >= rangs:
                continue
            for brique in rang.briques:
                if brique.angle == cible:
                    briques.append((brique, mur, rang))
                # La brique en butee du meme angle : premiere ou derniere du rang
                elif rang.briques and brique in (rang.briques[0], rang.briques[-1]):
                    voisin = _angle_voisin(mur, rang, brique, calepinage, cible)
                    if voisin:
                        briques.append((brique, mur, rang))

    boites = []
    for brique, mur, rang in briques:
        for piece, coin, taille in pieces_globales(brique, mur, rang):
            boites.append(
                (piece.ref, (coin[0], coin[1], coin[2] + rang.indice * eclatement), taille)
            )
    _scene(boites).export(chemin)
    return len(boites)


def _angle_voisin(
    mur: MurCalepine,
    rang: Rang,
    brique: BriquePosee,
    calepinage: Calepinage,
    cible: str,
) -> bool:
    """La brique en butee touche-t-elle l'angle vise ?"""
    filantes = [
        b
        for m in calepinage.murs
        for r in m.rangs
        if r.indice == rang.indice
        for b in r.briques
        if b.angle == cible
    ]
    if not filantes:
        return False
    reference = filantes[0]
    sommet = (
        (mur.depart[0], mur.depart[1])
        if brique.u == rang.debut
        else (mur.arrivee[0], mur.arrivee[1])
    )
    for m in calepinage.murs:
        if m.id != reference.mur:
            continue
        for bout in (m.depart, m.arrivee):
            if (
                abs(bout[0] - sommet[0]) <= EPAISSEUR_MUR
                and abs(bout[1] - sommet[1]) <= EPAISSEUR_MUR
            ):
                return True
    return False
