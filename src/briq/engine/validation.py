"""Validation du plan : ce qui est refusable avant tout calcul.

Le systeme constructif n'est pas negociable. Quand une situation du plan ne peut
pas respecter les regles, l'application le signale ; elle n'improvise pas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from itertools import pairwise

from briq.model.plan import Ouverture, Plan
from briq.units import (
    ENTRAXE_MAXI_RAIDISSEUR,
    GRILLE,
    HAUTEUR_RANG,
    PORTEE_MAXI_LINTEAU,
    RECUL_MINI_BAIE_ANGLE,
    sur_grille,
)


class Gravite(StrEnum):
    ERREUR = "erreur"
    AVERTISSEMENT = "avertissement"
    HYPOTHESE = "hypothese"


@dataclass(frozen=True, slots=True)
class Constat:
    gravite: Gravite
    code: str
    ou: str
    message: str

    def __str__(self) -> str:
        return f"[{self.gravite.value}] {self.code} — {self.ou} : {self.message}"


@dataclass(slots=True)
class Rapport:
    constats: list[Constat] = field(default_factory=list)

    def ajouter(self, gravite: Gravite, code: str, ou: str, message: str) -> None:
        self.constats.append(Constat(gravite, code, ou, message))

    @property
    def erreurs(self) -> list[Constat]:
        return [c for c in self.constats if c.gravite is Gravite.ERREUR]

    @property
    def avertissements(self) -> list[Constat]:
        return [c for c in self.constats if c.gravite is Gravite.AVERTISSEMENT]

    @property
    def valide(self) -> bool:
        return not self.erreurs


def _cale(valeur: int) -> int:
    """Arrondit a la grille de 240 la plus proche."""
    return round(valeur / GRILLE) * GRILLE


def normaliser_ouverture(o: Ouverture, mode: str, rapport: Rapport) -> Ouverture:
    """Verifie (ou recale) les cotes d'une baie sur la grille de 240."""
    corrections: dict[str, int] = {}
    for champ in ("position", "largeur", "allege", "hauteur"):
        valeur = getattr(o, champ)
        if sur_grille(valeur):
            continue
        if mode == "arrondir":
            corrections[champ] = _cale(valeur)
            rapport.ajouter(
                Gravite.AVERTISSEMENT,
                "HORS-GRILLE-RECALE",
                f"{o.mur}/{o.id}",
                f"{champ} {valeur} mm recale a {corrections[champ]} mm (multiple de {GRILLE})",
            )
        else:
            rapport.ajouter(
                Gravite.ERREUR,
                "HORS-GRILLE",
                f"{o.mur}/{o.id}",
                f"{champ} = {valeur} mm n'est pas un multiple de {GRILLE} mm",
            )
    return o.model_copy(update=corrections) if corrections else o


def valider(
    plan: Plan,
    longueurs_murs: dict[str, int],
    ancrages: dict[str, list[int]] | None = None,
) -> tuple[Rapport, list[Ouverture]]:
    """Valide le plan et retourne le rapport et les ouvertures normalisees."""
    rapport = Rapport()
    mode = plan.parametres.hors_grille

    # --- contour ---------------------------------------------------------
    sommets = plan.contour.sommets()
    for i, (x, y) in enumerate(sommets):
        suivant = sommets[(i + 1) % len(sommets)]
        if x != suivant[0] and y != suivant[1]:
            rapport.ajouter(
                Gravite.ERREUR,
                "ANGLE-NON-DROIT",
                f"contour/{i}",
                f"le segment {(x, y)} -> {suivant} n'est ni horizontal ni vertical "
                "(la version 1 ne traite que les angles a 90 degres)",
            )
    for identifiant, longueur in longueurs_murs.items():
        if not sur_grille(longueur):
            rapport.ajouter(
                Gravite.ERREUR,
                "MUR-HORS-GRILLE",
                identifiant,
                f"longueur {longueur} mm : multiple de {GRILLE} mm attendu "
                "(le contour n'est jamais recale automatiquement, un arrondi "
                "romprait sa fermeture)",
            )

    # --- ouvertures ------------------------------------------------------
    normalisees: list[Ouverture] = []
    par_mur: dict[str, list[Ouverture]] = {}
    for o in plan.ouvertures:
        if o.mur not in longueurs_murs:
            rapport.ajouter(Gravite.ERREUR, "MUR-INCONNU", o.id, f"le mur « {o.mur} » n'existe pas")
            continue
        o = normaliser_ouverture(o, mode, rapport)
        normalisees.append(o)
        par_mur.setdefault(o.mur, []).append(o)

    for identifiant, ouvertures in par_mur.items():
        longueur = longueurs_murs[identifiant]
        for o in sorted(ouvertures, key=lambda x: x.position):
            ou = f"{identifiant}/{o.id}"
            if o.fin > longueur:
                rapport.ajouter(
                    Gravite.ERREUR,
                    "BAIE-DEBORDANTE",
                    ou,
                    f"la baie finit a {o.fin} mm, au-dela du mur ({longueur} mm)",
                )
            recul_gauche, recul_droit = o.position, longueur - o.fin
            for cote, recul in (("gauche", recul_gauche), ("droite", recul_droit)):
                if recul < RECUL_MINI_BAIE_ANGLE:
                    rapport.ajouter(
                        Gravite.ERREUR,
                        "BAIE-TROP-PRES-ANGLE",
                        ou,
                        f"rive {cote} a {recul} mm de l'angle : "
                        f"{RECUL_MINI_BAIE_ANGLE} mm minimum "
                        "(240 d'appui de linteau + 240 de maconnerie)",
                    )
            if o.largeur > PORTEE_MAXI_LINTEAU:
                rapport.ajouter(
                    Gravite.AVERTISSEMENT,
                    "PORTEE-EXCESSIVE",
                    ou,
                    f"portee de {o.largeur} mm > {PORTEE_MAXI_LINTEAU} mm : "
                    "linteau cheville impossible, l'application prescrit un "
                    "lamelle-colle du commerce aux memes cotes",
                )
            haut = o.allege + o.hauteur + HAUTEUR_RANG
            if haut > plan.hauteur_sous_chainage:
                rapport.ajouter(
                    Gravite.ERREUR,
                    "BAIE-TROP-HAUTE",
                    ou,
                    f"allege + baie + linteau = {haut} mm depasse la hauteur "
                    f"sous chainage ({plan.hauteur_sous_chainage} mm)",
                )
        ordonnees = sorted(ouvertures, key=lambda x: x.position)
        for gauche, droite in pairwise(ordonnees):
            # Deux baies doivent laisser un trumeau capable de porter les deux
            # appuis de linteau (240 + 240) sans se recouvrir.
            if droite.position - gauche.fin < 2 * 240:
                rapport.ajouter(
                    Gravite.ERREUR,
                    "TRUMEAU-INSUFFISANT",
                    f"{identifiant}/{gauche.id}-{droite.id}",
                    f"trumeau de {droite.position - gauche.fin} mm entre les deux "
                    "baies : 480 mm minimum pour les deux appuis de linteau",
                )

    # --- raidissement ----------------------------------------------------
    for identifiant, longueur in longueurs_murs.items():
        coupures = sorted(
            [0]
            + [u for o in par_mur.get(identifiant, []) for u in (o.position, o.fin)]
            + list((ancrages or {}).get(identifiant, []))
            + [longueur]
        )
        for a, b in pairwise(coupures):
            if b - a > ENTRAXE_MAXI_RAIDISSEUR:
                rapport.ajouter(
                    Gravite.ERREUR,
                    "RAIDISSEUR-MANQUANT",
                    identifiant,
                    f"{b - a} mm de mur sans baie ni refend entre {a} et {b} mm : "
                    f"{ENTRAXE_MAXI_RAIDISSEUR} mm maximum, ajouter un refend, "
                    "une baie ou un poteau raidisseur P10",
                )

    return rapport, normalisees
