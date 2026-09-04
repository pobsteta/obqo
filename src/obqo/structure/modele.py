"""Le schema statique : un grillage de rangs et de poteaux, resolu par PyNite.

**Repere** — X le long du mur, Y vertical, Z hors du plan du mur. Le vent
souffle selon Z, la toiture descend selon -Y.

**Le modele, en une phrase** : chaque rang de 240 est une poutre articulee sur
les deux poteaux, chaque poteau est une poutre continue du pied a la tete, et
les rangs deversent dans les poteaux ce que le vent leur applique.

* Un **rang** est une poutre 240 x 240 dont l'inertie hors plan est reduite par
  `efficacite_rang` : ce n'est pas un madrier plein mais une file de briques
  creuses aboutees. Elle est articulee aux deux bouts (rotation autour de Y
  liberee) et recoit le vent sur les 240 mm de sa propre hauteur.
* Un **poteau** est une poutre 80 x 240 d'un seul tenant, articulee en pied et
  tenue en tete par la lisse de chainage. Il recoit directement le vent de son
  propre module de 240, et **indirectement** les reactions de tous les rangs,
  qui arrivent par les noeuds partages : c'est la tout l'interet d'un grillage
  sur un calcul a la main.
* La **portee** de calcul est d'axe a axe des P10, soit `pan + MODULE_POTEAU`.
  Enveloppe : les 160 mm de remplissage du module sont chevilles au poteau et
  travaillent avec lui, mais rien ne le prouve tant que l'essai E3 du brief
  Code_Aster n'a pas mesure cette liaison.

Ce que le modele **ignore**, et qu'il faut savoir avant de le croire : le
chevillage vertical entre rangs (chaque rang est calcule seul, ce qui est
defavorable), l'effet de membrane du mur, le poids propre de la maconnerie, et
toute redistribution plastique. La critique complete est dans
`docs/etudes/structure.md`.

PyNite ne s'importe **qu'ici**, et a l'interieur de la fonction : lire les
tables de `materiaux` ne doit rien couter a une installation minimale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from obqo.structure.materiaux import CLASSES, COEFFICIENT_DE_POISSON, Hypotheses
from obqo.units import EPAISSEUR_MUR, GRILLE, HAUTEUR_RANG, LARGEUR_POTEAU, MODULE_POTEAU

VENT: Final[str] = "V"
"""Nom du cas de charge de vent."""

PERMANENT: Final[str] = "G"
"""Nom du cas de charge permanent (toiture, neige, plancher haut)."""

ELU: Final[str] = "ELU"
ELS: Final[str] = "ELS"

FACTEURS: Final[dict[str, dict[str, float]]] = {
    ELU: {VENT: 1.5, PERMANENT: 1.35},
    ELS: {VENT: 1.0},
}
"""Combinaisons. ELU dimensionne les sections, ELS la fleche.

Le vent est l'action variable de base et la charge verticale l'action
permanente : c'est la combinaison qui gouverne un mur de facade. Une
combinaison ou le vent soulagerait n'existe pas ici, la flexion etant
hors plan et la compression axiale.
"""

POINTS: Final[int] = 21
"""Nombre de points de lecture le long d'une poutre. Impair : le milieu en est."""


@dataclass(frozen=True, slots=True)
class Pan:
    """Un pan de maconnerie entre deux poteaux raidisseurs.

    `longueur` est la maconnerie nue, sans les modules de poteau qui l'encadrent
    — c'est la grandeur que le paragraphe 1.7 plafonne a 6 m, et celle que
    `engine/raidissement.py` decoupe. Toujours un multiple de 240.
    """

    longueur: int
    hauteur: int
    """Hauteur sous chainage, multiple de 240."""
    mur: str = ""
    """Identifiant du mur d'ou vient le pan, pour la note. Vide si abstrait."""

    def __post_init__(self) -> None:
        for nom, valeur in (("longueur", self.longueur), ("hauteur", self.hauteur)):
            if valeur <= 0 or valeur % GRILLE:
                raise ValueError(f"{nom} {valeur} mm : multiple positif de {GRILLE} attendu")

    @property
    def portee(self) -> int:
        """Portee d'axe a axe des poteaux, mm."""
        return self.longueur + MODULE_POTEAU

    @property
    def rangs(self) -> int:
        return self.hauteur // HAUTEUR_RANG


@dataclass(frozen=True, slots=True)
class Efforts:
    """Ce que le grillage rend, en N et en mm. Enveloppes sur tous les rangs.

    Les efforts sont a l'ELU, les fleches a l'ELS : c'est ainsi qu'on les
    compare, et melanger les deux est l'erreur qui fait passer un mur qui ne
    passe pas.
    """

    moment_rang: float
    """Moment de flexion hors plan maximal d'un rang, N.mm (ELU)."""
    tranchant_rang: float
    """Effort tranchant maximal d'un rang, N (ELU)."""
    reaction_rang: float
    """Effort qu'un rang transmet a un poteau, N (ELU) — ce que les C1 reprennent."""
    fleche_rang: float
    """Fleche relative maximale d'un rang, mm (ELS)."""
    moment_poteau: float
    """Moment de flexion hors plan maximal d'un poteau, N.mm (ELU)."""
    normal_poteau: float
    """Compression maximale d'un poteau, N (ELU)."""
    fleche_poteau: float
    """Fleche relative maximale d'un poteau, mm (ELS)."""


def _enveloppe(valeurs: Any) -> float:
    """Plus grande valeur absolue le long d'une barre.

    PyNite rend un tableau a deux lignes — les abscisses, puis les valeurs — et
    c'est la seconde qui nous interesse.
    """
    return max(abs(float(v)) for v in valeurs[1])


def calculer(pan: Pan, hyp: Hypotheses) -> Efforts:
    """Monte le grillage, le resout, et rend les enveloppes d'efforts.

    Leve `ImportError` si l'extra « structure » n'est pas installe : c'est a
    l'appelant de le dire proprement a l'utilisateur.
    """
    from Pynite import FEModel3D

    bois = CLASSES[hyp.classe]
    modele = FEModel3D()
    modele.add_material("bois", bois.e_0_mean, bois.g_mean, COEFFICIENT_DE_POISSON, 0.0)

    # Sections. PyNite plie autour de l'axe local y sous une charge selon Z :
    # c'est donc Iy qui porte l'inertie hors plan, celle qui nous interesse.
    inertie_rang = EPAISSEUR_MUR * HAUTEUR_RANG**3 / 12
    modele.add_section(
        "rang",
        float(EPAISSEUR_MUR * HAUTEUR_RANG),
        inertie_rang * hyp.efficacite_rang,
        inertie_rang,
        0.141 * float(EPAISSEUR_MUR) ** 4,
    )
    modele.add_section(
        "poteau",
        float(LARGEUR_POTEAU * EPAISSEUR_MUR),
        LARGEUR_POTEAU * EPAISSEUR_MUR**3 / 12,
        EPAISSEUR_MUR * LARGEUR_POTEAU**3 / 12,
        0.229 * float(EPAISSEUR_MUR) * float(LARGEUR_POTEAU) ** 3,
    )

    portee = float(pan.portee)
    cotes = {"G": 0.0, "D": portee}

    # Un noeud par rang et par poteau, a mi-hauteur du rang : c'est la que le
    # chevillage transmet, et c'est la que la poutre-rang doit s'appuyer.
    for cote, x in cotes.items():
        modele.add_node(f"pied{cote}", x, 0.0, 0.0)
        for i in range(1, pan.rangs + 1):
            modele.add_node(f"{cote}{i:02d}", x, float(i * HAUTEUR_RANG - HAUTEUR_RANG // 2), 0.0)
        modele.add_node(f"tete{cote}", x, float(pan.hauteur), 0.0)
        modele.add_member(f"poteau{cote}", f"pied{cote}", f"tete{cote}", "bois", "poteau")
        # Pied articule, tete tenue lateralement par la lisse de chainage.
        modele.def_support(f"pied{cote}", True, True, True, False, True, False)
        modele.def_support(f"tete{cote}", True, False, True, False, False, False)

    rangs = [f"rang{i:02d}" for i in range(1, pan.rangs + 1)]
    for i, nom in enumerate(rangs, start=1):
        modele.add_member(nom, f"G{i:02d}", f"D{i:02d}", "bois", "rang")
        modele.def_releases(nom, Ryi=True, Ryj=True)

    # Vent : chaque poutre le recoit sur sa propre bande tributaire.
    vent = hyp.pression_vent / 1000  # kN/m2 -> N/mm2
    for nom in rangs:
        modele.add_member_dist_load(nom, "FZ", vent * HAUTEUR_RANG, vent * HAUTEUR_RANG, case=VENT)
    for cote in cotes:
        modele.add_member_dist_load(
            f"poteau{cote}", "FZ", vent * MODULE_POTEAU, vent * MODULE_POTEAU, case=VENT
        )
        # Toiture : le poteau en reprend `part_poteau`, sur toute sa portee.
        descente = hyp.charge_verticale * hyp.part_poteau * portee  # kN/m * mm = N
        modele.add_node_load(f"tete{cote}", "FY", -descente, case=PERMANENT)

    for nom, facteurs in FACTEURS.items():
        modele.add_load_combo(nom, dict(facteurs))
    modele.analyze(check_statics=False)

    def barres(noms: list[str]) -> list[Any]:
        return [modele.members[nom] for nom in noms]

    rangs_poses = barres(rangs)
    poteaux_poses = barres([f"poteau{c}" for c in cotes])
    return Efforts(
        moment_rang=max(_enveloppe(m.moment_array("My", POINTS, ELU)) for m in rangs_poses),
        tranchant_rang=max(_enveloppe(m.shear_array("Fz", POINTS, ELU)) for m in rangs_poses),
        # Ce qu'un rang deverse dans un poteau : le tranchant a son propre about,
        # et c'est exactement ce que les chevilles C1 doivent reprendre.
        reaction_rang=max(
            abs(float(m.shear("Fz", x, ELU))) for m in rangs_poses for x in (0.0, portee)
        ),
        fleche_rang=max(_enveloppe(m.rel_deflection_array("dz", POINTS, ELS)) for m in rangs_poses),
        moment_poteau=max(_enveloppe(m.moment_array("My", POINTS, ELU)) for m in poteaux_poses),
        normal_poteau=max(_enveloppe(m.axial_array(POINTS, ELU)) for m in poteaux_poses),
        fleche_poteau=max(
            _enveloppe(m.rel_deflection_array("dz", POINTS, ELS)) for m in poteaux_poses
        ),
    )
