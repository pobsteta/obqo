"""Etude : quelle longueur d'approvisionnement pour le carrelet 80x80 ?

Resout exactement (Gilmore-Gomory : enumeration des patrons + ILP CP-SAT) le
probleme de debit pour une demande realiste, en balayant les longueurs de barre.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

LONGUEURS = (80, 160, 240, 480)


def patrons_maximaux(barre: int, trait: int) -> list[tuple[int, ...]]:
    """Tous les patrons de decoupe auxquels on ne peut plus rien ajouter."""
    trouves: set[tuple[int, ...]] = set()

    def tient(c: tuple[int, ...]) -> bool:
        n = sum(c)
        utile = sum(a * b for a, b in zip(LONGUEURS, c, strict=True))
        return utile + trait * max(0, n - 1) <= barre

    def explorer(i: int, courant: tuple[int, ...]) -> None:
        if i == len(LONGUEURS):
            if sum(courant):
                trouves.add(courant)
            return
        k = 0
        while tient((*courant, k, *(0,) * (len(LONGUEURS) - i - 1))):
            explorer(i + 1, (*courant, k))
            k += 1

    explorer(0, ())
    return [
        c
        for c in trouves
        if not any(
            tient(tuple(x + (i == j) for j, x in enumerate(c))) for i in range(len(LONGUEURS))
        )
    ]


def resoudre(barre: int, trait: int, demande: dict[int, int]) -> tuple[int, int, int]:
    """Retourne (barres, patrons distincts utilises, chute totale en mm)."""
    patrons = patrons_maximaux(barre, trait)
    m = cp_model.CpModel()
    plafond = sum(demande.values())
    x = [m.new_int_var(0, plafond, f"p{i}") for i in range(len(patrons))]
    for j, L in enumerate(LONGUEURS):
        m.add(sum(p[j] * xi for p, xi in zip(patrons, x, strict=True)) >= demande.get(L, 0))
    m.minimize(sum(x))
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = 30.0
    s.parameters.num_workers = 8
    assert s.solve(m) in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    barres = int(s.objective_value)
    distincts = sum(1 for xi in x if s.value(xi) > 0)
    utile = sum(
        s.value(xi) * sum(a * b for a, b in zip(LONGUEURS, p, strict=True))
        for p, xi in zip(patrons, x, strict=True)
    )
    return barres, distincts, barres * barre - utile


# Demande representative d'une maison ~1000 briques 480 + 100 demis 240,
# derivee de la structure du paragraphe 1.2 du brief.
DEMANDE = {240: 12_700, 480: 1_000, 160: 6_100, 80: 300}

if __name__ == "__main__":
    besoin = sum(L * n for L, n in DEMANDE.items())
    print(f"Demande : {DEMANDE}")
    print(f"Bois strictement necessaire : {besoin / 1000:.1f} m lineaires\n")
    for trait in (0, 4):
        print(f"--- trait de scie = {trait} mm ---")
        entete = f"{'barre':>7} {'patrons':>8} {'barres':>8}"
        print(f"{entete} {'achete m':>10} {'chute':>8} {'chute %':>8}")
        for barre in (2400, 3000, 3600, 4000, 4200, 4800, 5000, 5400, 6000):
            n, distincts, chute = resoudre(barre, trait, DEMANDE)
            achete = n * barre
            print(
                f"{barre:>7} {len(patrons_maximaux(barre, trait)):>8} {n:>8} "
                f"{achete / 1000:>10.1f} {chute / 1000:>7.1f}m {100 * chute / achete:>7.2f}%"
            )
        print()
