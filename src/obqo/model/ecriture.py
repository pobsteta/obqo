"""Ecriture d'une esquisse en YAML commente, pour la garder et la rouvrir.

Le YAML plutot que le JSON pour la meme raison qu'a la saisie d'un plan : on
veut pouvoir relire son travail, et y ajouter une note a cote d'une cote.
"""

from __future__ import annotations

from obqo.model.esquisse import Esquisse

LIBELLES = {"porte": "porte", "fenetre": "fenetre", "porte_fenetre": "porte-fenetre"}

CARACTERES_A_PROTEGER = set(":#{}[],&*?|<>=!%@`\"'")
"""Un nom de piece contenant l'un d'eux casserait un scalaire YAML nu."""


def texte(valeur: str) -> str:
    """Rend une chaine sure en YAML : quotee des qu'elle peut prêter a confusion."""
    nu = valeur.strip()
    if not nu or nu != valeur or CARACTERES_A_PROTEGER & set(valeur) or nu[0] == "-":
        return "'" + valeur.replace("'", "''") + "'"
    return valeur


def esquisse_en_yaml(esquisse: Esquisse) -> str:
    """Rend l'esquisse sous une forme relisible et rechargeable."""
    lignes = [
        "# Esquisse BRIQ — rouvrable depuis l'onglet « Esquisse » d'obqo web.",
        "# Les pieces se touchent : chaque ligne partagee est un axe de mur.",
        "# Les baies sont posees sur ces axes, decrites par le segment qu'elles",
        "# occupent. Toutes les cotes sont en millimetres.",
        f"nom: {texte(esquisse.nom)}",
        f"hauteur_sous_chainage: {esquisse.hauteur_sous_chainage}",
        "pieces:",
    ]
    for piece in esquisse.pieces:
        lignes.append(
            f"  - {{nom: {texte(piece.nom)}, x: {piece.x}, y: {piece.y}, "
            f"largeur: {piece.largeur}, hauteur: {piece.hauteur}}}"
        )
    if esquisse.baies:
        lignes.append("baies:")
        for baie in esquisse.baies:
            passage = baie.largeur - (320 if baie.largeur > 1800 else 160)
            allege = f", allege: {baie.allege}"
            lignes.append(
                f"  - {{id: {texte(baie.id)}, type: {baie.type}, "
                f"depart: [{baie.depart[0]}, {baie.depart[1]}], "
                f"arrivee: [{baie.arrivee[0]}, {baie.arrivee[1]}]{allege}, "
                f"hauteur: {baie.hauteur}}}"
                f"   # {LIBELLES[baie.type]}, tremie {baie.largeur}, "
                f"passage libre {passage}"
            )
    return "\n".join(lignes) + "\n"
