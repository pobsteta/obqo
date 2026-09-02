"""Back-end SVG : bibliotheque standard uniquement, aucune dependance."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from briq.drawings.ir import (
    MENTION,
    Ancrage,
    Calque,
    Dessin,
    Polyligne,
    Rect,
    Style,
    Texte,
    Trait,
)
from briq.drawings.ir import STYLES as STYLES_IR
from briq.drawings.mise_en_page import A3, Cadrage, Feuille, cadrer

ANCRAGES = {Ancrage.GAUCHE: "start", Ancrage.MILIEU: "middle", Ancrage.DROITE: "end"}


def _style(calque: Calque) -> Style:
    return STYLES_IR[calque]


def _attributs(style: Style, remplir: bool, pointille: bool) -> dict[str, str]:
    attrs = {
        "stroke": style.trait,
        "stroke-width": f"{style.epaisseur}",
        "fill": style.remplissage if remplir and style.remplissage else "none",
        "stroke-linejoin": "round",
    }
    if pointille:
        attrs["stroke-dasharray"] = "2 1.5"
    return attrs


def _texte(parent: ET.Element, primitive: Texte, cadrage: Cadrage, feuille: Feuille) -> None:
    style = _style(primitive.calque)
    x, y = cadrage.point(primitive.x, primitive.y)
    y = feuille.hauteur - y
    lignes = primitive.texte.split("\n")
    for i, ligne in enumerate(lignes):
        decalage = (i - (len(lignes) - 1) / 2) * primitive.taille_mm * 1.15
        element = ET.SubElement(
            parent,
            "text",
            {
                "x": f"{x:.3f}",
                "y": f"{y + decalage:.3f}",
                "font-size": f"{primitive.taille_mm}",
                "fill": style.trait,
                "text-anchor": ANCRAGES[primitive.ancrage],
                "dominant-baseline": "central",
                "font-family": "Helvetica, Arial, sans-serif",
            },
        )
        if primitive.rotation:
            element.set("transform", f"rotate({-primitive.rotation} {x:.3f} {y + decalage:.3f})")
        element.text = ligne


def _cartouche(racine: ET.Element, dessin: Dessin, cadrage: Cadrage, feuille: Feuille) -> None:
    style = _style(Calque.CADRE)
    haut = feuille.hauteur - feuille.marge - feuille.cartouche
    ET.SubElement(
        racine,
        "rect",
        {
            "x": f"{feuille.marge}",
            "y": f"{feuille.marge}",
            "width": f"{feuille.largeur - 2 * feuille.marge}",
            "height": f"{feuille.hauteur - 2 * feuille.marge}",
            "fill": "none",
            "stroke": style.trait,
            "stroke-width": f"{style.epaisseur}",
        },
    )
    ET.SubElement(
        racine,
        "line",
        {
            "x1": f"{feuille.marge}",
            "y1": f"{haut}",
            "x2": f"{feuille.largeur - feuille.marge}",
            "y2": f"{haut}",
            "stroke": style.trait,
            "stroke-width": f"{style.epaisseur}",
        },
    )
    textes = [
        (haut + 7.0, 4.0, dessin.titre),
        (haut + 12.8, 2.5, dessin.sous_titre),
        (haut + 17.8, 2.5, f"Echelle 1:{cadrage.echelle}"),
        (haut + 22.8, 2.2, MENTION),
    ]
    for y, taille, texte in textes:
        if not texte:
            continue
        element = ET.SubElement(
            racine,
            "text",
            {
                "x": f"{feuille.marge + 4}",
                "y": f"{y}",
                "font-size": f"{taille}",
                "fill": _style(Calque.TEXTE).trait,
                "font-family": "Helvetica, Arial, sans-serif",
            },
        )
        element.text = texte


def _legende(racine: ET.Element, dessin: Dessin, feuille: Feuille) -> None:
    if not dessin.legende:
        return
    x = feuille.largeur - feuille.marge - feuille.legende + 2
    y = feuille.marge + feuille.cartouche + 6
    for intitule, calque in dessin.legende:
        style = _style(calque)
        ET.SubElement(
            racine,
            "rect",
            {
                "x": f"{x}",
                "y": f"{y - 2.6}",
                "width": "4",
                "height": "3",
                "fill": style.remplissage or "none",
                "stroke": style.trait,
                "stroke-width": "0.2",
            },
        )
        element = ET.SubElement(
            racine,
            "text",
            {
                "x": f"{x + 5.5}",
                "y": f"{y}",
                "font-size": "2.2",
                "fill": _style(Calque.TEXTE).trait,
                "font-family": "Helvetica, Arial, sans-serif",
            },
        )
        element.text = intitule
        y += 5.5


def rendre(dessin: Dessin, feuille: Feuille = A3, pour_ecran: bool = False) -> str:
    """Rend une planche en SVG, a l'echelle, avec cartouche et legende.

    `pour_ecran` omet les dimensions en millimetres : la planche s'adapte alors
    a son conteneur au lieu de s'imprimer a l'echelle exacte.
    """
    cadrage = cadrer(dessin, feuille)
    dimensions = (
        {} if pour_ecran else {"width": f"{feuille.largeur}mm", "height": f"{feuille.hauteur}mm"}
    )
    racine = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            **dimensions,
            "viewBox": f"0 0 {feuille.largeur} {feuille.hauteur}",
        },
    )
    ET.SubElement(racine, "rect", {"width": "100%", "height": "100%", "fill": "#ffffff"})

    groupes: dict[Calque, ET.Element] = {}
    for calque in dessin.calques_utilises():
        groupes[calque] = ET.SubElement(racine, "g", {"id": calque.value})

    for primitive in dessin.primitives:
        groupe = groupes[primitive.calque]
        style = _style(primitive.calque)
        match primitive:
            case Rect():
                x, y = cadrage.point(primitive.x, primitive.y + primitive.dy)
                ET.SubElement(
                    groupe,
                    "rect",
                    {
                        "x": f"{x:.3f}",
                        "y": f"{feuille.hauteur - y:.3f}",
                        "width": f"{cadrage.longueur(primitive.dx):.3f}",
                        "height": f"{cadrage.longueur(primitive.dy):.3f}",
                        **_attributs(style, True, primitive.pointille),
                    },
                )
            case Trait():
                x1, y1 = cadrage.point(primitive.x1, primitive.y1)
                x2, y2 = cadrage.point(primitive.x2, primitive.y2)
                ET.SubElement(
                    groupe,
                    "line",
                    {
                        "x1": f"{x1:.3f}",
                        "y1": f"{feuille.hauteur - y1:.3f}",
                        "x2": f"{x2:.3f}",
                        "y2": f"{feuille.hauteur - y2:.3f}",
                        **_attributs(style, False, primitive.pointille),
                    },
                )
            case Polyligne():
                points = " ".join(
                    f"{px:.3f},{feuille.hauteur - py:.3f}"
                    for px, py in (cadrage.point(x, y) for x, y in primitive.points)
                )
                ET.SubElement(
                    groupe,
                    "polygon" if primitive.ferme else "polyline",
                    {"points": points, **_attributs(style, primitive.ferme, primitive.pointille)},
                )
            case Texte():
                _texte(groupe, primitive, cadrage, feuille)

    _legende(racine, dessin, feuille)
    _cartouche(racine, dessin, cadrage, feuille)
    ET.indent(racine, space=" ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(racine, encoding="unicode")


def ecrire(dessin: Dessin, chemin: Path, feuille: Feuille = A3) -> None:
    chemin.write_text(rendre(dessin, feuille) + "\n", encoding="utf-8", newline="\n")
