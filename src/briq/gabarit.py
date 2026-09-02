"""Plan de depart commente, servi par `briq gabarit`."""

from __future__ import annotations

GABARIT = """\
# Plan BRIQ — modifier les cotes, puis : briq valider ce-fichier.yaml
# Methode de saisie pas a pas : docs/saisir-un-plan.md
#
# TOUTES LES COTES SONT EN MILLIMETRES, MULTIPLES DE 240.
# Preferer des multiples de 480 pour les longueurs de murs : cela evite des
# demi-briques, dont certaines en position d'angle que le catalogue ne couvre pas.

nom: Ma maison

# Hauteur sous chainage, multiple de 240. 2640 = 11 rangs.
hauteur_sous_chainage: 2640

# Contour = nu EXTERIEUR des murs, saisi par deplacements successifs.
# Le trace doit se refermer sur son point de depart : l'application le verifie.
contour:
  trace:
    depart: [0, 0]
    segments:
      - {direction: est,   longueur: 9600}   # M1 — facade sud
      - {direction: nord,  longueur: 7200}   # M2 — pignon est
      - {direction: ouest, longueur: 9600}   # M3 — facade nord
      - {direction: sud,   longueur: 7200}   # M4 — pignon ouest

# Refends porteurs. Les deux extremites doivent tomber sur le contour.
# Un refend compte comme raidisseur : un mur ne peut pas depasser 6 m sans
# refend ni baie.
refends:
  - {id: R1, depart: [4800, 0], arrivee: [4800, 7200]}

# Baies. Les cotes portent sur la TREMIE, pas sur le passage libre :
# les jambages se logent dedans et retirent 160 mm (320 au-dela de 1800).
#   tremie 960 -> passage 800    tremie 1680 -> passage 1520
#   tremie 1200 -> passage 1040  tremie 1920 -> passage 1600
#   tremie 1440 -> passage 1280  tremie 2400 -> passage 2080
# Contraintes : rive a 480 mm minimum d'un angle, 480 mm minimum de trumeau
# entre deux baies, tremie de 2400 maxi pour un linteau cheville, et
# allege + hauteur + 240 (le linteau) au plus egal a la hauteur sous chainage.
ouvertures:
  - id: P-entree
    mur: M1
    type: porte
    position: 2880
    largeur: 1200      # passage libre 1040
    hauteur: 2160
  - id: F-sud
    mur: M1
    type: fenetre
    position: 6240
    largeur: 1440      # passage libre 1280
    allege: 960
    hauteur: 1200
  - {id: F-est,  mur: M2, type: fenetre, position: 2880, largeur: 1200, allege: 960, hauteur: 1200}
  - {id: F-nord, mur: M3, type: fenetre, position: 2880, largeur: 1440, allege: 960, hauteur: 1200}
  - {id: F-ouest, mur: M4, type: fenetre, position: 2880, largeur: 1200, allege: 960, hauteur: 1200}
  - {id: P-couloir, mur: R1, type: porte, position: 3120, largeur: 960, hauteur: 2160}

parametres:
  longueur_barre: 4000              # voir docs/etudes/longueur-de-barre.md
  trait_de_scie: 4                  # largeur reelle de la lame
  chute_minimale_reutilisable: 240
  hors_grille: refuser              # ou « arrondir » pour recaler les baies
"""
