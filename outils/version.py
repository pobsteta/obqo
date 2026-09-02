"""Version suivante du depot, deduite des messages de commit.

Le depot ecrit des **commits conventionnels** : le type en tete du sujet dit ce
que le commit change, donc de combien la version doit bouger. Cet outil n'est
que la lecture systematique de cette convention — il ne decide rien de plus :

* une **rupture** (`type!:` ou `BREAKING CHANGE:` dans le corps) avance la
  majeure ; tant que la majeure vaut 0, elle avance la mineure, parce qu'une
  version 0 ne promet aucune stabilite (semver, paragraphe 4) ;
* `feat` avance la mineure ;
* `fix` et `perf` avancent la corrective ;
* tout le reste — `docs`, `refactor`, `test`, `chore`, `ci`, `style`, `build` —
  ne publie rien. Un depot qui publierait a chaque virgule de documentation
  noierait ses vraies versions.

Ecrit en clair plutot qu'apporte par une dependance : la regle tient en trente
lignes, elle se teste, et une chaine de publication qu'on ne sait pas relire
finit par publier ce qu'on n'a pas voulu.

Appele par `.github/workflows/publication.yml` apres chaque fusion sur la
branche par defaut. Sans `--appliquer`, il ne fait qu'annoncer.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Self

RACINE = Path(__file__).resolve().parents[1]

ENTETE = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<portee>[^)]*)\))?(?P<rupture>!)?:\s+(?P<sujet>.+)$"
)
RUPTURE = re.compile(r"^BREAKING[ -]CHANGE\s*:", re.MULTILINE)
"""La forme longue de la rupture, dans le corps du message."""

MINEURS = frozenset({"feat"})
CORRECTIFS = frozenset({"fix", "perf"})

SEPARATEUR = "\x00"
"""Separateur d'enregistrements entre deux messages : aucun ne le contient.

`git log` l'ecrit avec le motif `%x00` — un octet nul ne se passe pas en
argument de ligne de commande, il faut demander a git de l'emettre lui-meme.
"""


@dataclass(frozen=True, slots=True)
class Commit:
    """Un commit conventionnel, reduit a ce qui change la version."""

    type: str
    portee: str
    sujet: str
    rupture: bool

    @classmethod
    def lire(cls, message: str) -> Self | None:
        """Le commit, ou None si le message ne suit pas la convention.

        Un message hors convention n'est pas une erreur : il ne publie rien,
        comme un `chore`. Refuser la fusion pour cela bloquerait le depot sur
        un detail de forme.
        """
        lignes = message.strip().splitlines()
        if not lignes:
            return None
        trouve = ENTETE.match(lignes[0].strip())
        if trouve is None:
            return None
        corps = "\n".join(lignes[1:])
        return cls(
            type=trouve["type"],
            portee=trouve["portee"] or "",
            sujet=trouve["sujet"].strip(),
            rupture=bool(trouve["rupture"]) or bool(RUPTURE.search(corps)),
        )

    def decrire(self) -> str:
        return f"**{self.portee}** — {self.sujet}" if self.portee else self.sujet


@dataclass(frozen=True, order=True, slots=True)
class Version:
    majeure: int
    mineure: int
    corrective: int

    @classmethod
    def lire(cls, texte: str) -> Self:
        nombres = texte.strip().removeprefix("v").split(".")
        if len(nombres) != 3 or not all(n.isdigit() for n in nombres):
            raise ValueError(f"« {texte} » n'est pas une version X.Y.Z")
        majeure, mineure, corrective = (int(n) for n in nombres)
        return cls(majeure, mineure, corrective)

    def __str__(self) -> str:
        return f"{self.majeure}.{self.mineure}.{self.corrective}"


def prochaine(actuelle: Version, commits: Sequence[Commit]) -> Version | None:
    """La version a publier, ou None s'il n'y a rien a publier."""
    if any(c.rupture for c in commits):
        if actuelle.majeure == 0:
            # Une version 0 ne promet rien : une rupture n'y declenche pas le
            # passage en 1.0, qui se decide, lui, a la main.
            return Version(0, actuelle.mineure + 1, 0)
        return Version(actuelle.majeure + 1, 0, 0)
    if any(c.type in MINEURS for c in commits):
        return Version(actuelle.majeure, actuelle.mineure + 1, 0)
    if any(c.type in CORRECTIFS for c in commits):
        return Version(actuelle.majeure, actuelle.mineure, actuelle.corrective + 1)
    return None


SECTIONS: tuple[tuple[str, Callable[[Commit], bool]], ...] = (
    ("Ruptures", lambda c: c.rupture),
    ("Nouveautés", lambda c: c.type in MINEURS and not c.rupture),
    ("Corrections", lambda c: c.type in CORRECTIFS and not c.rupture),
)


def notes(commits: Sequence[Commit]) -> str:
    """Les notes de version, groupees par section, dans l'ordre des commits."""
    blocs: list[str] = []
    for titre, retenir in SECTIONS:
        retenus = [c for c in commits if retenir(c)]
        if retenus:
            lignes = "\n".join(f"- {c.decrire()}" for c in retenus)
            blocs.append(f"### {titre}\n\n{lignes}")
    return "\n\n".join(blocs)


TITRE_JOURNAL = "# Journal des versions"


def journal(existant: str, version: Version, jour: date, corps: str) -> str:
    """Insere la nouvelle version en tete du journal, sans toucher au reste."""
    section = f"## {version} — {jour.isoformat()}\n\n{corps}\n"
    lignes = existant.splitlines()
    for index, ligne in enumerate(lignes):
        if ligne.startswith("## "):
            return "\n".join([*lignes[:index], section, *lignes[index:]]).rstrip() + "\n"
    entete = existant.rstrip() or TITRE_JOURNAL
    return f"{entete}\n\n{section}"


# --- ecriture des fichiers versionnes -----------------------------------------

VERSION_PYPROJECT = re.compile(r'(?m)^version = "(?P<version>[^"]+)"$')
VERSION_MODULE = re.compile(r'(?m)^__version__ = "(?P<version>[^"]+)"$')


def _remplacer(motif: re.Pattern[str], texte: str, version: Version, ou: str) -> str:
    trouves = motif.findall(texte)
    if len(trouves) != 1:
        raise ValueError(f"{ou} : {len(trouves)} version(s) trouvee(s), une seule attendue")
    return motif.sub(lambda m: m.group(0).replace(m["version"], str(version)), texte, count=1)


def version_declaree(racine: Path = RACINE) -> Version:
    """La version que le depot annonce aujourd'hui."""
    texte = (racine / "pyproject.toml").read_text(encoding="utf-8")
    trouve = VERSION_PYPROJECT.search(texte)
    if trouve is None:
        raise ValueError("pyproject.toml ne declare pas de version")
    return Version.lire(trouve["version"])


def appliquer(version: Version, corps: str, jour: date, racine: Path = RACINE) -> list[Path]:
    """Ecrit la version dans les trois fichiers qui la portent."""
    pyproject = racine / "pyproject.toml"
    module = racine / "src" / "obqo" / "__init__.py"
    changelog = racine / "CHANGELOG.md"
    pyproject.write_text(
        _remplacer(VERSION_PYPROJECT, pyproject.read_text(encoding="utf-8"), version, "pyproject"),
        encoding="utf-8",
    )
    module.write_text(
        _remplacer(VERSION_MODULE, module.read_text(encoding="utf-8"), version, "__init__"),
        encoding="utf-8",
    )
    ancien = changelog.read_text(encoding="utf-8") if changelog.exists() else TITRE_JOURNAL + "\n"
    changelog.write_text(journal(ancien, version, jour, corps), encoding="utf-8")
    return [pyproject, module, changelog]


# --- lecture du depot ---------------------------------------------------------


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], capture_output=True, text=True, check=True, cwd=RACINE
    ).stdout


def dernier_tag() -> str | None:
    """Le dernier tag de version, ou None si le depot n'en porte aucun."""
    try:
        return _git("describe", "--tags", "--abbrev=0", "--match", "v[0-9]*").strip() or None
    except subprocess.CalledProcessError:
        return None


def commits_depuis(tag: str | None) -> list[Commit]:
    """Les commits conventionnels depuis ce tag, du plus ancien au plus recent."""
    plage = [f"{tag}..HEAD"] if tag else ["HEAD"]
    brut = _git("log", "--reverse", "--no-merges", "--format=%B%x00", *plage)
    lus = (Commit.lire(message) for message in brut.split(SEPARATEUR))
    return [commit for commit in lus if commit is not None]


def _annoncer_a_github(version: str) -> None:
    """Passe la version au reste du workflow, quand on tourne dans une Action."""
    sortie = os.environ.get("GITHUB_OUTPUT")
    if sortie:
        with open(sortie, "a", encoding="utf-8") as flux:
            flux.write(f"version={version}\n")


def main(argv: Sequence[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    analyseur.add_argument(
        "--appliquer",
        action="store_true",
        help="ecrire la version dans pyproject.toml, __init__.py et CHANGELOG.md",
    )
    analyseur.add_argument(
        "--notes", type=Path, default=None, help="fichier ou ecrire les notes de version"
    )
    arguments = analyseur.parse_args(argv)

    actuelle = version_declaree()
    tag = dernier_tag()
    commits = commits_depuis(tag)
    suivante = prochaine(actuelle, commits)
    if suivante is None:
        _annoncer_a_github("")
        print(
            f"Rien a publier depuis {tag or 'le debut du depot'} : "
            f"{len(commits)} commit(s), aucun qui change la version."
        )
        return 0

    corps = notes(commits)
    if arguments.notes is not None:
        arguments.notes.write_text(corps + "\n", encoding="utf-8")
    if arguments.appliquer:
        for fichier in appliquer(suivante, corps, date.today()):
            print(f"mis a jour : {fichier.relative_to(RACINE)}")
    _annoncer_a_github(str(suivante))
    print(f"{actuelle} -> {suivante}")
    return 0


if __name__ == "__main__":  # pragma: no cover - point d'entree du workflow
    raise SystemExit(main())
