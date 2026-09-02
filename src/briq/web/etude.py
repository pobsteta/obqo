"""Etat partage de l'interface web : une etude calepinee, mise en cache.

Le coeur ne sait rien du web ; l'interface n'est qu'un client de plus, comme la
CLI. Rien n'est persiste : les etudes vivent en memoire, indexees par l'empreinte
du plan, et les plus anciennes sont oubliees.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock

from briq.bom.debit import GloutonDecroissant, Solveur, solveur_par_defaut
from briq.bom.metre import Chiffrage, Metre, chiffrer, metrer
from briq.bom.nomenclature import Nomenclature, nomenclaturer
from briq.drawings.ir import Dessin
from briq.drawings.planches import dossier
from briq.engine.calepinage import calepiner
from briq.engine.validation import Rapport
from briq.model.lecture import depuis_texte
from briq.model.plan import Plan
from briq.model.systeme import Calepinage

ETUDES_EN_MEMOIRE = 8


@dataclass(frozen=True, slots=True)
class Etude:
    """Un plan calepine et tout ce qui en decoule."""

    cle: str
    plan: Plan
    rapport: Rapport
    calepinage: Calepinage
    nomenclature: Nomenclature
    metre: Metre
    chiffrage: Chiffrage
    planches: list[Dessin]


class EchecDeValidation(Exception):
    """Le plan porte des erreurs : il n'y a pas d'etude a produire."""

    def __init__(self, rapport: Rapport) -> None:
        super().__init__("plan invalide")
        self.rapport = rapport


def empreinte(source: str, exact: bool) -> str:
    """Cle stable d'une etude : le plan et le solveur retenu."""
    graine = f"{source}\n{'exact' if exact else 'glouton'}"
    return hashlib.sha256(graine.encode("utf-8")).hexdigest()[:16]


class Depot:
    """Cache borne des etudes, protege pour un serveur multi-fils."""

    def __init__(self, capacite: int = ETUDES_EN_MEMOIRE) -> None:
        self._etudes: OrderedDict[str, Etude] = OrderedDict()
        self._verrou = Lock()
        self._capacite = capacite

    def get(self, cle: str) -> Etude | None:
        with self._verrou:
            if cle not in self._etudes:
                return None
            self._etudes.move_to_end(cle)
            return self._etudes[cle]

    def _ranger(self, etude: Etude) -> Etude:
        with self._verrou:
            self._etudes[etude.cle] = etude
            self._etudes.move_to_end(etude.cle)
            while len(self._etudes) > self._capacite:
                self._etudes.popitem(last=False)
        return etude

    def etudier(self, source: str, exact: bool = False) -> Etude:
        """Calepine le plan, ou renvoie l'etude deja calculee.

        Le solveur glouton est le defaut ici : l'interface doit repondre tout de
        suite. L'optimum exact reste a un clic, et la CLI le prend par defaut.
        """
        cle = empreinte(source, exact)
        if (deja := self.get(cle)) is not None:
            return deja

        plan = depuis_texte(source)
        calepinage, rapport = calepiner(plan)
        if calepinage is None:
            raise EchecDeValidation(rapport)

        nomenclature = nomenclaturer(calepinage)
        solveur: Solveur = solveur_par_defaut(10.0) if exact else GloutonDecroissant()
        metre = metrer(calepinage, nomenclature, plan.parametres, solveur)
        return self._ranger(
            Etude(
                cle=cle,
                plan=plan,
                rapport=rapport,
                calepinage=calepinage,
                nomenclature=nomenclature,
                metre=metre,
                chiffrage=chiffrer(metre, plan.parametres),
                planches=dossier(calepinage, plan),
            )
        )
