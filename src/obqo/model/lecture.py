"""Lecture d'un plan : JSON ou YAML, vers le meme modele valide.

Le JSON reste le format canonique — c'est lui que decrit le schema versionne et
que produisent les outils. Mais un plan de maison se saisit a la main, et on veut
pouvoir ecrire `# fenetre de la cuisine, alignee sur l'evier` a cote d'une cote.
Le YAML, dont le JSON est un sous-ensemble, l'autorise sans rien changer au
modele.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from obqo.model.esquisse import Esquisse
from obqo.model.plan import Plan

SUFFIXES_YAML = (".yaml", ".yml")


def analyser(source: str) -> Any:
    """Analyse une source JSON ou YAML et retourne la structure brute.

    Le JSON est tente d'abord : ses messages d'erreur designent la ligne et la
    colonne fautives bien plus clairement que ceux de l'analyseur YAML.
    """
    try:
        return json.loads(source)
    except json.JSONDecodeError as erreur_json:
        try:
            return yaml.safe_load(source)
        except yaml.YAMLError as erreur_yaml:
            # Un texte qui commence par une accolade voulait etre du JSON :
            # renvoyer l'erreur JSON, plus precise, plutot que celle du YAML.
            if source.lstrip().startswith(("{", "[")):
                raise ValueError(str(erreur_json)) from erreur_json
            raise ValueError(str(erreur_yaml)) from erreur_yaml


def depuis_texte(source: str) -> Plan:
    """Valide un plan depuis sa source, quel que soit son format."""
    structure = analyser(source)
    if not isinstance(structure, dict):
        raise ValueError(
            "le plan doit etre un objet (accolades en JSON, cles en YAML), "
            f"pas un {type(structure).__name__}"
        )
    return Plan.model_validate(structure)


def depuis_fichier(chemin: Path) -> Plan:
    return depuis_texte(chemin.read_text(encoding="utf-8"))


def esquisse_depuis_texte(source: str) -> Esquisse:
    """Relit une esquisse enregistree, dans le meme format que les plans."""
    structure = analyser(source)
    if not isinstance(structure, dict):
        raise ValueError(
            "l'esquisse doit etre un objet (accolades en JSON, cles en YAML), "
            f"pas un {type(structure).__name__}"
        )
    return Esquisse.model_validate(structure)
