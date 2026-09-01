"""Moteur de calepinage : du plan valide au modele de briques posees.

**Regle actee (D2)** — jonction en T : le paragraphe 1.5 ne decrit le harpage
que pour les angles a 90 degres. Un refend est **en butee a ses deux extremites
a tous les rangs** : le mur traverse file toujours et n'est jamais interrompu.
La liaison est assuree par le chevillage traversant, non par une penetration
alternee, qui demanderait une brique que le catalogue ne contient pas.
"""

from __future__ import annotations

from briq.engine.appareillage import decouper, parite_du_rang
from briq.engine.geometrie import Mur, Squelette, squelette
from briq.engine.validation import Gravite, Rapport, valider
from briq.model.plan import Ouverture, Plan
from briq.model.systeme import (
    BriquePosee,
    Calepinage,
    ElementPose,
    MurCalepine,
    Quincaillerie,
    Rang,
    Ref,
)
from briq.rules.catalogue import (
    ANGLE_PAR_RANG,
    CHAINAGE_PAR_BRIQUE,
    JOINT_COURANT,
    LINTEAU_PAR_MONTANT,
)
from briq.units import (
    APPUI_LINTEAU,
    LARGEUR_BAIE_JAMBAGE_DOUBLE,
    LONGUEUR_BRIQUE,
    PORTEE_MAXI_LINTEAU,
)

ENTRAXE_MONTANT_LINTEAU = 320
"""Paragraphe 1.6 : un montant tous les 320 mm en travee de linteau."""


def _reference(longueur: int, debut_ferme: bool, fin_ferme: bool, angle: bool) -> Ref:
    """Reference de catalogue d'une brique selon ses abouts."""
    famille = "480" if longueur == LONGUEUR_BRIQUE else "240"
    if angle:
        return Ref(f"{famille}-ANR")
    suffixe = {0: "S", 1: "A", 2: "AA"}[int(debut_ferme) + int(fin_ferme)]
    return Ref(f"{famille}-{suffixe}")


def vide_du_rang(o: Ouverture, rang: int) -> tuple[int, int] | None:
    """Intervalle de maconnerie absente du a une baie, pour ce rang."""
    if rang < o.rang_bas or rang > o.rang_linteau:
        return None
    if rang == o.rang_linteau:
        # Le rang du linteau est occupe par les madriers, qui debordent de
        # l'appui de 240 de chaque cote.
        return (o.position - APPUI_LINTEAU, o.fin + APPUI_LINTEAU)
    return (o.position, o.fin)


def _segments(debut: int, fin: int, vides: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Decoupe la course en troncons de maconnerie, baies retirees."""
    troncons = [(debut, fin)]
    for a, b in vides:
        suivants: list[tuple[int, int]] = []
        for s, e in troncons:
            if b <= s or a >= e:
                suivants.append((s, e))
                continue
            if s < a:
                suivants.append((s, a))
            if b < e:
                suivants.append((b, e))
        troncons = suivants
    return [(a, b) for a, b in troncons if b > a]


def _poser_rang(
    mur: Mur,
    rang: int,
    sq: Squelette,
    ouvertures: list[Ouverture],
    rapport: Rapport,
) -> Rang:
    debut, fin = sq.course(mur, rang)
    debut0, _ = sq.course(mur, 0)
    parite = parite_du_rang(debut0, rang)
    angle_debut, angle_fin = sq.angles_par_mur[mur.id]
    file_au_debut = angle_debut is not None and angle_debut.filant(rang) == mur.id
    file_a_la_fin = angle_fin is not None and angle_fin.filant(rang) == mur.id

    vides = [v for o in ouvertures if (v := vide_du_rang(o, rang)) is not None]
    troncons = _segments(debut, fin, vides)
    r = Rang(mur=mur.id, indice=rang, debut=debut, fin=fin)

    for a, b in troncons:
        premier_troncon, dernier_troncon = a == debut, b == fin
        decoupe = decouper(a, b - a, parite)
        u = a
        for i, longueur in enumerate(decoupe):
            # Un about n'est libre qu'au bord d'un troncon : a l'interieur, deux
            # briques contigues forment un joint courant, poches ouvertes.
            bord_debut = i == 0
            bord_fin = i == len(decoupe) - 1
            tete_de_mur = premier_troncon and bord_debut
            pied_de_mur = dernier_troncon and bord_fin
            angle_debut_ici = tete_de_mur and file_au_debut
            angle_fin_ici = pied_de_mur and file_a_la_fin
            angle_ici = angle_debut_ici or angle_fin_ici
            # Ferme partout sauf la ou la filante d'angle porte sa mortaise.
            debut_ferme = bord_debut and not angle_debut_ici
            fin_ferme = bord_fin and not angle_fin_ici
            coin = None
            if angle_ici:
                coin = angle_debut if angle_debut_ici else angle_fin
                assert coin is not None
                if longueur != LONGUEUR_BRIQUE:
                    rapport.ajouter(
                        Gravite.HYPOTHESE,
                        "ANGLE-DEMI-BRIQUE",
                        f"{mur.id}/R{rang}",
                        "la brique filante d'angle est une demi-brique de 240 : "
                        "le catalogue du brief ne definit qu'une 480-ANR, "
                        "une 240-ANR est supposee (tenon d'angle a 120 de l'about)",
                    )
            r.briques.append(
                BriquePosee(
                    mur=mur.id,
                    rang=rang,
                    u=u,
                    ref=_reference(longueur, debut_ferme, fin_ferme, angle_ici),
                    about_debut_ferme=debut_ferme,
                    about_fin_ferme=fin_ferme,
                    angle=coin.id if coin else None,
                )
            )
            if i:
                r.quincaillerie.append(
                    Quincaillerie(
                        mur=mur.id,
                        rang=rang,
                        u=u,
                        role="joint courant",
                        pieces=tuple(sorted(JOINT_COURANT.items())),
                    )
                )
            u += longueur

    # Quincaillerie d'angle : portee par le mur filant, une fois par rang.
    for angle, u_angle in ((angle_debut, 0), (angle_fin, mur.longueur)):
        if angle is not None and angle.filant(rang) == mur.id:
            r.quincaillerie.append(
                Quincaillerie(
                    mur=mur.id,
                    rang=rang,
                    u=u_angle,
                    role=f"angle {angle.id}",
                    pieces=tuple(sorted(ANGLE_PAR_RANG.items())),
                )
            )
    return r


def _poser_baie(mur: Mur, o: Ouverture, rapport: Rapport) -> list[ElementPose]:
    """Jambages, madriers et montants de linteau d'une baie.

    **Regle actee (D1)** : le jambage P10 court sur la seule hauteur de la baie,
    du dessus de l'allege a la sous-face du linteau, et non « du soubassement au
    chainage ». Un jambage de 80 traversant l'allege laisserait entre les deux
    jambages un remplissage de `largeur - 160` : comme `largeur` est un multiple
    de 240, ce reste vaut toujours 80 et n'est jamais calable sur la grille.
    Avec cette regle l'allege est maconnee sur toute la largeur de la tremie,
    le madrier prend appui 240 de chaque cote sur cette maconnerie, et la
    relation `P9 = portee + 480` du paragraphe 1.3 est verifiee.
    """
    elements: list[ElementPose] = []
    epaisseur_jambage = 2 if o.largeur > LARGEUR_BAIE_JAMBAGE_DOUBLE else 1
    for cote, u in (("gauche", o.position), ("droite", o.fin - 80 * epaisseur_jambage)):
        elements.append(
            ElementPose(
                mur=mur.id,
                piece="P10",
                u=u,
                longueur=o.hauteur,
                quantite=epaisseur_jambage,
                role=f"jambage {cote}",
                ouverture=o.id,
            )
        )
    piece = "P9"
    if o.largeur > PORTEE_MAXI_LINTEAU:
        piece = "P9-LC"
        rapport.ajouter(
            Gravite.AVERTISSEMENT,
            "LINTEAU-LAMELLE",
            f"{mur.id}/{o.id}",
            f"portee {o.largeur} mm : deux lamelles-colles du commerce "
            f"80x240x{o.largeur + 2 * APPUI_LINTEAU} mm remplacent les madriers "
            "chevilles (ligne distincte du metre)",
        )
    elements.append(
        ElementPose(
            mur=mur.id,
            piece=piece,
            u=o.position - APPUI_LINTEAU,
            longueur=o.largeur + 2 * APPUI_LINTEAU,
            rang=o.rang_linteau,
            quantite=2,
            role="madrier de linteau",
            ouverture=o.id,
        )
    )
    return elements


def _montants_de_linteau(mur: Mur, o: Ouverture) -> Quincaillerie:
    """2 montants par zone d'appui, puis 1 tous les 320 en travee."""
    nombre = 4 + o.largeur // ENTRAXE_MONTANT_LINTEAU
    pieces = {ref: n * nombre for ref, n in LINTEAU_PAR_MONTANT.items()}
    return Quincaillerie(
        mur=mur.id,
        rang=o.rang_linteau,
        u=o.position,
        role=f"montants de linteau {o.id} ({nombre})",
        pieces=tuple(sorted(pieces.items())),
    )


def calepiner(plan: Plan) -> tuple[Calepinage | None, Rapport]:
    """Calepine le plan. Retourne None si le plan porte des erreurs."""
    sq = squelette(plan)
    longueurs = {m.id: m.longueur for m in sq.murs}
    rapport, ouvertures = valider(plan, longueurs, sq.ancrages)
    if not rapport.valide:
        return None, rapport

    calepinage = Calepinage(nom=plan.nom)
    par_mur: dict[str, list[Ouverture]] = {}
    for o in ouvertures:
        par_mur.setdefault(o.mur, []).append(o)

    for mur in sq.murs:
        mc = MurCalepine(
            id=mur.id,
            depart=mur.depart,
            arrivee=mur.arrivee,
            longueur_hors_tout=mur.longueur,
            interieur=mur.interieur,
        )
        baies = par_mur.get(mur.id, [])
        for rang in range(plan.rangs):
            r = _poser_rang(mur, rang, sq, baies, rapport)
            for o in baies:
                if rang == o.rang_linteau:
                    r.quincaillerie.append(_montants_de_linteau(mur, o))
                    r.quincaillerie.append(
                        Quincaillerie(
                            mur=mur.id,
                            rang=rang - 1,
                            u=o.position,
                            role=f"tenons a couper a ras sous le linteau {o.id}",
                        )
                    )
            mc.rangs.append(r)

        for o in baies:
            mc.elements.extend(_poser_baie(mur, o, rapport))

        # Chainage haut : lisse filante chevillee sur le dernier rang.
        mc.elements.append(
            ElementPose(
                mur=mur.id,
                piece="LISSE",
                u=0,
                longueur=mur.longueur,
                rang=plan.rangs,
                role="lisse de chainage haut",
            )
        )
        if mc.rangs:
            dernier = mc.rangs[-1]
            for b in dernier.briques:
                dernier.quincaillerie.append(
                    Quincaillerie(
                        mur=mur.id,
                        rang=dernier.indice,
                        u=b.u,
                        role="chevillage du chainage",
                        pieces=tuple(sorted(CHAINAGE_PAR_BRIQUE.items())),
                    )
                )
        calepinage.murs.append(mc)

    calepinage.avertissements = [str(c) for c in rapport.avertissements]
    calepinage.hypotheses = [str(c) for c in rapport.constats if c.gravite is Gravite.HYPOTHESE]
    return calepinage, rapport
