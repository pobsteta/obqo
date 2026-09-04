"""JSON -> geometrie Salome, groupes et maillage MED.

**NON TESTE.** Ce script a ete ecrit sans Salome sous la main. Relisez-le
**appel par appel** contre la documentation de votre version (9.x) avant de
vous fier au maillage qu'il produit : `MakePartition`, `GetShapesOnShape` et la
selection des faces cylindriques sont les trois endroits ou les signatures
bougent d'une version a l'autre.

A lancer depuis Salome, pas depuis le depot :

    salome -t specs/structure/aster/salome_echantillon.py args:rang.json,rang.med

Ce qu'il fait, dans l'ordre :

1. une boite par piece bois, une par cheville (cylindre) ;
2. **partition du bois seul**, qui colle les interfaces bois/bois en leur
   donnant des noeuds communs, puis **decoupe** des trous par les cylindres.
   Les chevilles restent des solides **separes** : c'est indispensable, une
   partition qui les inclurait rendrait l'interface fut/trou conforme, et il
   n'y aurait plus de contact a calculer — seulement du bois colle a du hetre ;
3. les groupes de mailles que le `.comm` attend (voir le tableau du brief) ;
4. maillage tetraedrique quadratique, 20 mm dans le bois, 8 mm sur les
   chevilles, puis export MED.

Taille attendue : un rang de 3 briques donne de l'ordre de 300 000 a 600 000
noeuds. Comptez des heures de `STAT_NON_LINE` avec contact, pas des minutes. Si
c'est trop, laissez les interfaces bois/bois collees par la partition et ne
gardez le contact qu'au fut des chevilles — c'est ce que fait `E1_cheville.comm`.
"""

from __future__ import annotations

import json
import sys

import GEOM  # constantes ST_IN / ST_ON de Salome
import salome
import SMESH
from salome.geom import geomBuilder
from salome.smesh import smeshBuilder

salome.salome_init()
geompy = geomBuilder.New()
smesh = smeshBuilder.New()

MAILLE_BOIS = 20.0
MAILLE_CHEVILLE = 8.0
"""Tailles de maille, mm. La cheville est plus fine : c'est elle qui plastifie."""

DIRECTIONS = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}


def _boite(piece):
    """Une piece bois : une boite alignee sur les axes, translatee a sa place."""
    x, y, z = piece["origine"]
    dx, dy, dz = piece["dimensions"]
    boite = geompy.MakeBoxDXDYDZ(dx, dy, dz)
    return geompy.MakeTranslation(boite, x, y, z)


def _cylindre(cheville):
    """Une cheville : un cylindre d'axe x, y ou z."""
    x, y, z = cheville["origine"]
    axe = geompy.MakeVectorDXDYDZ(*DIRECTIONS[cheville["axe"]])
    origine = geompy.MakeVertex(x, y, z)
    return geompy.MakeCylinder(
        origine, axe, cheville["diametre"] / 2.0, float(cheville["longueur"])
    )


def construire(document):
    """Le bois d'un cote, les chevilles de l'autre, et surtout pas l'inverse.

    Le bois est partitionne avec lui-meme : ses interfaces deviennent
    conformes, deux pieces contigues partagent leurs noeuds, et rien ne se
    traverse. Les trous sont ensuite **decoupes** par les cylindres, mais les
    cylindres ne sont pas partitionnes dans le bois : sans quoi le fut et le
    trou seraient une seule et meme face, et le contact n'aurait plus lieu
    d'etre. C'est le point de ce script a relire en premier.
    """
    bois = [_boite(p) for p in document["pieces"]]
    chevilles = [_cylindre(c) for c in document["chevilles"]]

    assemble = geompy.MakePartition(bois, [], [], [], geompy.ShapeType["SOLID"], 0, [], 0)
    perce = geompy.MakeCutList(assemble, chevilles) if chevilles else assemble
    assemblage = geompy.MakeCompound([perce, *chevilles])
    geompy.addToStudy(assemblage, document["echantillon"])
    return assemblage, perce, bois, chevilles


def _solides_dans(assemblage, gabarit, nom):
    """Groupe de volumes : les solides de la partition contenus dans `gabarit`."""
    groupe = geompy.CreateGroup(assemblage, geompy.ShapeType["SOLID"])
    trouves = geompy.GetShapesOnShapeIDs(gabarit, assemblage, geompy.ShapeType["SOLID"], GEOM.ST_IN)
    geompy.UnionIDs(groupe, trouves)
    geompy.addToStudyInFather(assemblage, groupe, nom)
    return groupe


def _faces_sur(assemblage, gabarit, nom, dans=None):
    """Groupe de faces posees sur `gabarit`, restreint a `dans` si donne."""
    groupe = geompy.CreateGroup(assemblage, geompy.ShapeType["FACE"])
    source = dans if dans is not None else assemblage
    geompy.UnionIDs(
        groupe,
        geompy.GetShapesOnShapeIDs(gabarit, source, geompy.ShapeType["FACE"], GEOM.ST_ON),
    )
    geompy.addToStudyInFather(assemblage, groupe, nom)
    return groupe


def grouper(assemblage, perce, document, bois, chevilles):
    """Les groupes que le `.comm` nomme : pieces, fil, chevilles, contact, faces."""
    groupes = {}

    # Un groupe par reference de piece, pour lire les contraintes piece par piece.
    par_ref = {}
    for piece, forme in zip(document["pieces"], bois, strict=True):
        par_ref.setdefault(piece["groupe"], []).append(forme)
    for nom, formes in par_ref.items():
        groupes[nom] = _solides_dans(assemblage, geompy.MakeCompound(formes), nom)

    # Un groupe par direction de fil : c'est lui qui pilote ANGL_REP.
    par_fil = {}
    for piece, forme in zip(document["pieces"], bois, strict=True):
        par_fil.setdefault(f"FIL_{piece['fil'].upper()}", []).append(forme)
    for nom, formes in par_fil.items():
        groupes[nom] = _solides_dans(assemblage, geompy.MakeCompound(formes), nom)

    if chevilles:
        groupes["CHEVILLES"] = _solides_dans(
            assemblage, geompy.MakeCompound(chevilles), "CHEVILLES"
        )

    # La paire de contact : FUT_ est la face laterale de la cheville, TROU_ la
    # face cylindrique que la decoupe a laissee dans le bois. Deux faces
    # distinctes, geometriquement confondues — c'est bien ce qu'il faut.
    for cheville, forme in zip(document["chevilles"], chevilles, strict=True):
        nom = cheville["nom"]
        groupes[f"FUT_{nom}"] = _faces_sur(assemblage, forme, f"FUT_{nom}", dans=forme)
        groupes[f"TROU_{nom}"] = _faces_sur(assemblage, forme, f"TROU_{nom}", dans=perce)

    # Faces de conditions aux limites : un plan, donne par sa normale.
    for face in document["faces"]:
        normale = face["normale"]
        plan = geompy.MakePlane(
            geompy.MakeVertex(
                *[face["coordonnee"] if a == normale else 0 for a in ("x", "y", "z")]
            ),
            geompy.MakeVectorDXDYDZ(*DIRECTIONS[normale]),
            10_000,
        )
        groupes[face["nom"]] = _faces_sur(assemblage, plan, face["nom"])

    return groupes


def mailler(assemblage, groupes, chemin):
    """Tetraedres quadratiques, plus fins sur les chevilles, puis MED."""
    maillage = smesh.Mesh(assemblage, "echantillon")
    netgen = maillage.Tetrahedron(algo=smeshBuilder.NETGEN_1D2D3D)
    parametres = netgen.Parameters()
    parametres.SetMaxSize(MAILLE_BOIS)
    parametres.SetMinSize(MAILLE_CHEVILLE / 2.0)
    parametres.SetSecondOrder(1)
    parametres.SetOptimize(1)

    fin = maillage.Tetrahedron(algo=smeshBuilder.NETGEN_1D2D3D, geom=groupes["CHEVILLES"])
    fin.Parameters().SetMaxSize(MAILLE_CHEVILLE)

    for nom, groupe in groupes.items():
        maillage.GroupOnGeom(groupe, nom, SMESH.ELEM0D)

    if not maillage.Compute():
        raise SystemExit("le maillage a echoue : reprendre les tailles de maille")
    maillage.ExportMED(chemin)
    print(f"{chemin} : {maillage.NbNodes()} noeuds, {maillage.NbTetras()} tetraedres")


def main(entree, sortie):
    with open(entree, encoding="utf-8") as flux:
        document = json.load(flux)
    assemblage, perce, bois, chevilles = construire(document)
    groupes = grouper(assemblage, perce, document, bois, chevilles)
    mailler(assemblage, groupes, sortie)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage : salome -t salome_echantillon.py args:<entree.json>,<sortie.med>")
    main(sys.argv[1], sys.argv[2])
