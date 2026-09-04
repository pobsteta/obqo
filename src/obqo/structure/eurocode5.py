"""Formules de l'EN 1995-1-1 : **des formules, pas des valeurs**.

Aucun nombre de norme ici — ils sont tous dans `materiaux.py`. Ce module ne
connait ni le bois, ni le vent, ni obqo : il prend des contraintes et rend des
taux de travail. C'est ce qui le rend relisible face au texte, article par
article, et testable a la main.

Un « taux » vaut 1 quand la sollicitation atteint la resistance : superieur a 1,
la verification n'est pas satisfaite. Toutes les fonctions rendent des taux, de
sorte que la note se lit d'une seule colonne.

Unites : N, mm, MPa. Pas d'exception, pas de kN.
"""

from __future__ import annotations

import math
from typing import NamedTuple


class Section(NamedTuple):
    """Section rectangulaire, vue dans **son plan de flexion**.

    `hauteur` est la dimension mesuree dans la direction de la charge : c'est
    elle qui est au cube dans l'inertie. Une meme piece a donc deux sections
    selon le plan regarde, et c'est voulu — se tromper de sens est l'erreur
    classique du calcul de poteau.
    """

    largeur: int
    hauteur: int

    @property
    def aire(self) -> float:
        return float(self.largeur * self.hauteur)

    @property
    def inertie(self) -> float:
        """Moment quadratique b h^3 / 12, mm4."""
        return self.largeur * self.hauteur**3 / 12

    @property
    def module_de_flexion(self) -> float:
        """Module de flexion b h^2 / 6, mm3."""
        return self.largeur * self.hauteur**2 / 6

    @property
    def rayon_de_giration(self) -> float:
        """i = h / racine(12), mm."""
        return self.hauteur / math.sqrt(12)


def resistance_de_calcul(f_k: float, k_mod: float, gamma_m: float) -> float:
    """(2.14) : X_d = k_mod * X_k / gamma_M."""
    return k_mod * f_k / gamma_m


def elancement(longueur_de_flambement: float, rayon_de_giration: float) -> float:
    """lambda = l_ef / i (§6.3.2)."""
    return longueur_de_flambement / rayon_de_giration


def elancement_relatif(lambda_: float, f_c_0_k: float, e_0_05: float) -> float:
    """(6.21) : lambda_rel = (lambda / pi) * racine(f_c,0,k / E_0,05)."""
    return lambda_ / math.pi * math.sqrt(f_c_0_k / e_0_05)


def coefficient_flambement(lambda_relatif: float, beta_c: float) -> float:
    """(6.25) a (6.29) : k_c, reduction de la resistance en compression.

    En dessous de 0,3 l'element est court : pas de flambement, k_c = 1.
    """
    if lambda_relatif <= 0.3:
        return 1.0
    k = 0.5 * (1 + beta_c * (lambda_relatif - 0.3) + lambda_relatif**2)
    return 1.0 / (k + math.sqrt(k**2 - lambda_relatif**2))


def taux_flexion(moment: float, module_de_flexion: float, f_m_d: float) -> float:
    """(6.11) : sigma_m,d / f_m,d, flexion simple selon un seul axe."""
    return moment / module_de_flexion / f_m_d


def taux_cisaillement(effort_tranchant: float, aire: float, f_v_d: float) -> float:
    """(6.13) avec tau_max = 1,5 V / A pour une section rectangulaire."""
    return 1.5 * effort_tranchant / aire / f_v_d


def taux_compression_flexion(
    effort_normal: float,
    aire: float,
    f_c_0_d: float,
    coefficient_de_flambement: float,
    moment: float,
    module_de_flexion: float,
    f_m_d: float,
) -> float:
    """(6.23) : sigma_c,d / (k_c f_c,0,d) + sigma_m,d / f_m,d, flexion composee.

    Le terme de compression n'est pas eleve au carre : c'est (6.23), le cas d'un
    element susceptible de flamber, et non (6.19) qui vaut pour un element court.
    """
    sigma_c = effort_normal / aire
    sigma_m = moment / module_de_flexion
    return sigma_c / (coefficient_de_flambement * f_c_0_d) + sigma_m / f_m_d


def taux_cheville(effort: float, nombre: float, resistance_de_calcul_unitaire: float) -> float:
    """Effort transmis rapporte a la resistance de l'ensemble des chevilles.

    Aucun coefficient d'effet de groupe n'est applique : avec une ou deux
    chevilles par rang la question ne se pose pas encore (§8.1.2 la pose des
    trois alignees dans le fil).
    """
    return effort / (nombre * resistance_de_calcul_unitaire)


def taux_fleche(fleche: float, portee: float, denominateur: float) -> float:
    """Fleche rapportee a la fleche admissible portee / denominateur."""
    return fleche * denominateur / portee
