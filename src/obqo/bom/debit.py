"""Debit de matiere : du besoin en pieces au plan de decoupe des barres.

Le probleme est un cutting-stock 1D. Ici il est **petit et exactement soluble** :
les longueurs demandees sont peu nombreuses (80, 160, 240, 480 pour le carrelet),
si bien qu'on peut enumerer *tous* les patrons de decoupe d'une barre — 761 pour
une barre de 4 m a 4 mm de trait — puis resoudre un programme lineaire en nombres
entiers a l'optimum. C'est la formulation de Gilmore-Gomory sans generation de
colonnes, puisque les colonnes tiennent toutes en memoire.

Deux solveurs derriere la meme interface :

* `GloutonDecroissant` — sans aucune dependance, sert de repli et de reference
  de test. Best-fit decroissant : a complexite egale il domine le first-fit
  decroissant du brief.
* `CpSat` — exact, via OR-Tools. Objectif lexicographique en trois temps :
  minimiser les barres, puis le nombre de patrons distincts (un plan de debit
  optimal mais illisible est un mauvais plan de debit), puis maximiser la
  longueur des chutes reutilisables plutot que de la disperser en poussiere.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Literal, Protocol

PLAFOND_PATRONS = 40_000
"""Au-dela, l'enumeration exhaustive n'est plus raisonnable : repli sur le glouton."""


@dataclass(frozen=True, slots=True)
class Stock:
    """Une matiere premiere approvisionnee en barres d'une longueur donnee."""

    designation: str
    longueur_barre: int
    trait_de_scie: int = 4
    chute_minimale_reutilisable: int = 240

    def tient(self, longueurs: tuple[int, ...], nombres: tuple[int, ...]) -> bool:
        return self.occupe(longueurs, nombres) <= self.longueur_barre

    def occupe(self, longueurs: tuple[int, ...], nombres: tuple[int, ...]) -> int:
        """Longueur consommee par un patron, traits de scie compris."""
        pieces = sum(nombres)
        utile = sum(a * b for a, b in zip(longueurs, nombres, strict=True))
        return utile + self.trait_de_scie * max(0, pieces - 1)


@dataclass(frozen=True, slots=True)
class Patron:
    """Une facon de debiter une barre : combien de pieces de chaque longueur."""

    decoupe: tuple[tuple[int, int], ...]
    """Couples (longueur, nombre), tries par longueur decroissante."""

    @property
    def pieces(self) -> int:
        return sum(n for _, n in self.decoupe)

    @property
    def utile(self) -> int:
        return sum(longueur * n for longueur, n in self.decoupe)

    def chute(self, stock: Stock) -> int:
        longueurs, nombres = zip(*self.decoupe, strict=True) if self.decoupe else ((), ())
        return stock.longueur_barre - stock.occupe(longueurs, nombres)

    def __str__(self) -> str:
        return " + ".join(f"{n}x{longueur}" for longueur, n in self.decoupe)


@dataclass(frozen=True, slots=True)
class BarreDebitee:
    patron: Patron
    repetitions: int


@dataclass(slots=True)
class PlanDeDebit:
    """Un plan de decoupe, et ce qu'il produit vraiment.

    Le bois achete se repartit en **trois** categories, jamais deux :

    * `longueur_utile` — les pieces demandees par le calepinage ;
    * `surproduction` — les pieces en trop, d'une longueur demandee ailleurs.
      Elles sortent de la scie utilisables : ce sont des rechanges, pas de la
      perte. Un solveur qui remplit une barre entamee avec une piece de plus ne
      gaspille rien ;
    * `chute` — le fond de barre, seul vrai dechet.

    Confondre les deux dernieres masquerait le rendement reel : c'est exactement
    ce qui rend la loi des 80/L invisible.
    """

    stock: Stock
    barres: list[BarreDebitee] = field(default_factory=list)
    solveur: str = ""
    optimal: bool = False
    demandes: Counter[int] = field(default_factory=Counter)

    @property
    def nombre_de_barres(self) -> int:
        return sum(b.repetitions for b in self.barres)

    @property
    def patrons_distincts(self) -> int:
        return len(self.barres)

    @property
    def longueur_achetee(self) -> int:
        return self.nombre_de_barres * self.stock.longueur_barre

    @property
    def longueur_debitee(self) -> int:
        """Longueur de toutes les pieces sorties de la scie, utiles ou non."""
        return sum(b.patron.utile * b.repetitions for b in self.barres)

    @property
    def longueur_utile(self) -> int:
        """Longueur des seules pieces reellement demandees."""
        produit = self.produit()
        return sum(
            min(produit.get(longueur, 0), besoin) * longueur
            for longueur, besoin in self.demandes.items()
        )

    @property
    def surproduction(self) -> int:
        """Pieces en trop : utilisables en rechange, ce n'est pas de la chute."""
        return self.longueur_debitee - self.longueur_utile

    @property
    def pieces_en_trop(self) -> Counter[int]:
        produit = self.produit()
        return Counter(
            {
                longueur: n - self.demandes.get(longueur, 0)
                for longueur, n in produit.items()
                if n > self.demandes.get(longueur, 0)
            }
        )

    @property
    def chute(self) -> int:
        """Fond de barre : le seul vrai dechet."""
        return self.longueur_achetee - self.longueur_debitee

    @property
    def taux_de_chute(self) -> float:
        return self.chute / self.longueur_achetee if self.longueur_achetee else 0.0

    @property
    def chutes_reutilisables(self) -> int:
        """Longueur de chute assez longue pour resservir (une demi-brique au moins)."""
        seuil = self.stock.chute_minimale_reutilisable
        return sum(
            b.patron.chute(self.stock) * b.repetitions
            for b in self.barres
            if b.patron.chute(self.stock) >= seuil
        )

    def produit(self) -> Counter[int]:
        total: Counter[int] = Counter()
        for barre in self.barres:
            for longueur, n in barre.patron.decoupe:
                total[longueur] += n * barre.repetitions
        return total


class Solveur(Protocol):
    """Interface du solveur de debit, pour pouvoir en changer sans toucher au reste."""

    nom: str

    def resoudre(self, demandes: Counter[int], stock: Stock) -> PlanDeDebit: ...


# --- enumeration des patrons --------------------------------------------------


def patrons_maximaux(longueurs: tuple[int, ...], stock: Stock) -> list[Patron] | None:
    """Tous les patrons auxquels on ne peut plus rien ajouter.

    Retourne None si l'enumeration depasse le plafond : le probleme est trop
    varie pour la methode exacte, l'appelant se rabat sur le glouton.
    """
    trouves: set[tuple[int, ...]] = set()
    n = len(longueurs)

    def explorer(i: int, courant: tuple[int, ...]) -> bool:
        if len(trouves) > PLAFOND_PATRONS:
            return False
        if i == n:
            if sum(courant):
                trouves.add(courant)
            return True
        k = 0
        while stock.tient(longueurs, (*courant, k, *(0,) * (n - i - 1))):
            if not explorer(i + 1, (*courant, k)):
                return False
            k += 1
        return True

    if not explorer(0, ()):
        return None

    def maximal(c: tuple[int, ...]) -> bool:
        return not any(
            stock.tient(longueurs, tuple(x + (i == j) for j, x in enumerate(c))) for i in range(n)
        )

    return [
        Patron(
            tuple(sorted(((L, k) for L, k in zip(longueurs, c, strict=True) if k), reverse=True))
        )
        for c in sorted(trouves)
        if maximal(c)
    ]


# --- glouton sans dependance --------------------------------------------------


class GloutonDecroissant:
    """Best-fit decroissant sur les capacites restantes, groupees par valeur.

    Les longueurs distinctes etant peu nombreuses, les capacites restantes le
    sont aussi : on les compte au lieu de les lister, ce qui rend l'algorithme
    lineaire en nombre de pieces distinctes plutot qu'en nombre de pieces.
    """

    nom = "glouton decroissant"

    def resoudre(self, demandes: Counter[int], stock: Stock) -> PlanDeDebit:
        restant = Counter({L: n for L, n in demandes.items() if n > 0})
        longueurs = sorted(restant, reverse=True)
        patrons: Counter[tuple[tuple[int, int], ...]] = Counter()
        while restant:
            decoupe: Counter[int] = Counter()
            libre = stock.longueur_barre
            while True:
                for longueur in longueurs:
                    if restant.get(longueur, 0) <= 0:
                        continue
                    cout = longueur + (stock.trait_de_scie if sum(decoupe.values()) else 0)
                    if cout <= libre:
                        decoupe[longueur] += 1
                        restant[longueur] -= 1
                        if restant[longueur] == 0:
                            del restant[longueur]
                        libre -= cout
                        break
                else:
                    break
            if not decoupe:
                raise ValueError(
                    f"{stock.designation} : une piece de {longueurs[0]} mm ne tient pas "
                    f"dans une barre de {stock.longueur_barre} mm"
                )
            patrons[tuple(sorted(decoupe.items(), reverse=True))] += 1
        plan = PlanDeDebit(stock=stock, solveur=self.nom, optimal=False, demandes=Counter(demandes))
        plan.barres = [
            BarreDebitee(Patron(decoupe), n)
            for decoupe, n in sorted(patrons.items(), key=lambda kv: (-kv[1], kv[0]))
        ]
        return plan


# --- solveur exact ------------------------------------------------------------


class CpSat:
    """Optimum exact par programmation lineaire en nombres entiers (OR-Tools).

    Objectif lexicographique :
      1. minimiser le nombre de barres ;
      2. a barres egales, minimiser le nombre de patrons distincts ;
      3. a patrons egaux, maximiser la longueur des chutes reutilisables.
    """

    nom = "CP-SAT (exact)"

    def __init__(
        self,
        secondes_par_phase: float = 20.0,
        objectif: Literal["complet", "barres"] = "complet",
    ) -> None:
        self.secondes_par_phase = secondes_par_phase
        self.objectif = objectif

    def resoudre(self, demandes: Counter[int], stock: Stock) -> PlanDeDebit:
        from ortools.sat.python import cp_model

        besoins = {L: n for L, n in demandes.items() if n > 0}
        if not besoins:
            return PlanDeDebit(stock=stock, solveur=self.nom, optimal=True)
        longueurs = tuple(sorted(besoins, reverse=True))
        patrons = patrons_maximaux(longueurs, stock)
        if patrons is None:
            return GloutonDecroissant().resoudre(demandes, stock)

        plafond = sum(besoins.values())
        modele = cp_model.CpModel()
        x = [modele.new_int_var(0, plafond, f"x{i}") for i in range(len(patrons))]
        tables = [dict(p.decoupe) for p in patrons]
        for longueur, besoin in besoins.items():
            modele.add(
                sum(t.get(longueur, 0) * xi for t, xi in zip(tables, x, strict=True)) >= besoin
            )

        solveur = cp_model.CpSolver()
        # Un seul fil et une graine fixe : la recherche parallele de CP-SAT est
        # non deterministe et, a objectif egal, rendrait le plan de debit
        # different d'une execution a l'autre. Le probleme est assez petit pour
        # que ce soit gratuit, et la reproductibilite des livrables prime.
        solveur.parameters.num_workers = 1
        solveur.parameters.random_seed = 0

        etats: list[object] = []

        def resoudre_phase() -> bool:
            solveur.parameters.max_time_in_seconds = self.secondes_par_phase
            etats.append(solveur.solve(modele))
            return etats[-1] in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        modele.minimize(sum(x))
        if not resoudre_phase():
            return GloutonDecroissant().resoudre(demandes, stock)
        barres = int(solveur.objective_value)
        optimal = etats[-1] == cp_model.OPTIMAL

        if self.objectif == "complet":
            modele.add(sum(x) == barres)
            utilise = [modele.new_bool_var(f"y{i}") for i in range(len(patrons))]
            for xi, yi in zip(x, utilise, strict=True):
                modele.add(xi <= plafond * yi)
            modele.minimize(sum(utilise))
            if resoudre_phase():
                distincts = int(solveur.objective_value)
                modele.add(sum(utilise) == distincts)
                seuil = stock.chute_minimale_reutilisable
                chutes = [p.chute(stock) for p in patrons]
                modele.maximize(
                    sum(chute * xi for chute, xi in zip(chutes, x, strict=True) if chute >= seuil)
                )
                resoudre_phase()

        plan = PlanDeDebit(
            stock=stock, solveur=self.nom, optimal=optimal, demandes=Counter(besoins)
        )
        plan.barres = sorted(
            (
                BarreDebitee(p, solveur.value(xi))
                for p, xi in zip(patrons, x, strict=True)
                if solveur.value(xi) > 0
            ),
            key=lambda b: (-b.repetitions, b.patron.decoupe),
        )
        return plan


def solveur_par_defaut(secondes_par_phase: float = 20.0) -> Solveur:
    """CP-SAT si OR-Tools est installe, glouton sinon."""
    try:
        import ortools.sat.python.cp_model  # noqa: F401
    except ImportError:
        return GloutonDecroissant()
    return CpSat(secondes_par_phase=secondes_par_phase)
