"""Validation du plan : ce qui est refusable avant tout calcul.

Le systeme constructif n'est pas negociable. Quand une situation du plan ne peut
pas respecter les regles, l'application le signale ; elle n'improvise pas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from itertools import pairwise

from obqo.engine.raidissement import coupures as points_raidisseurs
from obqo.engine.raidissement import positions_manquantes
from obqo.model.plan import Ouverture, Plan
from obqo.units import (
    ENTRAXE_MAXI_RAIDISSEUR,
    GRILLE,
    HAUTEUR_MINI_PASSAGE,
    HAUTEUR_RANG,
    MODULE_POTEAU,
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
    courses: dict[str, list[tuple[int, int]]] | None = None,
) -> tuple[Rapport, list[Ouverture], dict[str, list[int]]]:
    """Valide le plan, normalise les ouvertures et arrete les poteaux raidisseurs.

    Les poteaux rendus sont ceux du plan **plus** ceux que l'application ajoute
    la ou un pan de mur depasse l'entraxe du paragraphe 1.7. Les arreter ici
    plutot qu'ailleurs evite de parcourir deux fois les memes coupures.
    """
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

    for identifiant, rangs in (courses or {}).items():
        for indice, (debut, fin) in enumerate(rangs):
            if fin - debut < GRILLE:
                rapport.ajouter(
                    Gravite.ERREUR,
                    "MUR-TROP-COURT",
                    identifiant,
                    f"au rang {indice}, le harpage ne laisse que {fin - debut} mm de "
                    f"maconnerie : un mur doit garder au moins {GRILLE} mm de course "
                    "a tous les rangs",
                )
                break

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
            # La hauteur d'une tremie est le passage libre vertical : rien ne
            # vient s'y ajouter, contrairement aux jambages en largeur.
            if o.type in ("porte", "porte_fenetre") and o.hauteur < HAUTEUR_MINI_PASSAGE:
                rapport.ajouter(
                    Gravite.AVERTISSEMENT,
                    "PASSAGE-TROP-BAS",
                    ou,
                    f"tremie de {o.hauteur} mm de haut pour une {o.type.replace('_', '-')} : "
                    f"on ne passe plus debout en dessous de {HAUTEUR_MINI_PASSAGE} mm "
                    "(l'usage est 2160)",
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
    poteaux = _raidir(plan, rapport, longueurs_murs, par_mur, ancrages or {})
    return rapport, normalisees, poteaux


def _poteaux_declares(
    plan: Plan,
    rapport: Rapport,
    longueurs_murs: dict[str, int],
    par_mur: dict[str, list[Ouverture]],
) -> dict[str, list[int]]:
    """Controle les poteaux poses a la main et les range par mur."""
    declares: dict[str, list[int]] = {}
    for poteau in plan.poteaux:
        ou = f"{poteau.mur}/{poteau.id}"
        longueur = longueurs_murs.get(poteau.mur)
        if longueur is None:
            rapport.ajouter(Gravite.ERREUR, "MUR-INCONNU", ou, f"le mur {poteau.mur} n'existe pas")
            continue
        if not sur_grille(poteau.position):
            rapport.ajouter(
                Gravite.ERREUR,
                "HORS-GRILLE",
                ou,
                f"position = {poteau.position} mm n'est pas un multiple de {GRILLE} mm",
            )
            continue
        # Un poteau colle a un angle prendrait la place de la brique filante du
        # harpage : on lui laisse un module de degagement de chaque cote.
        if poteau.position < GRILLE or poteau.fin > longueur - GRILLE:
            rapport.ajouter(
                Gravite.ERREUR,
                "POTEAU-EN-ANGLE",
                ou,
                f"module {poteau.position}-{poteau.fin} mm sur un mur de {longueur} mm : "
                f"laisser {GRILLE} mm de degagement a chaque extremite, la brique "
                "filante du harpage y passe",
            )
            continue
        for o in par_mur.get(poteau.mur, []):
            if poteau.position < o.fin and o.position < poteau.fin:
                rapport.ajouter(
                    Gravite.ERREUR,
                    "POTEAU-DANS-BAIE",
                    ou,
                    f"le module {poteau.position}-{poteau.fin} mm recouvre la baie "
                    f"{o.id} ({o.position}-{o.fin} mm)",
                )
                break
        else:
            declares.setdefault(poteau.mur, []).append(poteau.position)
    return declares


def _raidir(
    plan: Plan,
    rapport: Rapport,
    longueurs_murs: dict[str, int],
    par_mur: dict[str, list[Ouverture]],
    ancrages: dict[str, list[int]],
) -> dict[str, list[int]]:
    """Poteaux par mur : ceux du plan, puis ceux que l'application ajoute."""
    declares = _poteaux_declares(plan, rapport, longueurs_murs, par_mur)
    poteaux: dict[str, list[int]] = {}
    for identifiant, longueur in longueurs_murs.items():
        poses = sorted(declares.get(identifiant, []))
        bornes = [u for o in par_mur.get(identifiant, []) for u in (o.position, o.fin)]
        bornes += [u for p in poses for u in (p, p + MODULE_POTEAU)]
        ajoutes = positions_manquantes(longueur, bornes, ancrages.get(identifiant, []))
        if ajoutes:
            rapport.ajouter(
                Gravite.HYPOTHESE,
                "POTEAU-AJOUTE",
                identifiant,
                f"{len(ajoutes)} poteau(x) raidisseur(s) P10 ajoute(s) a "
                + ", ".join(f"{u} mm" for u in ajoutes)
                + f" : au-dela de {ENTRAXE_MAXI_RAIDISSEUR} mm sans baie ni refend, "
                "le paragraphe 1.7 en demande un. Chacun occupe un module de 240 "
                "entre deux abouts fermes ; posez-en dans le plan pour choisir "
                "vous-meme leur place",
            )
        poteaux[identifiant] = sorted(poses + ajoutes)
        # Filet de securite : la repartition doit toujours ramener chaque pan
        # sous l'entraxe. Si ce constat sort un jour, c'est le calcul qui a tort.
        bornes += [u for p in ajoutes for u in (p, p + MODULE_POTEAU)]
        for a, b in pairwise(points_raidisseurs(longueur, bornes, ancrages.get(identifiant, []))):
            if b - a > ENTRAXE_MAXI_RAIDISSEUR:
                rapport.ajouter(
                    Gravite.ERREUR,
                    "RAIDISSEUR-MANQUANT",
                    identifiant,
                    f"{b - a} mm de mur sans baie ni refend entre {a} et {b} mm : "
                    f"{ENTRAXE_MAXI_RAIDISSEUR} mm maximum",
                )
    return poteaux
