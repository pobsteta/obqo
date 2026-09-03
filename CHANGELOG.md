# Journal des versions

Ce fichier est écrit par la chaîne de publication : à chaque fusion sur la
branche par défaut, `outils/version.py` lit les commits conventionnels depuis le
dernier tag, en déduit la version, et insère la section correspondante ici. On
n'y écrit pas à la main — on écrit ses messages de commit.

Voir `docs/publier.md` pour la règle complète.

## 0.7.0 — 2026-09-03

### Nouveautés

- **esquisse** — ecrire la surface de chaque piece sur le dessin

## 0.6.0 — 2026-09-03

### Ruptures

- **esquisse** — nommer les cotes d'une piece longueur et largeur

## 0.5.1 — 2026-09-03

### Corrections

- **esquisse** — une piece se cote en longueur et largeur, pas en hauteur

## 0.5.0 — 2026-09-03

### Nouveautés

- **plans** — reperer les murs sur les dessins, et compter la surface

## 0.4.0 — 2026-09-03

### Nouveautés

- **esquisse** — tracer refends et cloisons a la main
- **esquisse** — une zone de saisie par onglet, et des ouvertures partout

## 0.3.0 — 2026-09-03

### Nouveautés

- **raidissement** — poser les poteaux P10 qui manquent le long d'un mur

## 0.2.1 — 2026-09-03

### Corrections

- **baies** — donner a chaque type sa hauteur de tremie

## 0.2.0 — 2026-09-02

### Nouveautés

- **esquisse** — redimensionner les baies au clavier, et ouvrir sur le dessin
- **cli** — annoncer le numero de version avec --version

## 0.1.0 — 2026-09-02

Première version : calepinage, nomenclature, métré, débit optimisé, plans SVG /
PDF A3 / DXF, vue 3D, interface web et éditeur d'esquisse.
