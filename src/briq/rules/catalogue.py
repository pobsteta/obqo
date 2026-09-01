"""Regles metier du systeme BRIQ : **des tables, pas des algorithmes**.

Ce module est fait pour etre relu ligne a ligne face au brief. Il ne contient
aucune logique de placement : uniquement la composition des briques, des
assemblages et les constantes de metre. Le jour ou une regle d'atelier change,
on modifie ici une table, pas une fonction du moteur.
"""

from __future__ import annotations

from collections import Counter
from typing import Final, NamedTuple

from briq.model.systeme import Ref


class Piece(NamedTuple):
    """Une piece de la nomenclature (paragraphe 1.3 du brief)."""

    ref: str
    designation: str
    largeur: int
    hauteur: int
    longueur: int | None
    """None = longueur variable, fixee a la pose (P9, P10, lisse)."""


PIECES: Final[dict[str, Piece]] = {
    p.ref: p
    for p in (
        Piece("P1", "bois couche traversant perce", 80, 80, 240),
        Piece("P2", "bois couche traversant", 80, 80, 240),
        Piece("P3", "ame", 80, 80, 480),
        Piece("P4", "montant bois debout", 80, 80, 240),
        Piece("P5", "tenon", 80, 80, 160),
        Piece("P5-A", "tenon d'angle", 80, 80, 160),
        Piece("P6", "remplissage central / raccord inter-briques", 80, 80, 160),
        Piece("P7", "ame courte", 80, 80, 240),
        Piece("P8", "carre de fermeture", 80, 80, 80),
        Piece("P9", "madrier de linteau", 80, 240, None),
        Piece("P10", "jambage / poteau raidisseur", 80, 240, None),
        Piece("LISSE", "lisse de chainage haut", 80, 240, None),
        Piece("C1", "cheville traversante hetre", 20, 20, 230),
        Piece("C2", "cheville de verrouillage de tenon", 20, 20, 230),
        Piece("C3", "pige hetre", 20, 20, 40),
    )
}

# --- Composition atelier des briques -----------------------------------------
# Paragraphe 1.2 (BRIQ 480) et 1.4 (demi-brique 240). Les quantites sont celles
# de la brique nue, abouts ouverts.

CORPS_480: Final[Counter[str]] = Counter(
    {
        "P1": 4,  # lignes 3-4, couches 1 et 3
        "P2": 4,  # lignes 1 et 6, couches 1 et 3
        "P3": 1,  # ame traversante 480, couche 2
        "P4": 4,  # montants lignes 2 et 5, sur les deux parements
        "P6": 2,  # remplissages couche 2, lignes 3-4
        "P5": 2,  # tenons lignes 2 et 5
        "C1": 10,  # 6 verticales + 4 traversantes de montants
        "C2": 2,  # verrouillage des tenons, posees par le rang superieur
        "C3": 16,  # piges de jonction traversants / montants
    }
)

CORPS_240: Final[Counter[str]] = Counter(
    {
        "P2": 4,  # lignes 1 et 3, couches 1 et 3
        "P4": 2,  # montants ligne 2
        "P7": 1,  # ame courte
        "P5": 1,  # tenon unique ligne 2
        "C1": 2,  # traversantes de l'ame courte (40 / 200)
        "C2": 1,
        "C3": 10,  # 8 jonctions + 2 piges laterales de l'ame courte
    }
)

FERMETURE_ABOUT: Final[Counter[str]] = Counter({"P8": 2, "C1": 1})
"""Fermeture d'un about : un carre P8 par parement, verrouilles par une cheville."""

ANGLE_FILANTE: Final[Counter[str]] = Counter({"P5-A": 1, "P5": -1, "P8": -1})
"""480-ANR = 480-A, un tenon devient un P5-A, un carre est omis (mortaise de flanc)."""


def composition(ref: Ref) -> Counter[str]:
    """Pieces et chevilles d'atelier d'une brique du catalogue."""
    base = Counter(CORPS_480 if ref.longueur == 480 else CORPS_240)
    suffixe = ref.value.split("-", 1)[1]
    abouts = {"S": 0, "A": 1, "AA": 2, "ANR": 1}[suffixe]
    for _ in range(abouts):
        base.update(FERMETURE_ABOUT)
    if suffixe == "ANR":
        base.update(ANGLE_FILANTE)
    if any(n < 0 for n in base.values()):
        raise ValueError(f"composition negative pour {ref.value} : {base}")
    return Counter({r: n for r, n in base.items() if n})


# --- Assemblages de chantier --------------------------------------------------

JOINT_COURANT: Final[Counter[str]] = Counter({"P6": 2, "C1": 2})
"""Paragraphe 1.2 : 2 raccords a cheval sur le joint, 1 cheville par brique."""

ANGLE_PAR_RANG: Final[Counter[str]] = Counter({"P6": 1, "P8": 1, "C1": 2})
"""Paragraphe 1.5 et critere d'acceptation 2.5 : 1 raccord, 1 carre, 2 chevilles
par rang d'angle (le P5-A est compte dans la brique 480-ANR filante)."""

LINTEAU_PAR_MONTANT: Final[Counter[str]] = Counter({"P4": 1, "C1": 2})
"""Paragraphe 1.6 : chaque montant du linteau est cousu par 2 chevilles."""

CHAINAGE_PAR_BRIQUE: Final[Counter[str]] = Counter({"C1": 2})
"""Paragraphe 1.7 : lisse de chainage chevillee au dernier rang, 2 par brique."""

RAIDISSEUR_PAR_RANG: Final[Counter[str]] = Counter({"C1": 1})
"""Paragraphe 1.7 : poteau raidisseur cheville en travers a chaque rang."""


# --- Constantes de metre du brief (paragraphe 1.8) ----------------------------
# Conservees telles quelles pour servir de **controle croise** : le moteur
# recalcule ces valeurs a partir des tables ci-dessus et un test compare.


class Reference(NamedTuple):
    carrelet_ml: float
    hetre_ml: float
    masse_kg: float
    pieces_bois: int
    chevilles_atelier: int


REFERENCE_BRIEF: Final[dict[int, Reference]] = {
    480: Reference(4.16, 3.65, 12.3, 21, 28),
    240: Reference(1.84, 1.30, 6.2, 8, 13),
}


def longueur_carrelet(pieces: Counter[str]) -> int:
    """Metres lineaires de carrelet 80x80 pour un lot de pieces, en mm."""
    return sum(
        n * longueur
        for r, n in pieces.items()
        if (longueur := PIECES[r].longueur) is not None
        and (PIECES[r].largeur, PIECES[r].hauteur) == (80, 80)
    )


def longueur_hetre(pieces: Counter[str]) -> int:
    """Metres lineaires de rond de hetre 20 mm, en mm."""
    return sum(
        n * longueur
        for r, n in pieces.items()
        if (longueur := PIECES[r].longueur) is not None and PIECES[r].largeur == 20
    )


def compte_pieces_bois(pieces: Counter[str]) -> int:
    """Nombre de pieces bois (hors chevilles hetre)."""
    return sum(n for r, n in pieces.items() if PIECES[r].largeur != 20)
