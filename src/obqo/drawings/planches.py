"""Construction des planches : elevations, plans de pose, instructions."""

from __future__ import annotations

from obqo.drawings.ir import (
    Ancrage,
    Calque,
    Dessin,
    Polyligne,
    Rect,
    Texte,
    Trait,
    coter_horizontal,
    coter_vertical,
)
from obqo.drawings.mise_en_page import paginer
from obqo.model.plan import Ouverture, Plan
from obqo.model.systeme import BriquePosee, Calepinage, MurCalepine
from obqo.units import (
    EPAISSEUR_MUR,
    HAUTEUR_RANG,
    LONGUEUR_BRIQUE,
)

HAUTEUR_LISSE = 80


def calque_de(brique: BriquePosee) -> Calque:
    if brique.angle is not None:
        return Calque.ANGLE
    if brique.ref.longueur != LONGUEUR_BRIQUE:
        return Calque.DEMI
    if brique.about_debut_ferme or brique.about_fin_ferme:
        return Calque.ABOUT
    return Calque.BRIQUE


def _repere(brique: BriquePosee) -> str:
    """Suffixe court porte sur la brique : S est laisse vide, c'est le courant."""
    suffixe = brique.ref.value.split("-", 1)[1]
    return "" if suffixe == "S" else suffixe


def _tenons(brique: BriquePosee) -> tuple[int, ...]:
    """Abscisses des tenons d'une brique posee (lignes 2 et 5)."""
    if brique.ref.longueur == LONGUEUR_BRIQUE:
        return (brique.u + 120, brique.u + 360)
    return (brique.u + 120,)


def elevation(mur: MurCalepine, plan: Plan, ouvertures: list[Ouverture]) -> Dessin:
    """Elevation d'un mur : briques reperees, baies, linteaux, chainage, cotes."""
    dessin = Dessin(
        titre=f"Elevation du mur {mur.id}",
        sous_titre=(
            f"{plan.nom} — longueur hors tout {mur.longueur_hors_tout} mm, "
            f"{len(mur.rangs)} rangs, hauteur sous chainage {plan.hauteur_sous_chainage} mm"
        ),
    )

    for rang in mur.rangs:
        y = rang.indice * HAUTEUR_RANG
        for brique in rang.briques:
            dessin.ajouter(Rect(brique.u, y, brique.longueur, HAUTEUR_RANG, calque_de(brique)))
            if repere := _repere(brique):
                dessin.ajouter(
                    Texte(
                        brique.u + brique.longueur / 2,
                        y + HAUTEUR_RANG / 2,
                        repere,
                        Calque.REPERE,
                        taille_mm=1.6,
                    )
                )
            for x in _tenons(brique):
                dessin.ajouter(Trait(x, y + HAUTEUR_RANG - 40, x, y + HAUTEUR_RANG, Calque.TENON))
        dessin.ajouter(
            Texte(-160, y + HAUTEUR_RANG / 2, f"R{rang.indice:02d}", Calque.REPERE, taille_mm=2.0)
        )

    for o in ouvertures:
        bas, haut = o.allege, o.allege + o.hauteur
        dessin.ajouter(
            Rect(o.position, bas, o.largeur, o.hauteur, Calque.BAIE),
            Texte(
                o.position + o.largeur / 2,
                bas + o.hauteur / 2,
                f"{o.id}\n{o.largeur} x {o.hauteur}",
                Calque.TEXTE,
                taille_mm=2.2,
            ),
        )
        for element in mur.elements:
            if element.ouverture != o.id:
                continue
            if element.piece == "P10":
                dessin.ajouter(
                    Rect(element.u, bas, 80 * element.quantite, o.hauteur, Calque.JAMBAGE)
                )
            elif element.piece in ("P9", "P9-LC"):
                dessin.ajouter(
                    Rect(element.u, haut, element.longueur, HAUTEUR_RANG, Calque.LINTEAU),
                    Texte(
                        element.u + element.longueur / 2,
                        haut + HAUTEUR_RANG / 2,
                        f"2 x {element.piece} {element.longueur}",
                        Calque.TEXTE,
                        taille_mm=2.0,
                    ),
                )
        coter_horizontal(dessin, o.position, o.fin, -420)

    sommet = len(mur.rangs) * HAUTEUR_RANG
    dessin.ajouter(
        Rect(0, sommet, mur.longueur_hors_tout, HAUTEUR_LISSE, Calque.CHAINAGE),
        Texte(
            mur.longueur_hors_tout / 2,
            sommet + HAUTEUR_LISSE + 130,
            f"lisse de chainage 80x240 — {mur.longueur_hors_tout} mm",
            Calque.TEXTE,
            taille_mm=2.2,
        ),
    )

    coter_horizontal(dessin, 0, mur.longueur_hors_tout, -700)
    coter_vertical(dessin, 0, sommet, -560)
    dessin.legende = [(c.value, c) for c in dessin.calques_de_legende()]
    return dessin


def _repere_global(mur: MurCalepine) -> tuple[tuple[int, int], tuple[int, int]]:
    """Vecteur directeur et normale interieure d'un mur, en unites entieres."""
    (x0, y0), (x1, y1) = mur.depart, mur.arrivee
    dx = (x1 > x0) - (x1 < x0)
    dy = (y1 > y0) - (y1 < y0)
    return (dx, dy), (-dy, dx)  # contour orient dans le sens trigonometrique


def plan_de_rang(calepinage: Calepinage, plan: Plan, rang: int) -> Dessin:
    """Vue de dessus du niveau a un rang donne : angles, refends, baies."""
    dessin = Dessin(
        titre=f"Plan de pose — rang {rang:02d}",
        sous_titre=(
            f"{plan.nom} — altitude {rang * HAUTEUR_RANG} mm, "
            f"vue de dessus, murs de {EPAISSEUR_MUR} mm"
        ),
    )
    for mur in calepinage.murs:
        (dx, dy), (nx, ny) = _repere_global(mur)
        # Le contour est le nu exterieur : le mur s'epaissit vers l'interieur.
        # Un refend est en revanche centre sur son axe.
        v0 = -EPAISSEUR_MUR // 2 if mur.interieur else 0
        for brique in mur.rangs[rang].briques:
            a = (
                mur.depart[0] + dx * brique.u + nx * v0,
                mur.depart[1] + dy * brique.u + ny * v0,
            )
            coins = [
                a,
                (a[0] + dx * brique.longueur, a[1] + dy * brique.longueur),
                (
                    a[0] + dx * brique.longueur + nx * EPAISSEUR_MUR,
                    a[1] + dy * brique.longueur + ny * EPAISSEUR_MUR,
                ),
                (a[0] + nx * EPAISSEUR_MUR, a[1] + ny * EPAISSEUR_MUR),
            ]
            calque = Calque.REFEND if mur.interieur else calque_de(brique)
            dessin.ajouter(Polyligne(tuple(coins), calque, ferme=True))
        # Repere pose a l'exterieur du batiment pour les murs de facade, et
        # decale lateralement pour un refend, qui n'a pas de dehors.
        milieu = mur.longueur_hors_tout / 2
        recul = 400 if mur.interieur else -400
        dessin.ajouter(
            Texte(
                mur.depart[0] + dx * milieu + nx * (EPAISSEUR_MUR / 2 + v0 + recul),
                mur.depart[1] + dy * milieu + ny * (EPAISSEUR_MUR / 2 + v0 + recul),
                mur.id,
                Calque.TEXTE,
                taille_mm=3.0,
            )
        )
    dessin.legende = [(c.value, c) for c in dessin.calques_de_legende()]
    return dessin


def instructions(calepinage: Calepinage, plan: Plan) -> Dessin:
    """Page d'instructions de pose, generee depuis le modele."""
    lignes: list[str] = [
        f"INSTRUCTIONS DE POSE — {plan.nom}",
        "",
        f"{len(calepinage.briques)} briques, {len(calepinage.murs)} murs, "
        f"{plan.rangs} rangs de {HAUTEUR_RANG} mm.",
        "",
        "ORDRE DE POSE",
        "  1. Lisse basse d'ancrage sur le soubassement, sur tout le perimetre.",
        "  2. Rang par rang, de R00 au dernier rang, en commencant chaque rang par",
        "     l'angle du mur filant : le mur filant change a chaque rang (harpage",
        "     croise alterne).",
        "  3. A chaque rang, poser d'abord les briques d'angle, puis remplir vers",
        "     le milieu du mur. La demi-brique de 240 se pose en fin de course.",
        "  4. Refends en butee : le mur exterieur file toujours (regle D2).",
        "  5. Lisse de chainage haut sur le dernier rang, 2 chevilles par brique.",
        "",
        "MUR FILANT PAR ANGLE ET PAR RANG",
    ]
    coins: dict[str, list[str]] = {}
    for mur in calepinage.murs:
        for rang in mur.rangs:
            for q in rang.quincaillerie:
                if q.role.startswith("angle "):
                    coins.setdefault(q.role.removeprefix("angle "), []).append(
                        f"R{rang.indice:02d}:{mur.id}"
                    )
    for coin in sorted(coins):
        filants = coins[coin][:6]
        lignes.append(
            f"  {coin} : " + "  ".join(filants) + ("  ..." if len(coins[coin]) > 6 else "")
        )

    lignes += ["", "CHEVILLES DE POSE PAR RANG (hors atelier)"]
    for mur in calepinage.murs:
        total: dict[str, int] = {}
        for rang in mur.rangs:
            for q in rang.quincaillerie:
                for ref, n in q.pieces:
                    total[ref] = total.get(ref, 0) + n
        detail = ", ".join(f"{n} x {ref}" for ref, n in sorted(total.items()))
        lignes.append(f"  {mur.id} : {detail}")

    # Un tenon sans reception au rang superieur n'a rien a tenir : il se
    # trouve sous une baie ou hors de l'emprise d'un linteau, et se coupe a ras
    # (paragraphe 1.6). La liste est **calculee** sur la geometrie reelle des
    # pieces, pas deduite de la position des baies.
    from obqo.drawings.volume import tenons_sans_reception

    orphelins = tenons_sans_reception(calepinage)
    lignes += ["", f"TENONS A COUPER A RAS ({len(orphelins)})"]
    par_mur_rang: dict[tuple[str, int], list[int]] = {}
    for identifiant, indice, u in orphelins:
        par_mur_rang.setdefault((identifiant, indice), []).append(u)
    for (identifiant, indice), abscisses in sorted(par_mur_rang.items()):
        lignes.append(
            f"  {identifiant} rang R{indice:02d} : u = "
            + ", ".join(str(u) for u in sorted(abscisses))
            + " mm"
        )
    if not orphelins:
        lignes.append("  aucun")

    if calepinage.avertissements:
        lignes += ["", "AVERTISSEMENTS"]
        lignes += [f"  {a}" for a in calepinage.avertissements]

    dessin = Dessin(titre="Instructions de pose", echelle=1)
    for i, ligne in enumerate(lignes):
        dessin.ajouter(
            Texte(
                0,
                -i * 5.0,
                ligne,
                Calque.TEXTE,
                taille_mm=3.0 if i == 0 else 2.4,
                ancrage=Ancrage.GAUCHE,
            )
        )
    return dessin


def dossier(calepinage: Calepinage, plan: Plan) -> list[Dessin]:
    """Toutes les planches du dossier, dans l'ordre de reliure.

    Une elevation trop longue pour tenir au 1:50 est paginee en plusieurs
    feuilles qui se recouvrent, plutot que reduite jusqu'a l'illisible.
    """
    par_mur: dict[str, list[Ouverture]] = {}
    for o in plan.ouvertures:
        par_mur.setdefault(o.mur, []).append(o)
    planches: list[Dessin] = []
    for mur in calepinage.murs:
        planches.extend(paginer(elevation(mur, plan, par_mur.get(mur.id, []))))
    planches += [plan_de_rang(calepinage, plan, r) for r in range(plan.rangs)]
    planches.append(instructions(calepinage, plan))
    return planches


def apercu(plan: Plan) -> Dessin:
    """Vue de dessus schematique d'un plan : contour et refends, sans calepinage.

    Sert a montrer immediatement ce qu'une esquisse a produit, y compris quand le
    plan n'est pas encore calepinable — il lui manque en general ses baies.
    """
    dessin = Dessin(
        titre=f"Apercu — {plan.nom}",
        sous_titre=(
            f"{len(plan.contour.sommets())} murs, {len(plan.refends)} refend"
            f"{'s' if len(plan.refends) > 1 else ''}, "
            f"hauteur sous chainage {plan.hauteur_sous_chainage} mm"
        ),
    )
    sommets = plan.contour.sommets()
    dessin.ajouter(Polyligne(tuple(sommets), Calque.BRIQUE, ferme=True))
    for i, (x, y) in enumerate(sommets):
        suivant = sommets[(i + 1) % len(sommets)]
        longueur = abs(suivant[0] - x) + abs(suivant[1] - y)
        dessin.ajouter(
            Texte(
                (x + suivant[0]) / 2,
                (y + suivant[1]) / 2,
                f"M{i + 1} — {longueur}",
                Calque.TEXTE,
                taille_mm=2.4,
            )
        )
    for refend in plan.refends:
        (x0, y0), (x1, y1) = refend.depart, refend.arrivee
        horizontal = y0 == y1
        demi = EPAISSEUR_MUR // 2
        dessin.ajouter(
            Rect(
                min(x0, x1) - (0 if horizontal else demi),
                min(y0, y1) - (demi if horizontal else 0),
                abs(x1 - x0) or EPAISSEUR_MUR,
                abs(y1 - y0) or EPAISSEUR_MUR,
                Calque.REFEND,
            ),
            Texte((x0 + x1) / 2, (y0 + y1) / 2, refend.id, Calque.REPERE, taille_mm=2.6),
        )
    dessin.legende = [(c.value, c) for c in dessin.calques_de_legende()]
    return dessin
