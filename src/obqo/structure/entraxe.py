"""La verification, et la note qu'on tend au bureau d'etudes.

`verifier` confronte les efforts du grillage aux resistances de l'Eurocode 5 et
rend un taux de travail par critere. `entraxe_maxi` cherche le plus long pan
admissible. `note` met le tout en francais, hypotheses en tete — parce qu'une
note de calcul dont on ne voit pas les hypotheses ne vaut rien.

Un taux vaut 1 quand la sollicitation atteint la resistance. Le **critere
dimensionnant** est celui dont le taux est le plus grand : c'est lui, et lui
seul, qui commande l'entraxe. Le dire evite la lecture magique d'un resultat.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from obqo.engine.geometrie import squelette
from obqo.engine.raidissement import pans_maconnes
from obqo.model.plan import Plan
from obqo.model.systeme import Calepinage, MurCalepine
from obqo.structure.eurocode5 import (
    Section,
    coefficient_flambement,
    elancement,
    elancement_relatif,
    resistance_de_calcul,
    taux_cheville,
    taux_cisaillement,
    taux_compression_flexion,
    taux_fleche,
    taux_flexion,
)
from obqo.structure.materiaux import BETA_C, CLASSES, GAMMA_M, Hypotheses, k_mod
from obqo.structure.modele import Efforts, Pan, calculer
from obqo.units import APPUI_LINTEAU, EPAISSEUR_MUR, GRILLE, HAUTEUR_RANG, LARGEUR_POTEAU

FLEXION_RANG = "flexion du rang"
CISAILLEMENT_RANG = "cisaillement du rang"
FLECHE_RANG = "fleche du rang"
POTEAU = "compression et flexion du poteau"
FLECHE_POTEAU = "fleche du poteau"
CHEVILLAGE = "chevillage rang-poteau"

HAUTEUR_PAR_DEFAUT = 2640
"""Hauteur sous chainage a defaut de plan : 11 rangs, celle des exemples."""

PLAFOND_MODULES = 100
"""Borne de la recherche d'entraxe : 24 m, au-dela le probleme a change de nature."""


@dataclass(frozen=True, slots=True)
class Verification:
    """Le verdict sur un pan : un taux par critere, et lequel commande."""

    pan: Pan
    efforts: Efforts
    taux: dict[str, float] = field(default_factory=dict)

    @property
    def critere(self) -> str:
        """Critere dimensionnant. A egalite, le premier dans l'ordre de la table."""
        return max(self.taux, key=lambda nom: self.taux[nom])

    @property
    def taux_maxi(self) -> float:
        return self.taux[self.critere]

    @property
    def admis(self) -> bool:
        return self.taux_maxi <= 1.0


def verifier(pan: Pan, hyp: Hypotheses) -> Verification:
    """Calcule le pan et confronte chaque effort a sa resistance de calcul."""
    efforts = calculer(pan, hyp)
    bois = CLASSES[hyp.classe]
    kmod = k_mod(hyp.classe_de_service, hyp.duree_du_vent)
    gamma_bois = GAMMA_M["bois massif"]

    f_m_d = resistance_de_calcul(bois.f_m_k, kmod, gamma_bois)
    f_v_d = resistance_de_calcul(bois.f_v_k, kmod, gamma_bois)
    f_c_0_d = resistance_de_calcul(bois.f_c_0_k, kmod, gamma_bois)

    # Le rang : meme efficacite sur la raideur (dans le modele) et sur la
    # resistance (ici). Si l'essai E2 les separe, ce parametre se dedouble.
    rang = Section(EPAISSEUR_MUR, HAUTEUR_RANG)
    efficacite = hyp.efficacite_rang

    # Le poteau flambe hors plan sur toute sa hauteur ; dans le plan du mur, la
    # maconnerie le tient a chaque rang, sa longueur de flambement n'est que 240.
    poteau_hors_plan = Section(LARGEUR_POTEAU, EPAISSEUR_MUR)
    poteau_dans_le_plan = Section(EPAISSEUR_MUR, LARGEUR_POTEAU)
    k_c = min(
        coefficient_flambement(
            elancement_relatif(
                elancement(longueur, section.rayon_de_giration), bois.f_c_0_k, bois.e_0_05
            ),
            BETA_C,
        )
        for longueur, section in (
            (float(pan.hauteur), poteau_hors_plan),
            (float(HAUTEUR_RANG), poteau_dans_le_plan),
        )
    )

    f_cheville_d = resistance_de_calcul(
        hyp.resistance_cheville_k * 1000, kmod, GAMMA_M["assemblage"]
    )

    taux = {
        FLEXION_RANG: taux_flexion(efforts.moment_rang, rang.module_de_flexion, f_m_d * efficacite),
        CISAILLEMENT_RANG: taux_cisaillement(efforts.tranchant_rang, rang.aire, f_v_d * efficacite),
        FLECHE_RANG: taux_fleche(efforts.fleche_rang, pan.portee, hyp.fleche_admissible),
        POTEAU: taux_compression_flexion(
            efforts.normal_poteau,
            poteau_hors_plan.aire,
            f_c_0_d,
            k_c,
            efforts.moment_poteau,
            poteau_hors_plan.module_de_flexion,
            f_m_d,
        ),
        FLECHE_POTEAU: taux_fleche(efforts.fleche_poteau, pan.hauteur, hyp.fleche_admissible),
        CHEVILLAGE: taux_cheville(efforts.reaction_rang, hyp.chevilles_par_rang, f_cheville_d),
    }
    return Verification(pan=pan, efforts=efforts, taux=taux)


def entraxe_maxi(hyp: Hypotheses, hauteur: int) -> int:
    """Plus long pan de maconnerie admissible, en mm, multiple de 240.

    Rend 0 si meme un pan d'un seul module ne passe pas — auquel cas ce n'est
    plus l'entraxe qu'il faut revoir mais le systeme.

    La recherche est un balayage croissant : les taux augmentent avec la portee
    sur toute la plage utile, mais rien ne le **prouve** — la compression du
    poteau croit avec la portee tandis que son coefficient de flambement n'en
    depend pas — et un balayage ne suppose rien. Il coute une trentaine de
    resolutions de quelques millisecondes.
    """
    dernier = 0
    for modules in range(1, PLAFOND_MODULES + 1):
        pan = Pan(longueur=modules * GRILLE, hauteur=hauteur)
        if not verifier(pan, hyp).admis:
            return dernier
        dernier = pan.longueur
    return dernier


def _hypotheses_en_lignes(hyp: Hypotheses) -> list[str]:
    return [
        "Hypotheses",
        f"  bois                     {hyp.classe}, classe de service {hyp.classe_de_service}, "
        f"vent en duree {hyp.duree_du_vent} (k_mod = "
        f"{k_mod(hyp.classe_de_service, hyp.duree_du_vent):.2f})",
        f"  pression de vent         {hyp.pression_vent:.2f} kN/m2 (entree du bureau d'etudes)",
        f"  charge verticale         {hyp.charge_verticale:.2f} kN/m, dont "
        f"{100 * hyp.part_poteau:.0f} % au poteau",
        f"  efficacite d'un rang     {hyp.efficacite_rang:.2f} (essai E2 — le parametre "
        "le plus incertain)",
        f"  resistance d'une C1      {hyp.resistance_cheville_k:.2f} kN (essai E1), "
        f"{hyp.chevilles_par_rang} par rang, lu au catalogue",
        f"  fleche admissible        portee / {hyp.fleche_admissible}",
    ]


def note(v: Verification, hyp: Hypotheses) -> list[str]:
    """La note de calcul d'un pan, ligne a ligne, sans couleur ni dependance."""
    lignes = _hypotheses_en_lignes(hyp)
    lignes += [
        "",
        f"Pan{' ' + v.pan.mur if v.pan.mur else ''} : maconnerie {v.pan.longueur} mm, "
        f"portee d'axe a axe {v.pan.portee} mm, hauteur {v.pan.hauteur} mm "
        f"({v.pan.rangs} rangs)",
        "",
        "Taux de travail",
    ]
    for nom, taux in v.taux.items():
        marque = "  <-- dimensionnant" if nom == v.critere else ""
        lignes.append(f"  {nom:<34} {taux:5.2f}{marque}")
    lignes += [
        "",
        f"Verdict : {'admis' if v.admis else 'REFUSE'} (taux maxi {v.taux_maxi:.2f} — {v.critere})",
        "",
        "Document de calepinage — dimensionnement structural a valider par un",
        "bureau d'etudes bois (Eurocode 5, sismique). Cette note est une",
        "argumentation, pas une preuve : voir docs/etudes/structure.md.",
    ]
    return lignes


# --- Note d'un plan reel -------------------------------------------------------


def _tremies(mur: MurCalepine) -> list[tuple[int, int]]:
    """Emprises des baies du mur, lues sur les madriers de linteau poses.

    Le madrier deborde de l'appui de 240 de chaque cote : la tremie est ce qui
    reste entre les deux appuis. On le lit sur le calepinage plutot que sur le
    plan, parce que la validation a pu recaler une baie sur la grille.
    """
    return sorted(
        (e.u + APPUI_LINTEAU, e.u + e.longueur - APPUI_LINTEAU)
        for e in mur.elements
        if e.piece in ("P9", "P9-LC")
    )


def pans_du_plan(plan: Plan, calepinage: Calepinage) -> list[Pan]:
    """Tous les pans de maconnerie **exterieurs** d'un plan calepine.

    Les refends ne recoivent pas de vent : ils sont ecartes ici, et la note le
    dit plutot que de le taire. Leur descente de charge verticale releverait
    d'un autre calcul, que ce module ne fait pas.
    """
    ancrages = squelette(plan).ancrages
    pans: list[Pan] = []
    for mur in calepinage.murs:
        if mur.interieur:
            continue
        for a, b in pans_maconnes(
            mur.longueur_hors_tout, _tremies(mur), mur.poteaux, ancrages.get(mur.id, [])
        ):
            pans.append(
                Pan(
                    longueur=b - a,
                    hauteur=plan.hauteur_sous_chainage,
                    mur=f"{mur.id} [{a}-{b}]",
                )
            )
    return pans


def note_du_plan(
    verifications: list[Verification], hyp: Hypotheses, refends: list[str]
) -> list[str]:
    """La note d'un plan entier : les hypotheses, puis un pan par ligne."""
    lignes = _hypotheses_en_lignes(hyp)
    lignes += [
        "",
        f"{'pan':<22} {'maconnerie':>11} {'portee':>8} "
        f"{'critere dimensionnant':<34} {'taux':>6}  verdict",
    ]
    for v in verifications:
        lignes.append(
            f"{v.pan.mur:<22} {v.pan.longueur:>8} mm {v.pan.portee:>5} mm "
            f"{v.critere:<34} {v.taux_maxi:>6.2f}  {'admis' if v.admis else 'REFUSE'}"
        )
    refuses = [v for v in verifications if not v.admis]
    lignes += [
        "",
        f"{len(verifications)} pans exterieurs verifies, {len(refuses)} refuse(s).",
    ]
    if refends:
        lignes.append(
            f"Murs interieurs non verifies (aucun vent sur un refend) : {', '.join(refends)}."
        )
    lignes += [
        "",
        "Document de calepinage — dimensionnement structural a valider par un",
        "bureau d'etudes bois (Eurocode 5, sismique). Cette note est une",
        "argumentation, pas une preuve : voir docs/etudes/structure.md.",
    ]
    return lignes
