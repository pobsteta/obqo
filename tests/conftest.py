from __future__ import annotations

import json
from pathlib import Path

import pytest

from briq.model.plan import Plan

RACINE = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def maison() -> Plan:
    return Plan.model_validate(json.loads((RACINE / "exemples" / "maison.json").read_text()))


def plan_rectangle(largeur: int, profondeur: int, hauteur: int = 2640, **extra: object) -> Plan:
    """Plan rectangulaire minimal, cale sur la grille."""
    return Plan.model_validate(
        {
            "nom": f"rectangle {largeur}x{profondeur}",
            "hauteur_sous_chainage": hauteur,
            "contour": {
                "trace": {
                    "segments": [
                        {"direction": "est", "longueur": largeur},
                        {"direction": "nord", "longueur": profondeur},
                        {"direction": "ouest", "longueur": largeur},
                        {"direction": "sud", "longueur": profondeur},
                    ]
                }
            },
            **extra,
        }
    )
