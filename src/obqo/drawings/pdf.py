"""Back-end PDF : ReportLab, pur Python, A3 a l'italienne, multi-pages.

Pas de cairosvg : il impose des bibliotheques systeme, rend mal le texte et ne
sait pas produire un document de plusieurs pages. Or on veut un dossier relie,
pas dix-sept fichiers separes.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from obqo.drawings.ir import (
    MENTION,
    Ancrage,
    Calque,
    Dessin,
    Polyligne,
    Rect,
    Texte,
    Trait,
)
from obqo.drawings.ir import STYLES as STYLES_IR
from obqo.drawings.mise_en_page import A3, Cadrage, Feuille, cadrer

POLICE = "Helvetica"


def _appliquer(canevas: Canvas, calque: Calque, pointille: bool) -> None:
    style = STYLES_IR[calque]
    canevas.setStrokeColor(HexColor(style.trait))
    canevas.setLineWidth(style.epaisseur * mm)
    canevas.setDash((2 * mm, 1.5 * mm) if pointille else ())
    if style.remplissage:
        canevas.setFillColor(HexColor(style.remplissage))


def _cartouche(canevas: Canvas, dessin: Dessin, cadrage: Cadrage, feuille: Feuille) -> None:
    style = STYLES_IR[Calque.CADRE]
    canevas.setStrokeColor(HexColor(style.trait))
    canevas.setLineWidth(style.epaisseur * mm)
    canevas.setDash(())
    canevas.rect(
        feuille.marge * mm,
        feuille.marge * mm,
        (feuille.largeur - 2 * feuille.marge) * mm,
        (feuille.hauteur - 2 * feuille.marge) * mm,
        stroke=1,
        fill=0,
    )
    haut = feuille.marge + feuille.cartouche
    canevas.line(feuille.marge * mm, haut * mm, (feuille.largeur - feuille.marge) * mm, haut * mm)
    canevas.setFillColor(HexColor(STYLES_IR[Calque.TEXTE].trait))
    lignes = (
        (haut - 8.0, 11.0, dessin.titre),
        (haut - 13.5, 7.0, dessin.sous_titre),
        (haut - 18.5, 7.0, f"Echelle 1:{cadrage.echelle}"),
        (haut - 23.5, 6.2, MENTION),
    )
    for y, taille, texte in lignes:
        if not texte:
            continue
        canevas.setFont(POLICE, taille)
        canevas.drawString((feuille.marge + 4) * mm, y * mm, texte)


def _legende(canevas: Canvas, dessin: Dessin, feuille: Feuille) -> None:
    if not dessin.legende:
        return
    x = feuille.largeur - feuille.marge - feuille.legende + 2
    y = feuille.hauteur - feuille.marge - 12
    for intitule, calque in dessin.legende:
        style = STYLES_IR[calque]
        canevas.setStrokeColor(HexColor(style.trait))
        canevas.setLineWidth(0.2 * mm)
        canevas.setDash(())
        if style.remplissage:
            canevas.setFillColor(HexColor(style.remplissage))
        canevas.rect(x * mm, y * mm, 4 * mm, 3 * mm, stroke=1, fill=1 if style.remplissage else 0)
        canevas.setFillColor(HexColor(STYLES_IR[Calque.TEXTE].trait))
        canevas.setFont(POLICE, 6.2)
        canevas.drawString((x + 5.5) * mm, (y + 0.6) * mm, intitule)
        y -= 5.5


def _page(canevas: Canvas, dessin: Dessin, feuille: Feuille) -> None:
    cadrage = cadrer(dessin, feuille)
    for primitive in dessin.primitives:
        style = STYLES_IR[primitive.calque]
        match primitive:
            case Rect():
                _appliquer(canevas, primitive.calque, primitive.pointille)
                x, y = cadrage.point(primitive.x, primitive.y)
                canevas.rect(
                    x * mm,
                    y * mm,
                    cadrage.longueur(primitive.dx) * mm,
                    cadrage.longueur(primitive.dy) * mm,
                    stroke=1,
                    fill=1 if style.remplissage else 0,
                )
            case Trait():
                _appliquer(canevas, primitive.calque, primitive.pointille)
                x1, y1 = cadrage.point(primitive.x1, primitive.y1)
                x2, y2 = cadrage.point(primitive.x2, primitive.y2)
                canevas.line(x1 * mm, y1 * mm, x2 * mm, y2 * mm)
            case Polyligne():
                _appliquer(canevas, primitive.calque, primitive.pointille)
                chemin = canevas.beginPath()
                points = [cadrage.point(x, y) for x, y in primitive.points]
                chemin.moveTo(points[0][0] * mm, points[0][1] * mm)
                for px, py in points[1:]:
                    chemin.lineTo(px * mm, py * mm)
                if primitive.ferme:
                    chemin.close()
                canevas.drawPath(
                    chemin, stroke=1, fill=1 if primitive.ferme and style.remplissage else 0
                )
            case Texte():
                canevas.setFillColor(HexColor(style.trait))
                canevas.setFont(POLICE, primitive.taille_mm * mm)
                x, y = cadrage.point(primitive.x, primitive.y)
                lignes = primitive.texte.split("\n")
                canevas.saveState()
                canevas.translate(x * mm, y * mm)
                if primitive.rotation:
                    canevas.rotate(primitive.rotation)
                for i, ligne in enumerate(lignes):
                    dy = -(i - (len(lignes) - 1) / 2) * primitive.taille_mm * 1.15
                    match primitive.ancrage:
                        case Ancrage.GAUCHE:
                            canevas.drawString(0, dy * mm, ligne)
                        case Ancrage.DROITE:
                            canevas.drawRightString(0, dy * mm, ligne)
                        case _:
                            canevas.drawCentredString(0, dy * mm, ligne)
                canevas.restoreState()

    _legende(canevas, dessin, feuille)
    _cartouche(canevas, dessin, cadrage, feuille)


def ecrire(planches: list[Dessin], chemin: Path, feuille: Feuille = A3) -> None:
    """Ecrit tout le dossier dans un seul PDF, une planche par page A3."""
    canevas = Canvas(
        str(chemin),
        pagesize=(feuille.largeur * mm, feuille.hauteur * mm),
        invariant=True,
    )
    canevas.setTitle("Dossier de calepinage BRIQ")
    for dessin in planches:
        _page(canevas, dessin, feuille)
        canevas.showPage()
    canevas.save()
