"""De l'esquisse au plan : calage sur la grille, contour, refends.

Deux operations, volontairement separees pour rester relisibles :

* `caler` ramene les lignes du dessin sur un pas donne — 480 par defaut, la
  cote qui evite les demi-briques. Il cale **les lignes de coordonnees**, pas les
  pieces : deux pieces qui se touchaient se touchent encore apres calage, la
  topologie du plan est preservee par construction ;
* `vers_plan` deduit le contour et les refends de l'occupation des cellules.

Ce que le moteur de calepinage sait faire borne le resultat : un refend doit
aller d'un mur exterieur a l'autre. Une ligne interieure qui ne traverse pas tout
le batiment n'est pas un refend obqo — c'est une **cloison non porteuse**, hors
calepinage, et l'application le dit au lieu de produire un plan infaisable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from obqo.engine.validation import Gravite, Rapport
from obqo.model.esquisse import Baie, Esquisse, Piece
from obqo.model.plan import Contour, Ouverture, Plan, Refend
from obqo.units import EPAISSEUR_MUR, GRILLE

PAS_RECOMMANDE = 480
"""Pas de calage par defaut : evite les demi-briques (voir docs/hypotheses.md)."""

Point = tuple[int, int]


class Ajustement(NamedTuple):
    """Ce que le calage a change sur une piece ou sur une baie.

    Une baie n'a qu'une largeur a caler : sa hauteur se saisit au clavier, elle
    ne se dessine pas. Les champs de hauteur valent alors None.
    """

    quoi: str
    largeur_avant: int
    largeur_apres: int
    hauteur_avant: int | None = None
    hauteur_apres: int | None = None

    @property
    def bouge(self) -> bool:
        return self.largeur_avant != self.largeur_apres or self.hauteur_avant != self.hauteur_apres

    def __str__(self) -> str:
        if self.hauteur_avant is None or self.hauteur_apres is None:
            return (
                f"{self.quoi} : largeur {self.largeur_avant} -> {self.largeur_apres} mm "
                f"({self.largeur_apres - self.largeur_avant:+d})"
            )
        return (
            f"{self.quoi} : {self.largeur_avant} x {self.hauteur_avant} -> "
            f"{self.largeur_apres} x {self.hauteur_apres} mm "
            f"({self.largeur_apres - self.largeur_avant:+d}, "
            f"{self.hauteur_apres - self.hauteur_avant:+d})"
        )


def _caler_lignes(valeurs: list[int], pas: int) -> dict[int, int]:
    """Projette des coordonnees croissantes sur le pas, sans jamais les croiser.

    Garder l'ordre strict est ce qui preserve la topologie : une piece ne peut
    pas devenir plate ni passer de l'autre cote de sa voisine.
    """
    cale: dict[int, int] = {}
    precedent: int | None = None
    # L'origine est calee elle aussi, mais conservee : un dessin ne doit pas
    # sauter dans le coin de la feuille parce qu'on l'a mis sur la grille.
    origine = valeurs[0]
    ancre = round(origine / pas) * pas
    for valeur in valeurs:
        cible = ancre + round((valeur - origine) / pas) * pas
        if precedent is not None and cible <= precedent:
            cible = precedent + pas
        cale[valeur] = cible
        precedent = cible
    return cale


def _projeter(valeur: int, lignes: dict[int, int], origine: int) -> int:
    """Cale une coordonnee de baie : sur sa ligne si c'en est une, sinon sur 240.

    Une baie a une coordonnee sur l'axe de son mur — donc une ligne de piece, qui
    suit le calage des murs — et une autre le long du mur, qui n'en est pas une.
    Cette derniere se cale sur la **grille de 240**, jamais sur 480 : une porte
    de 1 200 est parfaitement valide, et l'arrondir a 960 lui coute 24 cm de
    passage. Seules les longueurs de murs gagnent a tomber sur 480.
    """
    if valeur in lignes:
        return lignes[valeur]
    return round((valeur - origine) / GRILLE) * GRILLE + round(origine / GRILLE) * GRILLE


def caler(esquisse: Esquisse, pas: int = PAS_RECOMMANDE) -> tuple[Esquisse, list[Ajustement]]:
    """Ramene l'esquisse sur le pas demande et dit ce qui a bouge."""
    x = _caler_lignes(esquisse.abscisses, pas)
    y = _caler_lignes(esquisse.ordonnees, pas)
    ox, oy = esquisse.abscisses[0], esquisse.ordonnees[0]
    pieces: list[Piece] = []
    ajustements: list[Ajustement] = []
    for piece in esquisse.pieces:
        calee = Piece(
            nom=piece.nom,
            x=x[piece.x],
            y=y[piece.y],
            largeur=x[piece.droite] - x[piece.x],
            hauteur=y[piece.haut] - y[piece.y],
        )
        pieces.append(calee)
        ajustements.append(
            Ajustement(piece.nom, piece.largeur, calee.largeur, piece.hauteur, calee.hauteur)
        )
    baies: list[Baie] = []
    for baie in esquisse.baies:
        baie_calee = baie.model_copy(
            update={
                "depart": (
                    _projeter(baie.depart[0], x, ox),
                    _projeter(baie.depart[1], y, oy),
                ),
                "arrivee": (
                    _projeter(baie.arrivee[0], x, ox),
                    _projeter(baie.arrivee[1], y, oy),
                ),
            }
        )
        baies.append(baie_calee)
        ajustements.append(Ajustement(baie.id, baie.largeur, baie_calee.largeur))
    return (
        esquisse.model_copy(update={"pieces": pieces, "baies": baies}),
        [a for a in ajustements if a.bouge],
    )


class MurDerive(NamedTuple):
    """Un mur du plan, tel que le moteur de calepinage le nommera."""

    id: str
    depart: tuple[int, int]
    arrivee: tuple[int, int]
    interieur: bool

    @property
    def longueur(self) -> int:
        return abs(self.arrivee[0] - self.depart[0]) + abs(self.arrivee[1] - self.depart[1])


def murs_du_plan(plan: Plan) -> list[MurDerive]:
    """Les murs d'un plan, dans l'ordre et sous le nom que leur donne le moteur.

    `engine.geometrie` numerote les murs exterieurs M1, M2... en suivant le
    contour ; les refends gardent leur identifiant. L'editeur d'esquisse s'appuie
    dessus pour poser les baies sur un mur qui existera vraiment.
    """
    sommets = plan.contour.sommets()
    murs = [
        MurDerive(f"M{i + 1}", sommets[i], sommets[(i + 1) % len(sommets)], False)
        for i in range(len(sommets))
    ]
    murs += [MurDerive(r.id, r.depart, r.arrivee, True) for r in plan.refends]
    return murs


def _poser_baies(plan: Plan, baies: list[Baie], rapport: Rapport) -> list[Ouverture]:
    """Rattache chaque baie de l'esquisse au mur qui la porte."""
    murs = murs_du_plan(plan)
    ouvertures: list[Ouverture] = []
    for baie in baies:
        porteur = next((m for m in murs if baie.sur(m.depart, m.arrivee)), None)
        if porteur is None:
            rapport.ajouter(
                Gravite.ERREUR,
                "BAIE-SANS-MUR",
                baie.id,
                "la baie ne repose sur aucun mur du plan derive. Le calage a pu "
                "deplacer le mur qui la portait : reposez-la",
            )
            continue
        depuis = min(
            abs(baie.depart[0] - porteur.depart[0]) + abs(baie.depart[1] - porteur.depart[1]),
            abs(baie.arrivee[0] - porteur.depart[0]) + abs(baie.arrivee[1] - porteur.depart[1]),
        )
        ouvertures.append(
            Ouverture(
                id=baie.id,
                mur=porteur.id,
                type=baie.type,
                position=depuis,
                largeur=baie.largeur,
                allege=0 if baie.type in ("porte", "porte_fenetre") else baie.allege,
                hauteur=baie.hauteur,
            )
        )
    return ouvertures


@dataclass(slots=True)
class Treillis:
    """Occupation des cellules du damier forme par les lignes de l'esquisse."""

    abscisses: list[int]
    ordonnees: list[int]
    cellules: dict[tuple[int, int], str]

    def occupee(self, i: int, j: int) -> bool:
        return (i, j) in self.cellules

    @property
    def colonnes(self) -> int:
        return len(self.abscisses) - 1

    @property
    def lignes(self) -> int:
        return len(self.ordonnees) - 1


def treillis(esquisse: Esquisse) -> Treillis:
    xs, ys = esquisse.abscisses, esquisse.ordonnees
    cellules: dict[tuple[int, int], str] = {}
    for piece in esquisse.pieces:
        for i in range(xs.index(piece.x), xs.index(piece.droite)):
            for j in range(ys.index(piece.y), ys.index(piece.haut)):
                cellules[(i, j)] = piece.nom
    return Treillis(xs, ys, cellules)


def _segments_de_bord(t: Treillis) -> list[tuple[Point, Point]]:
    """Segments du bord, orientes de sorte que l'interieur soit a gauche."""
    segments: list[tuple[Point, Point]] = []
    for i in range(t.colonnes + 1):
        for j in range(t.lignes):
            ouest = t.occupee(i - 1, j) if i else False
            est = t.occupee(i, j) if i < t.colonnes else False
            if ouest == est:
                continue
            bas, haut = (t.abscisses[i], t.ordonnees[j]), (t.abscisses[i], t.ordonnees[j + 1])
            segments.append((bas, haut) if ouest else (haut, bas))
    for j in range(t.lignes + 1):
        for i in range(t.colonnes):
            sud = t.occupee(i, j - 1) if j else False
            nord = t.occupee(i, j) if j < t.lignes else False
            if sud == nord:
                continue
            gauche = (t.abscisses[i], t.ordonnees[j])
            droite = (t.abscisses[i + 1], t.ordonnees[j])
            segments.append((droite, gauche) if sud else (gauche, droite))
    return segments


def _fusionner(points: list[Point]) -> list[Point]:
    """Supprime les sommets alignes d'une polyligne rectiligne."""
    if len(points) < 3:
        return points
    garde: list[Point] = []
    for index, point in enumerate(points):
        avant = points[index - 1]
        apres = points[(index + 1) % len(points)]
        aligne_x = avant[0] == point[0] == apres[0]
        aligne_y = avant[1] == point[1] == apres[1]
        if not (aligne_x or aligne_y):
            garde.append(point)
    return garde


def contour_de(t: Treillis, rapport: Rapport) -> list[Point] | None:
    """Trace le contour exterieur de la reunion des pieces."""
    segments = _segments_de_bord(t)
    depuis: dict[Point, list[Point]] = {}
    for depart, arrivee in segments:
        depuis.setdefault(depart, []).append(arrivee)

    pincements = [p for p, suivants in depuis.items() if len(suivants) > 1]
    if pincements:
        rapport.ajouter(
            Gravite.ERREUR,
            "PIECES-EN-POINTE",
            f"{pincements[0]}",
            "deux pieces ne se touchent que par un coin : le contour n'est pas "
            "trace de facon unique. Decalez-en une, ou ajoutez la piece manquante",
        )
        return None

    depart = min(depuis)
    boucle: list[Point] = [depart]
    courant = depuis[depart][0]
    while courant != depart:
        boucle.append(courant)
        suivants = depuis.get(courant)
        if not suivants:  # pragma: no cover - impossible sur un bord ferme
            rapport.ajouter(Gravite.ERREUR, "CONTOUR-OUVERT", f"{courant}", "bord interrompu")
            return None
        courant = suivants[0]

    if len(boucle) != len(segments):
        rapport.ajouter(
            Gravite.ERREUR,
            "PLAN-EN-PLUSIEURS-MORCEAUX",
            _decrire_blocs(t),
            "les pieces forment plusieurs blocs separes, ou entourent un vide. "
            "Une esquisse doit decrire un batiment d'un seul tenant, sans cour "
            "interieure : un vide de 240 mm entre deux pieces suffit a les separer",
        )
        return None
    return _fusionner(boucle)


def _blocs(t: Treillis) -> list[set[tuple[int, int]]]:
    """Composantes connexes des cellules occupees, par contact de cote."""
    restantes = set(t.cellules)
    trouves: list[set[tuple[int, int]]] = []
    while restantes:
        depart = restantes.pop()
        bloc = {depart}
        a_voir = [depart]
        while a_voir:
            i, j = a_voir.pop()
            for voisin in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
                if voisin in restantes:
                    restantes.discard(voisin)
                    bloc.add(voisin)
                    a_voir.append(voisin)
        trouves.append(bloc)
    return trouves


def _decrire_blocs(t: Treillis) -> str:
    """Localise chaque bloc, pour que le message designe l'endroit du probleme."""
    blocs = _blocs(t)
    if len(blocs) < 2:
        return "vide interieur"
    descriptions = []
    for bloc in sorted(blocs, key=lambda b: -len(b)):
        pieces = sorted({t.cellules[c] for c in bloc})
        x0 = min(t.abscisses[i] for i, _ in bloc)
        y0 = min(t.ordonnees[j] for _, j in bloc)
        descriptions.append(f"{', '.join(pieces)} (vers {x0}, {y0})")
    return " | ".join(descriptions)


def _examiner_ligne(
    paires: list[tuple[str | None, str | None]], bornes: list[int]
) -> tuple[int, int] | str | None:
    """Qualifie une ligne du treillis : refend, cloison, ou rien du tout.

    Une ligne du treillis n'est pas forcement un mur : elle nait du bord d'une
    piece et peut traverser une piece voisine de part en part. Si les deux cotes
    appartiennent a la **meme** piece, la ligne coupe cette piece — ce n'est pas
    un mur, et l'ignorer est la seule reponse correcte.

    Retourne les bornes du refend, `None` si la ligne n'est pas un mur du tout,
    ou la chaine « cloison » si c'est un mur qui ne traverse pas tout le
    batiment — parce qu'il debouche sur le contour ou s'arrete dans une piece.
    """
    interieur: list[bool] = []
    sur_contour = False
    traverse_une_piece = False
    for gauche, droite in paires:
        if gauche is not None and droite is not None:
            if gauche == droite:
                traverse_une_piece = True
                interieur.append(False)
            else:
                interieur.append(True)
        elif gauche is None and droite is None:
            interieur.append(False)
        else:
            sur_contour = True
            interieur.append(False)
    if not any(interieur):
        # Aucune separation reelle : la ligne ne fait que couper une piece.
        return None
    if traverse_une_piece:
        # Mur bien reel, mais qui s'arrete dans une piece voisine.
        return "cloison"
    if sur_contour:
        return "cloison"
    indices = [k for k, v in enumerate(interieur) if v]
    if indices != list(range(indices[0], indices[-1] + 1)):
        return "cloison"
    return bornes[indices[0]], bornes[indices[-1] + 1]


def _refends(t: Treillis, rapport: Rapport) -> list[Refend]:
    """Lignes interieures qui traversent tout le batiment, donc calepinables."""
    trouves: list[Refend] = []
    cloisons: list[str] = []

    def retenir(
        verdict: object, depart: tuple[int, int], arrivee: tuple[int, int], repere: str
    ) -> None:
        if verdict == "cloison":
            cloisons.append(repere)
        elif isinstance(verdict, tuple):
            trouves.append(Refend(id=f"R{len(trouves) + 1}", depart=depart, arrivee=arrivee))

    for i in range(1, t.colonnes):
        paires = [(t.cellules.get((i - 1, j)), t.cellules.get((i, j))) for j in range(t.lignes)]
        verdict = _examiner_ligne(paires, t.ordonnees)
        x = t.abscisses[i]
        bornes = verdict if isinstance(verdict, tuple) else (0, 0)
        retenir(verdict, (x, bornes[0]), (x, bornes[1]), f"x = {x}")

    for j in range(1, t.lignes):
        paires = [(t.cellules.get((i, j - 1)), t.cellules.get((i, j))) for i in range(t.colonnes)]
        verdict = _examiner_ligne(paires, t.abscisses)
        y = t.ordonnees[j]
        bornes = verdict if isinstance(verdict, tuple) else (0, 0)
        retenir(verdict, (bornes[0], y), (bornes[1], y), f"y = {y}")

    trouves, croises = _demeler(trouves)
    cloisons.extend(croises)
    if cloisons:
        rapport.ajouter(
            Gravite.AVERTISSEMENT,
            "CLOISON-NON-PORTEUSE",
            ", ".join(cloisons),
            "ces murs interieurs ne peuvent pas etre des refends obqo : soit ils "
            "ne traversent pas tout le batiment, soit ils en croisent un autre — "
            "et le systeme ne decrit pas la jonction en croix. A realiser en "
            "cloison legere, hors calepinage",
        )
    return trouves


def _horizontal(refend: Refend) -> bool:
    return refend.depart[1] == refend.arrivee[1]


def _se_croisent(a: Refend, b: Refend) -> bool:
    """Un refend vertical et un horizontal se coupent-ils en leur interieur ?"""
    if _horizontal(a) == _horizontal(b):
        return False
    vertical, horizontal = (b, a) if _horizontal(a) else (a, b)
    x = vertical.depart[0]
    y = horizontal.depart[1]
    return min(horizontal.depart[0], horizontal.arrivee[0]) < x < max(
        horizontal.depart[0], horizontal.arrivee[0]
    ) and min(vertical.depart[1], vertical.arrivee[1]) < y < max(
        vertical.depart[1], vertical.arrivee[1]
    )


def _longueur(refend: Refend) -> int:
    return abs(refend.arrivee[0] - refend.depart[0]) + abs(refend.arrivee[1] - refend.depart[1])


def _demeler(refends: list[Refend]) -> tuple[list[Refend], list[str]]:
    """Ecarte les refends qui en croisent un autre.

    Le systeme ne decrit pas de jonction en croix : deux refends qui se coupent
    se disputeraient la meme colonne de 240. Plutot que de produire un plan
    infaisable, on garde le sens qui porte le plus de mur — choix deterministe —
    et l'autre repasse en cloison legere. L'utilisateur voit ce qui a ete ecarte
    et peut redessiner s'il prefere l'inverse.
    """
    if not any(_se_croisent(a, b) for a in refends for b in refends):
        return refends, []
    horizontaux = [r for r in refends if _horizontal(r)]
    verticaux = [r for r in refends if not _horizontal(r)]
    total_h = sum(_longueur(r) for r in horizontaux)
    total_v = sum(_longueur(r) for r in verticaux)
    gardes, ecartes = (verticaux, horizontaux) if total_v >= total_h else (horizontaux, verticaux)
    repere = [f"y = {r.depart[1]}" if _horizontal(r) else f"x = {r.depart[0]}" for r in ecartes]
    renumerotes = [r.model_copy(update={"id": f"R{index + 1}"}) for index, r in enumerate(gardes)]
    return renumerotes, repere


def vers_plan(esquisse: Esquisse) -> tuple[Plan | None, Rapport]:
    """Convertit une esquisse en plan obqo. Retourne None si c'est impossible."""
    rapport = Rapport()
    for piece in esquisse.pieces:
        for cote, valeur in (("largeur", piece.largeur), ("hauteur", piece.hauteur)):
            if valeur % GRILLE:
                rapport.ajouter(
                    Gravite.ERREUR,
                    "PIECE-HORS-GRILLE",
                    piece.nom,
                    f"{cote} {valeur} mm : multiple de {GRILLE} mm attendu — "
                    "caler l'esquisse avant de convertir",
                )
        if min(piece.largeur, piece.hauteur) <= EPAISSEUR_MUR:
            rapport.ajouter(
                Gravite.ERREUR,
                "PIECE-TROP-PETITE",
                piece.nom,
                f"{piece.largeur} x {piece.hauteur} mm : les murs qui la bordent "
                "ne laisseraient aucun espace habitable",
            )

    t = treillis(esquisse)
    sommets = contour_de(t, rapport)
    if sommets is None or not rapport.valide:
        return None, rapport

    plan = Plan(
        nom=esquisse.nom,
        hauteur_sous_chainage=esquisse.hauteur_sous_chainage,
        contour=Contour(points=sommets),
        refends=_refends(t, rapport),
    )
    if esquisse.baies:
        plan = plan.model_copy(update={"ouvertures": _poser_baies(plan, esquisse.baies, rapport)})
    return (plan if rapport.valide else None), rapport
