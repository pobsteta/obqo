"""Geometrie interne des briques, planches et back-ends de dessin."""

from __future__ import annotations

from collections import Counter
from itertools import pairwise
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from briq.drawings import dxf, pdf, svg
from briq.drawings.ir import MENTION, Calque, Dessin, Rect, echelle_adaptee
from briq.drawings.mise_en_page import A3, ECHELLE_DE_LISIBILITE, cadrer, paginer
from briq.drawings.planches import dossier, elevation, instructions, plan_de_rang
from briq.drawings.volume import (
    receptions_globales,
    tenons_globaux,
    tenons_sans_reception,
)
from briq.engine.calepinage import calepiner, vide_du_rang
from briq.model.plan import Plan
from briq.model.systeme import Ref
from briq.rules.catalogue import PIECES, composition
from briq.rules.geometrie_brique import cellules_vides, pieces_de

from .conftest import plan_rectangle


@pytest.fixture(scope="module")
def maison_calepinee(maison: Plan):
    calepinage, _ = calepiner(maison)
    assert calepinage is not None
    return calepinage


# --- geometrie interne d'une brique ------------------------------------------


def test_la_geometrie_concorde_avec_la_table_de_composition() -> None:
    """Deux tables ecrites independamment doivent donner les memes pieces."""
    for ref in Ref:
        geometrique = Counter(p.ref for p in pieces_de(ref))
        declaree = Counter({r: n for r, n in composition(ref).items() if PIECES[r].largeur != 20})
        assert geometrique == declaree, ref


def test_les_cellules_vides_sont_les_poches_et_les_receptions() -> None:
    """Paragraphe 1.2 : 4 poches ouvertes et 2 trous de reception sur une 480."""
    vides = cellules_vides(Ref.B480_S)
    poches = [c for c in vides if c[2] == 80]
    receptions = [c for c in vides if c[2] == 0]
    assert len(poches) == 4
    assert {(x, y) for x, y, _ in poches} == {(0, 0), (0, 160), (400, 0), (400, 160)}
    assert len(receptions) == 2
    assert {(x, y) for x, y, _ in receptions} == {(80, 80), (320, 80)}


def test_une_brique_480_occupe_48_cellules_sur_54() -> None:
    volume = sum(p.volume for p in pieces_de(Ref.B480_S))
    # Les tenons debordent de 80 au-dessus du rang : 2 x 80x80x80 en plus.
    assert volume == 48 * 80**3 + 2 * 80**3


def test_la_anr_n_a_qu_un_carre_le_second_etant_la_mortaise_de_flanc() -> None:
    carres = [p for p in pieces_de(Ref.B480_ANR) if p.ref == "P8"]
    assert len(carres) == 1
    assert (carres[0].x, carres[0].y) == (0, 0), "carre du parement exterieur"
    tenons = [p for p in pieces_de(Ref.B480_ANR) if p.ref == "P5-A"]
    assert len(tenons) == 1 and tenons[0].x == 80, "tenon d'angle cote angle"


# --- le harpage tombe-t-il juste ? -------------------------------------------


def test_tout_tenon_sans_reception_est_sous_une_baie(maison: Plan, maison_calepinee) -> None:
    """Verification impossible a faire sur une elevation 2D.

    Un tenon sans reception au rang superieur est **soit** sous une baie ou hors
    de l'emprise d'un linteau (il se coupe a ras), **soit** le signe que le
    harpage croise alterne ne tombe pas juste. Ce test prouve qu'il n'y a que
    des cas du premier type : la colonne d'angle est geometriquement correcte.
    """
    orphelins = tenons_sans_reception(maison_calepinee)
    assert orphelins, "la maison d'exemple a des baies, donc des tenons a couper"
    par_mur = {o.mur: [] for o in maison.ouvertures}
    for o in maison.ouvertures:
        par_mur[o.mur].append(o)
    for identifiant, rang, u in orphelins:
        vides = [
            v for o in par_mur.get(identifiant, []) if (v := vide_du_rang(o, rang + 1)) is not None
        ]
        assert any(a <= u < b for a, b in vides), (
            f"tenon orphelin hors emprise de baie : {identifiant} R{rang} u={u} — "
            "le harpage ne tombe pas juste"
        )


def test_le_coin_minimum_est_correct_sur_un_mur_oriente_a_l_envers(maison_calepinee) -> None:
    """Un mur oriente vers l'ouest ou le sud a une direction negative.

    Le point de depart d'une piece y devient son bord maximum : sans prendre le
    minimum composante par composante, tenons et receptions ne coincident plus.
    """
    for mur in maison_calepinee.murs:
        sens = mur.arrivee[0] - mur.depart[0] < 0 or mur.arrivee[1] - mur.depart[1] < 0
        if not sens:
            continue
        rang = mur.rangs[0]
        for brique in rang.briques:
            for _, (x, y) in tenons_globaux(brique, mur, rang):
                assert min(mur.depart[0], mur.arrivee[0]) - 240 <= x
                assert min(mur.depart[1], mur.arrivee[1]) - 240 <= y
        assert receptions_globales(rang.briques[0], mur, rang)
        break
    else:  # pragma: no cover
        pytest.fail("la maison d'exemple devrait avoir un mur oriente a l'envers")


# --- planches -----------------------------------------------------------------


def test_l_elevation_contient_une_forme_par_brique(maison: Plan, maison_calepinee) -> None:
    mur = maison_calepinee.murs[0]
    baies = [o for o in maison.ouvertures if o.mur == mur.id]
    dessin = elevation(mur, maison, baies)
    briques = [
        p
        for p in dessin.primitives
        if isinstance(p, Rect)
        and p.calque in (Calque.BRIQUE, Calque.DEMI, Calque.ANGLE, Calque.ABOUT)
    ]
    assert len(briques) == len(mur.briques)
    assert any(p.calque is Calque.CHAINAGE for p in dessin.primitives)
    assert any(p.calque is Calque.LINTEAU for p in dessin.primitives)


def test_le_dossier_a_une_planche_par_mur_par_rang_et_les_instructions(
    maison: Plan, maison_calepinee
) -> None:
    planches = dossier(maison_calepinee, maison)
    assert len(planches) == len(maison_calepinee.murs) + maison.rangs + 1
    assert planches[-1].titre == "Instructions de pose"


def test_les_instructions_listent_les_tenons_a_couper(maison: Plan, maison_calepinee) -> None:
    texte = "\n".join(
        p.texte for p in instructions(maison_calepinee, maison).primitives if hasattr(p, "texte")
    )
    attendu = len(tenons_sans_reception(maison_calepinee))
    assert f"TENONS A COUPER A RAS ({attendu})" in texte
    assert "ORDRE DE POSE" in texte


def test_le_plan_de_rang_place_les_murs_dans_le_plan(maison: Plan, maison_calepinee) -> None:
    """Les briques couvrent exactement le contour ; les reperes debordent."""
    from briq.drawings.ir import Polyligne

    dessin = plan_de_rang(maison_calepinee, maison, 0)
    points = [pt for p in dessin.primitives if isinstance(p, Polyligne) for pt in p.points]
    assert (min(x for x, _ in points), min(y for _, y in points)) == (0, 0)
    assert (max(x for x, _ in points), max(y for _, y in points)) == (13920, 10560)


def test_l_echelle_choisie_fait_tenir_le_dessin(maison: Plan, maison_calepinee) -> None:
    for planche in dossier(maison_calepinee, maison):
        cadrage = cadrer(planche, A3)
        x0, y0, x1, y1 = planche.emprise
        _, _, zdx, zdy = A3.zone
        assert (x1 - x0) / cadrage.echelle <= zdx + 0.01
        assert (y1 - y0) / cadrage.echelle <= zdy + 0.01


def test_une_echelle_normalisee_est_toujours_retenue() -> None:
    dessin = Dessin(titre="t")
    dessin.ajouter(Rect(0, 0, 100_000, 100_000))
    assert echelle_adaptee(dessin, 380, 250) == 500


# --- back-ends ----------------------------------------------------------------


def test_le_svg_est_bien_forme_et_porte_la_mention(
    tmp_path: Path, maison, maison_calepinee
) -> None:
    planche = dossier(maison_calepinee, maison)[0]
    rendu = svg.rendre(planche)
    racine = ET.fromstring(rendu)
    assert racine.tag.endswith("svg")
    assert racine.get("width") == "420.0mm"
    assert MENTION in rendu
    assert "Echelle 1:" in rendu


def test_le_svg_est_deterministe(maison, maison_calepinee) -> None:
    planche = dossier(maison_calepinee, maison)[0]
    assert svg.rendre(planche) == svg.rendre(planche)


def test_le_pdf_est_un_seul_document_multi_pages(tmp_path: Path, maison, maison_calepinee) -> None:
    planches = dossier(maison_calepinee, maison)
    cible = tmp_path / "dossier.pdf"
    pdf.ecrire(planches, cible)
    contenu = cible.read_bytes()
    assert contenu.startswith(b"%PDF")
    assert contenu.count(b"/Type /Page\n") >= len(planches) - 1


def test_le_dxf_se_relit_avec_ses_calques(tmp_path: Path, maison, maison_calepinee) -> None:
    import ezdxf

    planches = dossier(maison_calepinee, maison)[:1]
    fichiers = dxf.ecrire(planches, tmp_path)
    assert len(fichiers) == 1
    document = ezdxf.readfile(fichiers[0])
    noms = {couche.dxf.name for couche in document.layers}
    assert Calque.BRIQUE.value in noms
    # Le DXF dessine a l'echelle 1 : les coordonnees sont celles du modele.
    largeurs = [e.get_points()[2][0] for e in document.modelspace() if e.dxftype() == "LWPOLYLINE"]
    assert max(largeurs) >= 13000


def test_les_petites_planches_passent_par_tous_les_back_ends(tmp_path: Path) -> None:
    calepinage, _ = calepiner(plan_rectangle(2880, 2400, hauteur=480))
    assert calepinage is not None
    petit = plan_rectangle(2880, 2400, hauteur=480)
    planches = dossier(calepinage, petit)
    svg.ecrire(planches[0], tmp_path / "p.svg")
    pdf.ecrire(planches, tmp_path / "p.pdf")
    dxf.ecrire(planches, tmp_path)
    assert (tmp_path / "p.svg").stat().st_size > 0
    assert (tmp_path / "p.pdf").stat().st_size > 0


# --- pagination ---------------------------------------------------------------


def test_une_elevation_qui_tient_n_est_pas_paginee(maison: Plan, maison_calepinee) -> None:
    mur = maison_calepinee.murs[0]
    baies = [o for o in maison.ouvertures if o.mur == mur.id]
    pages = paginer(elevation(mur, maison, baies))
    assert len(pages) == 1
    assert pages[0].echelle is None, "l'echelle reste libre sur une planche unique"


def test_un_mur_trop_long_est_decoupe_en_pages_qui_se_recouvrent() -> None:
    """Un mur de 24 m ne tiendrait qu'au 1:100, ou les reperes sont illisibles."""
    long_ = plan_rectangle(
        24000,
        4800,
        ouvertures=[
            {
                "id": f"F{i}",
                "mur": m,
                "type": "fenetre",
                "position": pos,
                "largeur": 1200,
                "allege": 960,
                "hauteur": 1200,
            }
            for i, (m, pos) in enumerate(
                [
                    ("M1", 4800),
                    ("M1", 11040),
                    ("M1", 17280),
                    ("M3", 4800),
                    ("M3", 11040),
                    ("M3", 17280),
                ]
            )
        ],
    )
    calepinage, rapport = calepiner(long_)
    assert calepinage is not None, [str(e) for e in rapport.erreurs]
    mur = calepinage.murs[0]
    baies = [o for o in long_.ouvertures if o.mur == mur.id]
    pages = paginer(elevation(mur, long_, baies))

    assert len(pages) > 1
    assert [p.titre for p in pages] == [
        f"Elevation du mur M1 ({i + 1}/{len(pages)})" for i in range(len(pages))
    ]
    for page in pages:
        assert page.echelle == ECHELLE_DE_LISIBILITE
        x0, _, x1, _ = page.emprise
        _, _, zdx, _ = A3.zone
        assert (x1 - x0) / page.echelle <= zdx + 0.01
    # Les pages se recouvrent, et couvrent tout le mur sans trou.
    for gauche, droite in pairwise(pages):
        assert droite.emprise[0] < gauche.emprise[2], "il manque une bande commune"
    assert pages[0].emprise[0] == elevation(mur, long_, baies).emprise[0]
    assert pages[-1].emprise[2] == elevation(mur, long_, baies).emprise[2]


def test_les_pages_partagent_le_meme_cadre_vertical() -> None:
    long_ = plan_rectangle(24000, 4800)
    calepinage, _ = calepiner(long_)
    if calepinage is None:  # murs sans raidisseur : le refus est attendu
        return
    pages = paginer(elevation(calepinage.murs[0], long_, []))
    hauteurs = {(p.emprise[1], p.emprise[3]) for p in pages}
    assert len(hauteurs) == 1, "les pages doivent rester comparables"
