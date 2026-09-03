# Publier une version

Il n'y a rien à faire : la version se donne toute seule à la fusion. Ce
document dit comment, pour qu'on sache ce qu'on déclenche en écrivant un
message de commit.

## Le principe

**Le message de commit décide de la version.** Le dépôt suit les commits
conventionnels — `type(portée): sujet` — et `outils/version.py` les relit depuis
le dernier tag :

| Ce que dit le commit | Ce que fait la version |
|---|---|
| `feat: …` | avance la **mineure** — 0.2.0 → 0.3.0 |
| `fix: …`, `perf: …` | avance la **corrective** — 0.2.0 → 0.2.1 |
| `feat!: …`, ou `BREAKING CHANGE:` dans le corps | avance la **majeure** — 1.4.2 → 2.0.0 |
| `docs`, `refactor`, `test`, `chore`, `ci`, `style`, `build` | **rien** |
| message hors convention | **rien**, et ce n'est pas une erreur |

Deux points qui ne vont pas de soi :

* **En version 0, une rupture n'envoie pas en 1.0.** Elle avance la mineure
  (0.4.2 → 0.5.0). Une version 0 ne promet aucune stabilité ; le passage en 1.0
  est une décision, pas un effet de bord d'un point d'exclamation.
* **Une fusion peut ne rien publier.** Une journée de documentation ou de
  remaniement laisse la version où elle est. Un dépôt qui publie à chaque
  virgule noie ses vraies versions.

## Ce qui se passe à la fusion

`.github/workflows/publication.yml` se déclenche sur la branche par défaut :

1. les **contrôles** — ruff, mypy, pytest, les preuves lentes du solveur
   comprises. Une version ne se pose pas sur du rouge ;
2. `outils/version.py --appliquer` écrit le même numéro dans **`pyproject.toml`**,
   **`src/obqo/__init__.py`** et **`CHANGELOG.md`**, où il insère les notes
   groupées par section (Ruptures, Nouveautés, Corrections) ;
3. `uv build` construit la roue ;
4. le commit `chore(version): X.Y.Z`, le **tag `vX.Y.Z`** et la **release
   GitHub** — notes de version et roue attachée.

Le tout est poussé avec le `GITHUB_TOKEN` : GitHub ne relance pas les workflows
sur ces commits, la publication ne se rappelle donc pas elle-même.

## La mise en route, une fois pour toutes

Deux réglages du dépôt, sans lesquels le workflow tourne mais ne pousse rien :

* **Settings → Actions → General → Workflow permissions** : « Read and write
  permissions ». Le job demande `contents: write`, mais ce réglage en fixe le
  plafond — en dessous, le `git push` et le `gh release create` échouent sur un
  403.
* **un tag de départ** : `outils/version.py` compte depuis le dernier tag
  `vX.Y.Z`. Sans aucun tag, il relit tout l'historique et met tout dans les
  notes. Le dépôt porte `v0.1.0`, posé sur la dernière version d'avant la
  publication automatique.

## Voir ce que la prochaine fusion publierait

```bash
uv run python -m outils.version          # dit la version, n'écrit rien
uv run python -m outils.version --appliquer   # écrit les trois fichiers
uv run obqo --version                    # ce que le paquet installé annonce
```

Sans `--appliquer`, l'outil ne fait qu'annoncer — c'est la commande à lancer
avant de fusionner quand on veut savoir ce qu'on déclenche.

## Quand une publication échoue

Le cas déjà vu, et corrigé : une poussée humaine arrivée pendant le workflow
faisait **rejeter la branche pendant que le tag passait**. Le tag se retrouvait
sur un commit inexistant, `git describe` ne le voyait plus, et chaque
publication suivante recalculait la même version puis mourait sur
`tag already exists` (`exit 128`). La poussée est désormais `--atomic` : tout ou
rien, et la fusion suivante republie avec les bonnes notes.

S'il reste un tag orphelin d'une ancienne exécution :

```bash
git tag -l                                  # les tags connus
git merge-base --is-ancestor vX.Y.Z HEAD    # dans la branche ? sinon, orphelin
git push origin :refs/tags/vX.Y.Z           # le supprimer du dépôt
git tag -d vX.Y.Z                           # et en local
```

Rien n'est perdu : les notes se recalculent depuis le dernier tag encore
atteignable, donc la version suivante reprendra tous les commits.

## Passer en 1.0, ou corriger une version

Les deux se font à la main, et c'est voulu : ce sont des décisions.

```bash
# la version de départ de la prochaine série
sed -i 's/^version = .*/version = "1.0.0"/' pyproject.toml
sed -i 's/^__version__ = .*/__version__ = "1.0.0"/' src/obqo/__init__.py
git commit -am "chore(version): 1.0.0"
git tag -a v1.0.0 -m "obqo 1.0.0" && git push --follow-tags
```

L'outil repart du dernier tag et de la version déclarée : poser le tag suffit à
lui dire d'où compter.

## Pourquoi pas une dépendance de publication

La règle tient en trente lignes lisibles et testées
(`tests/test_version.py`) ; une chaîne de publication qu'on ne sait pas relire
finit par publier ce qu'on n'a pas voulu. C'est le même arbitrage que partout
ailleurs dans le dépôt — voir `docs/00-choix-techniques.md`.
