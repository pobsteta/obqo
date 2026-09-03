"""Types internes du systeme constructif : ce que le moteur produit.

Immuables et sans dependance : c'est le modele que consommeront la nomenclature,
le metre et les dessins. Les identifiants sont **deterministes** (`M2.R07.B04`)
pour que deux executions produisent des sorties comparables octet pour octet.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import pairwise


class Ref(StrEnum):
    """References du catalogue de briques (paragraphe 1.4 du brief)."""

    B480_S = "480-S"
    B480_A = "480-A"
    B480_AA = "480-AA"
    B480_ANR = "480-ANR"
    B240_S = "240-S"
    B240_A = "240-A"
    B240_AA = "240-AA"
    B240_ANR = "240-ANR"

    @property
    def longueur(self) -> int:
        return 480 if self.value.startswith("480") else 240


@dataclass(frozen=True, slots=True)
class BriquePosee:
    mur: str
    rang: int
    u: int
    """Abscisse du debut de la brique le long de l'axe du mur, en mm."""
    ref: Ref
    about_debut_ferme: bool = False
    about_fin_ferme: bool = False
    angle: str | None = None
    """Identifiant du coin quand la brique est la filante d'angle."""

    @property
    def longueur(self) -> int:
        return self.ref.longueur

    @property
    def fin(self) -> int:
        return self.u + self.longueur

    @property
    def id(self) -> str:
        return f"{self.mur}.R{self.rang:02d}.U{self.u:05d}"


@dataclass(frozen=True, slots=True)
class ElementPose:
    """Piece de chantier posee : jambage, madrier, colonne de fermeture, lisse."""

    mur: str
    piece: str
    """Reference de la nomenclature : P8, P9, P10, LISSE."""
    u: int
    longueur: int
    rang: int | None = None
    quantite: int = 1
    role: str = ""
    ouverture: str | None = None


@dataclass(frozen=True, slots=True)
class Quincaillerie:
    """Pieces et chevilles posees au chantier (hors atelier de fabrication)."""

    mur: str
    rang: int
    u: int
    role: str
    pieces: tuple[tuple[str, int], ...] = ()
    """Couples (reference, quantite)."""


@dataclass(slots=True)
class Rang:
    mur: str
    indice: int
    debut: int
    """Abscisse de depart de la course du rang (0 ou 240 selon le harpage)."""
    fin: int
    briques: list[BriquePosee] = field(default_factory=list)
    elements: list[ElementPose] = field(default_factory=list)
    quincaillerie: list[Quincaillerie] = field(default_factory=list)

    @property
    def joints(self) -> list[int]:
        """Abscisses des joints verticaux interieurs entre briques contigues.

        Deux briques separees par une baie ne forment pas un joint.
        """
        return [b.u for a, b in pairwise(self.briques) if a.fin == b.u]


@dataclass(slots=True)
class MurCalepine:
    id: str
    depart: tuple[int, int]
    arrivee: tuple[int, int]
    longueur_hors_tout: int
    rangs: list[Rang] = field(default_factory=list)
    elements: list[ElementPose] = field(default_factory=list)
    interieur: bool = False
    poteaux: list[int] = field(default_factory=list)
    """Rives gauches des modules de 240 occupes par un poteau raidisseur.

    Le mur le dit lui-meme plutot que de laisser deduire la reponse des pieces
    posees : les dessins et les controles de couverture en ont besoin.
    """

    @property
    def briques(self) -> list[BriquePosee]:
        return [b for r in self.rangs for b in r.briques]


@dataclass(slots=True)
class Calepinage:
    nom: str
    murs: list[MurCalepine] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)

    @property
    def briques(self) -> list[BriquePosee]:
        return [b for m in self.murs for b in m.briques]

    def compte_briques(self) -> Counter[Ref]:
        return Counter(b.ref for b in self.briques)

    def compte_quincaillerie(self) -> Counter[str]:
        total: Counter[str] = Counter()
        for m in self.murs:
            for r in m.rangs:
                for q in r.quincaillerie:
                    for ref, n in q.pieces:
                        total[ref] += n
        return total

    def compte_elements(self) -> Counter[str]:
        total: Counter[str] = Counter()
        for m in self.murs:
            for e in m.elements:
                total[e.piece] += e.quantite
            for r in m.rangs:
                for e in r.elements:
                    total[e.piece] += e.quantite
        return total
