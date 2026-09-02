"""Back-end DXF : ezdxf, pur Python, dessin a l'echelle 1 dans l'espace objet.

Le DXF n'est pas une feuille mais un modele : on y dessine en millimetres reels,
comme l'attend un logiciel de CAO. C'est le format qu'un bureau d'etudes bois
peut ouvrir, mesurer et annoter — et le brief impose de lui faire valider le
dimensionnement.
"""

from __future__ import annotations

from pathlib import Path

import ezdxf
import ezdxf.document
import ezdxf.enums

from obqo.drawings.ir import (
    MENTION,
    Ancrage,
    Calque,
    Dessin,
    Polyligne,
    Rect,
    Texte,
    Trait,
    nom_de_fichier,
)
from obqo.drawings.ir import STYLES as STYLES_IR
from obqo.drawings.mise_en_page import A3, cadrer

ALIGNEMENTS = {Ancrage.GAUCHE: "LEFT", Ancrage.MILIEU: "CENTER", Ancrage.DROITE: "RIGHT"}


def ecrire(planches: list[Dessin], dossier: Path) -> list[Path]:
    """Un fichier DXF par planche, chacun a l'echelle 1."""
    ecrits: list[Path] = []
    for index, dessin in enumerate(planches):
        # Le DXF dessine a l'echelle 1, mais la hauteur des textes est donnee
        # sur la feuille : on la ramene au modele via l'echelle de tirage,
        # celle-la meme que retiendraient les back-ends SVG et PDF.
        echelle = cadrer(dessin, A3).echelle
        document = ezdxf.new("R2010", setup=True)  # type: ignore[attr-defined]
        document.header["$INSUNITS"] = 4  # millimetres
        for calque, style in STYLES_IR.items():
            document.layers.add(name=calque.value, color=style.aci)
        espace = document.modelspace()

        for primitive in dessin.primitives:
            attributs = {"layer": primitive.calque.value}
            match primitive:
                case Rect():
                    coins = [
                        (primitive.x, primitive.y),
                        (primitive.x + primitive.dx, primitive.y),
                        (primitive.x + primitive.dx, primitive.y + primitive.dy),
                        (primitive.x, primitive.y + primitive.dy),
                    ]
                    espace.add_lwpolyline(coins, close=True, dxfattribs=attributs)
                case Trait():
                    espace.add_line(
                        (primitive.x1, primitive.y1),
                        (primitive.x2, primitive.y2),
                        dxfattribs=attributs,
                    )
                case Polyligne():
                    espace.add_lwpolyline(
                        primitive.points, close=primitive.ferme, dxfattribs=attributs
                    )
                case Texte():
                    # La hauteur du texte est donnee sur la feuille : on la
                    # ramene aux millimetres du modele via l'echelle de tirage.
                    hauteur = primitive.taille_mm * echelle
                    for i, ligne in enumerate(primitive.texte.split("\n")):
                        dy = -(i - (len(primitive.texte.split("\n")) - 1) / 2) * hauteur * 1.15
                        entite = espace.add_text(
                            ligne,
                            height=hauteur,
                            rotation=primitive.rotation,
                            dxfattribs=attributs,
                        )
                        entite.set_placement(
                            (primitive.x, primitive.y + dy),
                            align=ezdxf.enums.TextEntityAlignment[
                                {
                                    "LEFT": "MIDDLE_LEFT",
                                    "CENTER": "MIDDLE_CENTER",
                                    "RIGHT": "MIDDLE_RIGHT",
                                }[ALIGNEMENTS[primitive.ancrage]]
                            ],
                        )

        x0, _, _, y1 = dessin.emprise
        for i, ligne in enumerate((dessin.titre, dessin.sous_titre, MENTION)):
            if not ligne:
                continue
            entite = espace.add_text(
                ligne,
                height=(120 if i == 0 else 80) * (echelle / 50),
                dxfattribs={"layer": Calque.TEXTE.value},
            )
            entite.set_placement(
                (x0, y1 + (600 - i * 160) * (echelle / 50)),
                align=ezdxf.enums.TextEntityAlignment.MIDDLE_LEFT,
            )

        chemin = dossier / f"{index:02d}-{nom_de_fichier(dessin.titre)}.dxf"
        document.saveas(chemin)
        ecrits.append(chemin)
    return ecrits
