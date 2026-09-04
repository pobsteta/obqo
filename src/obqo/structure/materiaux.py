"""Valeurs de norme et hypotheses de calcul : **des tables, pas des formules**.

Ce module est fait pour etre relu ligne a ligne face aux normes, comme
`rules/catalogue.py` se relit face au brief. Aucune valeur numerique de norme
ne doit apparaitre ailleurs : `eurocode5.py` ne contient que des formules,
`modele.py` que le schema statique.

Deux natures de valeurs cohabitent ici, et il ne faut jamais les confondre :

* **CLASSES, K_MOD, GAMMA_M, BETA_C** viennent des normes. Un numero de tableau
  accompagne chacune. Personne ne les change, sauf changement de norme.
* **Hypotheses** porte ce qu'aucune norme ne donne pour un mur de briques de
  bois chevillees. Chaque defaut est prudent, et son docstring dit d'ou il
  vient et quel essai le remplacera.

Les textes eux-memes ne sont pas dans le depot et ne peuvent pas y etre :
voir `docs/normes.md`. **Cette table est une transcription, a recontroler
contre l'edition en vigueur avant d'etre presentee a un bureau d'etudes.**
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, NamedTuple

from obqo.rules.catalogue import RAIDISSEUR_PAR_RANG


class Bois(NamedTuple):
    """Une classe de resistance, EN 338 tableau 1. Contraintes en MPa (N/mm2)."""

    classe: str
    f_m_k: float
    """Flexion, valeur caracteristique."""
    f_t_0_k: float
    """Traction axiale."""
    f_c_0_k: float
    """Compression axiale."""
    f_c_90_k: float
    """Compression transversale (portance)."""
    f_v_k: float
    """Cisaillement."""
    e_0_mean: float
    """Module axial moyen — pour les fleches (ELS)."""
    e_0_05: float
    """Module axial au fractile 5 % — pour le flambement (ELU)."""
    g_mean: float
    """Module de cisaillement moyen."""
    rho_k: float
    """Masse volumique caracteristique, kg/m3."""
    rho_mean: float
    """Masse volumique moyenne, kg/m3."""


CLASSES: Final[dict[str, Bois]] = {
    b.classe: b
    for b in (
        Bois("C18", 18.0, 11.0, 18.0, 2.2, 3.4, 9000.0, 6000.0, 560.0, 320.0, 380.0),
        Bois("C24", 24.0, 14.5, 21.0, 2.5, 4.0, 11000.0, 7400.0, 690.0, 350.0, 420.0),
        Bois("C30", 30.0, 19.0, 24.0, 2.7, 4.0, 12000.0, 8000.0, 750.0, 380.0, 460.0),
        Bois("D30", 30.0, 18.0, 23.0, 8.0, 3.9, 11000.0, 9200.0, 690.0, 530.0, 640.0),
    )
}
"""EN 338 tableau 1 (resineux C) et tableau 2 (feuillus D).

C24 est l'epicea de charpente courant, celui que le brief suppose. D30 n'est la
que pour chiffrer un hetre : la cheville n'est **pas** justifiee par l'Eurocode 5
(voir `docs/etudes/structure.md`), cette ligne sert d'ordre de grandeur.
"""

CLASSE_PAR_DEFAUT: Final[str] = "C24"
"""Epicea de charpente : l'essence et la qualite que suppose le brief."""

GAMMA_M: Final[dict[str, float]] = {
    "bois massif": 1.3,
    "assemblage": 1.3,
}
"""EN 1995-1-1 tableau 2.3, coefficients partiels sur la propriete de materiau."""

K_MOD: Final[dict[tuple[int, str], float]] = {
    (1, "permanente"): 0.60,
    (1, "long terme"): 0.70,
    (1, "moyen terme"): 0.80,
    (1, "court terme"): 0.90,
    (1, "instantanee"): 1.10,
    (2, "permanente"): 0.60,
    (2, "long terme"): 0.70,
    (2, "moyen terme"): 0.80,
    (2, "court terme"): 0.90,
    (2, "instantanee"): 1.10,
    (3, "permanente"): 0.50,
    (3, "long terme"): 0.55,
    (3, "moyen terme"): 0.65,
    (3, "court terme"): 0.70,
    (3, "instantanee"): 0.90,
}
"""EN 1995-1-1 tableau 3.1, bois massif : (classe de service, duree) -> k_mod."""

BETA_C: Final[float] = 0.2
"""EN 1995-1-1 (6.29), bois massif : defaut de rectitude pris en compte."""

DUREES: Final[tuple[str, ...]] = (
    "permanente",
    "long terme",
    "moyen terme",
    "court terme",
    "instantanee",
)
"""Classes de duree de charge, de la plus longue a la plus courte (tableau 2.2)."""


def k_mod(classe_de_service: int, duree: str) -> float:
    """Coefficient de duree de charge et d'humidite (tableau 3.1)."""
    try:
        return K_MOD[(classe_de_service, duree)]
    except KeyError:
        raise ValueError(
            f"classe de service {classe_de_service} et duree {duree!r} : "
            f"attendu 1, 2 ou 3 et l'une de {', '.join(DUREES)}"
        ) from None


@dataclass(frozen=True, slots=True)
class Hypotheses:
    """Tout ce qu'aucune norme ne donne pour un mur de briques chevillees.

    Chaque defaut est **prudent** et remplacable par un essai. Aucune de ces
    valeurs n'est une verite : ce sont les entrees que le bureau d'etudes signe
    ou conteste, et la note les imprime toujours en tete.
    """

    classe: str = CLASSE_PAR_DEFAUT
    """Classe de resistance du bois d'ossature, EN 338."""

    classe_de_service: int = 2
    """EN 1995-1-1 §2.3.1.3. Classe 2 : sous abri, humidite du bois < 20 %.

    Un mur exterieur de bois massif protege par un debord de toiture est en
    classe 2 ; en classe 3 (exposition directe) le k_mod tombe et l'entraxe
    avec lui.
    """

    duree_du_vent: str = "court terme"
    """Classe de duree de la charge de vent (tableau 2.2).

    L'EN 1991-1-4 range le vent en « instantanee » (k_mod = 1,1) ; l'usage
    francais le calcule le plus souvent en « court terme » (0,9). Le defaut
    prend le cas defavorable ; le passer a « instantanee » releve l'entraxe
    d'environ 10 %.
    """

    pression_vent: float = 0.8
    """Pression de vent de calcul sur le parement, kN/m2, valeur caracteristique.

    **Entree du bureau d'etudes.** Le module ne calcule pas le vent selon
    l'EN 1991-1-4 (zone, rugosite, altitude, hauteur du batiment) : 0,8 kN/m2
    est un ordre de grandeur courant en zone 2, hauteur courante, et rien de
    plus.
    """

    charge_verticale: float = 5.0
    """Charge descendante en tete de mur, kN par metre de mur, caracteristique.

    Toiture, neige et plancher haut confondus. Ordre de grandeur d'une toiture
    de maison en zone de neige courante ; a remplacer par la descente de charges
    reelle.
    """

    part_poteau: float = 0.5
    """Part de la charge verticale que le poteau reprend, le reste allant au mur.

    Le P10 est plus raide que la maconnerie chevillee qui l'entoure et attire
    donc plus que sa part geometrique (80 sur 240, soit un tiers). La moitie est
    une majoration prudente ; l'essai E4 du brief Code_Aster la mesurerait.
    """

    efficacite_rang: float = 0.3
    """Part de l'inertie et de la resistance d'un bloc plein qu'atteint un rang.

    Un rang de 240 x 240 n'est pas un madrier plein : c'est une file de briques
    creuses, aboutees par deux raccords P6 chevilles. Sa raideur et sa
    resistance en flexion hors plan valent une fraction de celles de la section
    brute. **C'est le parametre le plus incertain de tout le module, et c'est
    lui qui commande l'entraxe.** L'essai E2 du brief Code_Aster le mesure ;
    l'attendu annonce est 0,1 a 0,4, le defaut prend le haut de la fourchette
    parce que le rang est ici pris seul, sans les rangs voisins qui le
    raidissent.
    """

    resistance_cheville_k: float = 3.0
    """Resistance caracteristique d'une cheville C1 en double cisaillement, kN.

    **Pas une valeur d'Eurocode.** L'EN 1995-1-1 §8 traite les tiges en acier ;
    une cheville de hetre de 20 mm casse en cisaillement de son propre bois bien
    avant. 3 kN est une borne basse tiree du cisaillement du hetre, a remplacer
    par l'essai E1 du brief Code_Aster (attendu 3 a 8 kN).
    """

    chevilles_par_rang: int = field(
        default_factory=lambda: int(RAIDISSEUR_PAR_RANG["C1"]),
    )
    """Nombre de C1 liant un rang au poteau raidisseur.

    **Lu dans le catalogue, jamais duplique** : le nombre de chevilles est une
    regle d'atelier, elle vit dans `rules/catalogue.py`. Changer le catalogue
    change le calcul, et un test le verrouille.
    """

    fleche_admissible: int = 250
    """Denominateur de la fleche admissible : la portee divisee par ce nombre.

    L'EN 1995-1-1 tableau 7.2 donne des fourchettes, pas des seuils : L/300 a
    L/500 pour une poutre de plancher, plus souple pour un element de facade.
    L/250 est l'usage pour un remplissage sous vent, ou c'est la menuiserie et
    l'etancheite a l'air qui commandent, non la ruine.
    """


COEFFICIENT_DE_POISSON: Final[float] = 0.4
"""nu_LT du bois resineux. Absent de l'EN 338 : Kollmann, Bodig & Jayne.

Sans effet sur les resultats de ce module — le modele est un grillage de
poutres, ou seuls E et G interviennent — mais PyNite demande la valeur.
"""
