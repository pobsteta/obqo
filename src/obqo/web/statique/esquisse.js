// Editeur d'esquisse : des rectangles sur une grille, rien de plus.
// Le SVG travaille directement en millimetres du plan grace a son viewBox :
// pas de conversion a maintenir, seulement une inversion de matrice a la souris.
//
// Vocabulaire : l'interface dit « ouverture », comme le plan obqo, mais le code
// garde `baie` — c'est le nom du champ dans l'esquisse enregistree, et le
// renommer casserait les fichiers deja ecrits pour un simple synonyme.

const toile = document.getElementById("toile");
const etat = document.getElementById("etat");
const resultat = document.getElementById("resultat");
const MONDE = { largeur: 19200, hauteur: 14400 };
const MINI = 1920; // une piece plus petite n'a plus d'espace habitable

let pieces = [
  { nom: "séjour", x: 1920, y: 1920, largeur: 4800, hauteur: 3840 },
  { nom: "cuisine", x: 6720, y: 1920, largeur: 3840, hauteur: 3840 },
];
let baies = [];
let murs = [];
// `murs` porte les murs **deduits** que le serveur renvoie ; `traces` porte
// ceux que l'on dessine soi-meme. Les deux coexistent : le trace complete la
// deduction, il ne la remplace pas.
let traces = [];
let traceActif = null;
let mode = "pieces";
let selection = null;
let baieActive = null;
let geste = null;
const LARGEUR_MINI_BAIE = 720;
const HAUTEUR_MINI_BAIE = 240; // un rang
const RECUL_MINI_ANGLE = 480; // 240 d'appui de linteau + 240 de maconnerie
const HAUTEUR_RANG = 240;
const LIBELLES = { porte: "porte", fenetre: "fenêtre", porte_fenetre: "porte-fenêtre" };
const LIBELLES_MUR = { refend: "refend", cloison: "cloison" };
const LONGUEUR_MINI_MUR = 960;

// Cotes de tremie usuelles, reprises de `units.py`. Une porte de 1200 laisserait
// un passage ou l'on ne tient pas debout : le type doit emmener sa hauteur.
const HAUTEURS = { porte: 2160, porte_fenetre: 2160, fenetre: 1200 };
const ALLEGES = { porte: 0, porte_fenetre: 0, fenetre: 960 };
const HAUTEUR_MINI_PASSAGE = 1920; // 8 rangs

// « porte 1 » se relit dans une nomenclature ; « B1 » ne dit rien a personne.
function nomLibre(type) {
  const base = LIBELLES[type];
  let numero = 1;
  while (baies.some((b) => b.id === `${base} ${numero}`)) numero += 1;
  return `${base} ${numero}`;
}

function nomLibreMur(type) {
  const base = LIBELLES_MUR[type];
  let numero = 1;
  while (traces.some((m) => m.id === `${base} ${numero}`)) numero += 1;
  return `${base} ${numero}`;
}

const PAS_DESSIN = 240; // on dessine fin, on cale ensuite : voir le bouton « Caler »
const pas = () => Number(document.getElementById("pas").value);
const caler = (v) => Math.round(v / PAS_DESSIN) * PAS_DESSIN;

function lignesVoisines(sauf) {
  const x = new Set();
  const y = new Set();
  pieces.forEach((piece, index) => {
    if (index === sauf) return;
    x.add(piece.x).add(piece.x + piece.largeur);
    y.add(piece.y).add(piece.y + piece.hauteur);
  });
  return { x: [...x], y: [...y] };
}

// Un vide de 240 mm entre deux pieces ne se voit pas a l'ecran et coupe le
// batiment en deux. L'aimantation le rend presque impossible : un bord qui
// approche celui d'une voisine s'y colle exactement.
function aimanter(valeur, candidats) {
  let meilleur = valeur;
  let ecart = PAS_DESSIN;
  for (const candidat of candidats) {
    if (Math.abs(candidat - valeur) <= ecart) {
      ecart = Math.abs(candidat - valeur);
      meilleur = candidat;
    }
  }
  return meilleur;
}

function svg(nom, attributs) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", nom);
  for (const [cle, valeur] of Object.entries(attributs)) {
    element.setAttribute(cle, valeur);
  }
  return element;
}

function pointSouris(evenement) {
  const p = toile.createSVGPoint();
  p.x = evenement.clientX;
  p.y = evenement.clientY;
  const monde = p.matrixTransform(toile.getScreenCTM().inverse());
  return { x: monde.x, y: MONDE.hauteur - monde.y };
}

function chevauchements() {
  const conflits = new Set();
  pieces.forEach((a, i) =>
    pieces.forEach((b, j) => {
      if (
        i < j &&
        a.x < b.x + b.largeur && b.x < a.x + a.largeur &&
        a.y < b.y + b.hauteur && b.y < a.y + a.hauteur
      ) {
        conflits.add(i);
        conflits.add(j);
      }
    })
  );
  return conflits;
}

function dessiner() {
  toile.replaceChildren();
  const p = PAS_DESSIN;
  const grille = svg("g", { class: "grille" });
  for (let x = 0; x <= MONDE.largeur; x += p) {
    grille.appendChild(
      svg("line", {
        x1: x, y1: 0, x2: x, y2: MONDE.hauteur,
        class: x % 960 ? "grille__fin" : "grille__fort",
      })
    );
  }
  for (let y = 0; y <= MONDE.hauteur; y += p) {
    grille.appendChild(
      svg("line", {
        x1: 0, y1: y, x2: MONDE.largeur, y2: y,
        class: y % 960 ? "grille__fin" : "grille__fort",
      })
    );
  }
  toile.appendChild(grille);

  const conflits = chevauchements();
  pieces.forEach((piece, index) => {
    const classes =
      "piece" +
      (index === selection ? " piece--active" : "") +
      (conflits.has(index) ? " piece--conflit" : "");
    const groupe = svg("g", { class: classes });
    const yEcran = MONDE.hauteur - piece.y - piece.hauteur;
    groupe.appendChild(
      svg("rect", { x: piece.x, y: yEcran, width: piece.largeur, height: piece.hauteur })
    );
    const cx = piece.x + piece.largeur / 2;
    const cy = yEcran + piece.hauteur / 2;
    groupe.appendChild(
      Object.assign(svg("text", { x: cx, y: cy - 130, class: "piece__nom" }), {
        textContent: piece.nom,
      })
    );
    groupe.appendChild(
      Object.assign(svg("text", { x: cx, y: cy + 280, class: "piece__cote" }), {
        textContent: `${piece.largeur} × ${piece.hauteur}`,
      })
    );
    if (index === selection) {
      groupe.appendChild(
        svg("rect", {
          x: piece.x + piece.largeur - 260, y: yEcran + piece.hauteur - 260,
          width: 260, height: 260, class: "poignee",
        })
      );
    }
    groupe.dataset.index = index;
    toile.appendChild(groupe);
  });

  if (typeof memoriser === "function") memoriser();
  // Le formulaire suit l'etat comme le dessin : une seule source, un seul
  // endroit ou le rafraichir.
  montrerFormePiece();

  if (conflits.size) {
    const noms = [...conflits].map((i) => `« ${pieces[i].nom} »`).join(", ");
    etat.textContent = `${noms} se chevauchent : déplacez-en une. Une pièce ne peut pas empiéter sur sa voisine, elles se partagent un mur.`;
    etat.classList.add("etat--conflit");
  } else {
    etat.classList.remove("etat--conflit");
    // Une seule couche pour les deux modes qui travaillent sur les murs : on y
    // voit les murs, ceux traces a la main et les ouvertures ensemble.
    if (mode !== "pieces") toile.appendChild(coucheDesMurs());

  etat.textContent = pieces.length
      ? `${pieces.length} pièce${pieces.length > 1 ? "s" : ""} — emprise ${emprise()}`
      : "Aucune pièce. Glissez sur le fond pour en créer une.";
  }
}

// La couche des murs, commune aux modes « ouvertures » et « murs interieurs ».
//
// Les ouvertures y figurent dans les deux : une porte se pose en meme temps que
// le mur qui la porte, et devoir changer d'onglet entre les deux revient a
// dessiner a l'aveugle. Les etiquettes des murs traces et des ouvertures sont
// placees d'un seul coup, sinon elles s'ecriraient les unes sur les autres.
function coucheDesMurs() {
  const couche = svg("g", { class: "murs" });
  murs.forEach((mur) => {
    // En mode « murs interieurs », les refends deja deduits du dessin des
    // pieces passent en filigrane : on voit ce qu'il est inutile de retracer.
    const filigrane = mode === "murs" && mur.interieur;
    const ligne = svg("line", {
      x1: mur.depart[0], y1: MONDE.hauteur - mur.depart[1],
      x2: mur.arrivee[0], y2: MONDE.hauteur - mur.arrivee[1],
      class: filigrane ? "mur mur--deduit" : "mur" + (mur.interieur ? " mur--interieur" : ""),
    });
    ligne.dataset.mur = mur.id;
    couche.appendChild(ligne);
  });

  const traceables = mode === "murs" ? traces : [];
  // H et L sont ecrits : sur un plan, « 2160 × 960 » se lit dans les deux
  // sens, et une porte posee a l'envers se paie en menuiserie.
  const etiquettes = poserLesEtiquettes([
    ...traceables.map((m) => ({ ...m, etiquette: `${m.id} ${longueurDe(m)}` })),
    ...baies.map((b) => ({ ...b, etiquette: `${b.id} H${b.hauteur}×L${largeurDe(b)}` })),
  ]);

  const poser = (segment, classe, cle, index, pose) => {
    const ligne = svg("line", {
      x1: segment.depart[0], y1: MONDE.hauteur - segment.depart[1],
      x2: segment.arrivee[0], y2: MONDE.hauteur - segment.arrivee[1],
      class: classe,
    });
    ligne.dataset[cle] = index;
    couche.appendChild(ligne);
    couche.appendChild(
      Object.assign(
        svg("text", {
          x: pose.x,
          y: MONDE.hauteur - pose.y,
          class: "baie__cote",
          "text-anchor": pose.ancre,
          "dominant-baseline": pose.ligne,
        }),
        { textContent: pose.texte }
      )
    );
  };

  traceables.forEach((mur, index) =>
    poser(
      mur,
      `trace trace--${mur.type}` + (index === traceActif ? " trace--actif" : ""),
      "trace",
      index,
      etiquettes[index]
    )
  );
  baies.forEach((baie, index) =>
    poser(
      baie,
      "baie" + (index === baieActive ? " baie--active" : ""),
      "baie",
      index,
      etiquettes[traceables.length + index]
    )
  );
  return couche;
}

function longueurDe(mur) {
  return (
    Math.abs(mur.arrivee[0] - mur.depart[0]) + Math.abs(mur.arrivee[1] - mur.depart[1])
  );
}

function largeurDe(baie) {
  return (
    Math.abs(baie.arrivee[0] - baie.depart[0]) + Math.abs(baie.arrivee[1] - baie.depart[1])
  );
}

// Le mur qui porte la baie : celui dont le segment la contient entierement.
// Une baie relue d'un fichier ne connait que ses deux points, et un calage a pu
// deplacer le mur qu'elle citait : on le retrouve sur la geometrie du moment,
// celle que le serveur a rendue.
function murPorteur(baie) {
  const vertical = baie.depart[0] === baie.arrivee[0];
  const axe = vertical ? 1 : 0;
  const travers = vertical ? 0 : 1;
  const porteur = murs.find((mur) => {
    if ((mur.depart[0] === mur.arrivee[0]) !== vertical) return false;
    if (mur.depart[travers] !== baie.depart[travers]) return false;
    const min = Math.min(mur.depart[axe], mur.arrivee[axe]);
    const max = Math.max(mur.depart[axe], mur.arrivee[axe]);
    return [baie.depart[axe], baie.arrivee[axe]].every((v) => v >= min && v <= max);
  });
  return porteur || null;
}

// La largeur se saisit au clavier comme la hauteur : glisser a la souris donne
// la baie a peu pres, le champ la donne exactement. La rive gauche reste en
// place ; si la baie ne tient plus jusqu'au bout du mur, elle recule le long de
// celui-ci plutot que d'en sortir — un mur trop court est le seul cas ou la
// largeur demandee n'est pas tenue, et il se dit.
function redimensionnerBaie(baie, voulue) {
  const axe = baie.depart[0] === baie.arrivee[0] ? 1 : 0;
  const mur = murPorteur(baie);
  let largeur = Math.max(LARGEUR_MINI_BAIE, caler(voulue));
  let debut = Math.min(baie.depart[axe], baie.arrivee[axe]);
  let avis = "";
  if (mur) {
    const min = Math.min(mur.depart[axe], mur.arrivee[axe]);
    const max = Math.max(mur.depart[axe], mur.arrivee[axe]);
    if (largeur > max - min) {
      largeur = Math.max(LARGEUR_MINI_BAIE, max - min);
      avis = `Le mur ${mur.id} ne fait que ${max - min} mm : baie ramenée à ${largeur} mm.`;
    }
    debut = Math.min(Math.max(debut, min), max - largeur);
    baie.mur = mur.id;
  }
  const fixe = axe ? baie.depart[0] : baie.depart[1];
  baie.depart = axe ? [fixe, debut] : [debut, fixe];
  baie.arrivee = axe ? [fixe, debut + largeur] : [debut + largeur, fixe];
  return avis;
}

// Ce que la baie coute vraiment : le passage libre une fois les jambages poses,
// et les regles qu'elle enfreint deja — un plan refuse a la generation aurait
// pu se dire ici, au moment ou l'on tape la cote.
function resumeDeLaBaie(baie) {
  const tremie = largeurDe(baie);
  const passage = tremie - (tremie > 1800 ? 320 : 160);
  const mur = murPorteur(baie);
  const lignes = [
    `${baie.id} sur ${(mur && mur.id) || baie.mur || "un mur"} : trémie ` +
      `${baie.hauteur} × ${tremie} mm (h × l), passage libre ${passage} mm`,
  ];
  if (tremie > 2400) lignes.push("au-delà de 2400, linteau en lamellé-collé");
  if (baie.type !== "fenetre" && baie.hauteur < HAUTEUR_MINI_PASSAGE) {
    lignes.push(
      `${baie.hauteur} mm de haut : on ne passe plus debout en dessous de ` +
        `${HAUTEUR_MINI_PASSAGE} mm (l'usage est ${HAUTEURS.porte})`
    );
  }
  const chainage = Number(document.getElementById("hauteur-chainage").value) || 2640;
  const haut = baie.allege + baie.hauteur + HAUTEUR_RANG;
  if (haut > chainage) {
    lignes.push(
      `allège + hauteur + linteau = ${haut} mm au-dessus des ${chainage} mm ` +
        "sous chaînage : baissez l'ouverture"
    );
  }
  if (mur) {
    const axe = baie.depart[0] === baie.arrivee[0] ? 1 : 0;
    const bornes = [mur.depart[axe], mur.arrivee[axe]];
    const reculs = [
      Math.min(baie.depart[axe], baie.arrivee[axe]) - Math.min(...bornes),
      Math.max(...bornes) - Math.max(baie.depart[axe], baie.arrivee[axe]),
    ];
    const serre = Math.min(...reculs);
    if (serre < RECUL_MINI_ANGLE) {
      lignes.push(
        `rive à ${serre} mm de l'angle : ${RECUL_MINI_ANGLE} mm minimum pour ` +
          "l'appui du linteau"
      );
    }
  }
  return lignes.join(" — ");
}

const ETIQUETTE = { hauteur: 240, parCaractere: 132, ecart: 300, marge: 120 };

// Une etiquette posee toujours au-dessus de la baie se couche en travers du mur
// des qu'il est vertical — « porte d'entree 1200 » fait 2,5 m de long pour un
// mur de 240. On la decale donc perpendiculairement au mur, vers l'exterieur du
// batiment, et on l'ecarte d'un cran de plus tant qu'elle mord sur une
// etiquette deja posee.
function poserLesEtiquettes(segments) {
  const centre = centreDuBati();
  const posees = boitesDesNoms();
  return segments.map((baie) => {
    const texte = baie.etiquette;
    const largeur = texte.length * ETIQUETTE.parCaractere;
    const mx = (baie.depart[0] + baie.arrivee[0]) / 2;
    const my = (baie.depart[1] + baie.arrivee[1]) / 2;
    const vertical = baie.depart[0] === baie.arrivee[0];
    const dehors = (vertical ? mx < centre.x : my < centre.y) ? -1 : 1;
    // Deux textes horizontaux se degagent en hauteur, jamais en largeur : le
    // cran d'echappement vaut donc une ligne, pas la longueur de l'etiquette —
    // sans quoi celle d'un mur vertical part a des metres de sa baie.
    const cran = ETIQUETTE.hauteur + ETIQUETTE.marge;
    const decalages = vertical
      ? [0, cran, -cran, 2 * cran, -2 * cran]
      : [0, 1, 2, 3, 4].map((n) => n * cran * dehors);
    // Un mur au bord du cadre n'a pas d'exterieur : l'etiquette y sortirait du
    // dessin. On rentre alors du cote interieur plutot que de la perdre.
    let secours = null;
    for (const cote of [dehors, -dehors]) {
      for (const decalage of decalages) {
        const pose = vertical
          ? { texte, x: mx + cote * ETIQUETTE.ecart, y: my + decalage,
              ancre: cote < 0 ? "end" : "start", ligne: "middle" }
          : { texte, x: mx, y: my + cote * ETIQUETTE.ecart + decalage,
              ancre: "middle", ligne: cote < 0 ? "hanging" : "auto" };
        const boite = encadrer(pose, largeur);
        secours = secours || pose;
        if (!dansLeCadre(boite)) continue;
        if (!posees.some((autre) => seChevauchent(boite, autre))) {
          posees.push(boite);
          return pose;
        }
      }
    }
    return secours;
  });
}

const dansLeCadre = (b) =>
  b.x0 >= 0 && b.y0 >= 0 && b.x1 <= MONDE.largeur && b.y1 <= MONDE.hauteur;

// Le nom d'une piece et sa cote occupent deja son milieu : une etiquette de baie
// qui rentre du cote interieur doit les eviter, sinon elle se lit par-dessus.
function boitesDesNoms() {
  return pieces.map((piece) => {
    const cote = `${piece.largeur} × ${piece.hauteur}`;
    const largeur = Math.max(piece.nom.length * 190, cote.length * 145);
    const cx = piece.x + piece.largeur / 2;
    const cy = piece.y + piece.hauteur / 2;
    return { x0: cx - largeur / 2, y0: cy - 280, x1: cx + largeur / 2, y1: cy + 470 };
  });
}

// L'ancre et la ligne de base disent ou le texte tombe par rapport a son point.
function encadrer(pose, largeur) {
  const x0 =
    pose.ancre === "end" ? pose.x - largeur
    : pose.ancre === "start" ? pose.x
    : pose.x - largeur / 2;
  const y0 =
    pose.ligne === "middle" ? pose.y - ETIQUETTE.hauteur / 2
    : pose.ligne === "hanging" ? pose.y - ETIQUETTE.hauteur
    : pose.y;
  return { x0, y0, x1: x0 + largeur, y1: y0 + ETIQUETTE.hauteur };
}

const seChevauchent = (a, b) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;

function boiteDuBati() {
  return {
    x0: Math.min(...pieces.map((p) => p.x)),
    y0: Math.min(...pieces.map((p) => p.y)),
    x1: Math.max(...pieces.map((p) => p.x + p.largeur)),
    y1: Math.max(...pieces.map((p) => p.y + p.hauteur)),
  };
}

function centreDuBati() {
  if (!pieces.length) return { x: MONDE.largeur / 2, y: MONDE.hauteur / 2 };
  const b = boiteDuBati();
  return { x: (b.x0 + b.x1) / 2, y: (b.y0 + b.y1) / 2 };
}

// Projete le pointeur sur l'axe du mur le plus proche : une baie ne peut
// exister que sur un mur, autant y coller le geste des le depart.
function surLeMur(point) {
  let meilleur = null;
  let ecart = 900;
  for (const mur of murs) {
    const [ax, ay] = mur.depart;
    const [bx, by] = mur.arrivee;
    if (ax === bx) {
      const d = Math.abs(point.x - ax);
      const dans = point.y >= Math.min(ay, by) && point.y <= Math.max(ay, by);
      if (dans && d < ecart) { ecart = d; meilleur = { mur, x: ax, y: caler(point.y) }; }
    } else {
      const d = Math.abs(point.y - ay);
      const dans = point.x >= Math.min(ax, bx) && point.x <= Math.max(ax, bx);
      if (dans && d < ecart) { ecart = d; meilleur = { mur, x: caler(point.x), y: ay }; }
    }
  }
  if (!meilleur) return null;
  const [ax, ay] = meilleur.mur.depart;
  const [bx, by] = meilleur.mur.arrivee;
  meilleur.x = Math.min(Math.max(meilleur.x, Math.min(ax, bx)), Math.max(ax, bx));
  meilleur.y = Math.min(Math.max(meilleur.y, Math.min(ay, by)), Math.max(ay, by));
  return meilleur;
}

function emprise() {
  const b = boiteDuBati();
  return `${b.x1 - b.x0} × ${b.y1 - b.y0} mm hors tout`;
}

function pieceSous(evenement) {
  const groupe = evenement.target.closest("g.piece");
  return groupe ? Number(groupe.dataset.index) : null;
}

// Cliquer une ouverture la selectionne, dans les deux modes qui l'affichent.
// Selectionner ici deselectionne le mur trace : deux formulaires ouverts en
// meme temps sur deux objets differents ne se lisent pas.
function choisirUneOuverture(evenement) {
  const cible = evenement.target.dataset && evenement.target.dataset.baie;
  if (cible === undefined || cible === null || cible === "") return false;
  baieActive = Number(cible);
  traceActif = null;
  montrerFormeMur();
  montrerFormeBaie();
  dessiner();
  return true;
}

toile.addEventListener("pointerdown", (evenement) => {
  const point = pointSouris(evenement);
  toile.setPointerCapture(evenement.pointerId);

  if (mode === "murs") {
    if (choisirUneOuverture(evenement)) return;
    const surTrace = evenement.target.dataset && evenement.target.dataset.trace;
    if (surTrace !== undefined && surTrace !== null && surTrace !== "") {
      traceActif = Number(surTrace);
      baieActive = null;
      montrerFormeBaie();
      montrerFormeMur();
      dessiner();
      return;
    }
    const origine = [caler(point.x), caler(point.y)];
    // Un geste qui part d'un mur est ambigu : le long du mur c'est une
    // ouverture, en travers c'est un mur de plus. On ne tranche pas au
    // pointerdown — on attend de voir dans quel sens la souris part.
    const ancre = surLeMur(point);
    if (ancre) {
      geste = { type: "ambigu", ancre, origine };
      return;
    }
    traceActif = traces.length;
    baieActive = null;
    traces.push({
      id: nomLibreMur("refend"),
      type: "refend",
      depart: [...origine],
      arrivee: [...origine],
    });
    geste = { type: "mur", origine };
    montrerFormeBaie();
    dessiner();
    return;
  }

  if (mode === "baies") {
    if (choisirUneOuverture(evenement)) return;
    const ancre = surLeMur(point);
    if (!ancre) {
      baieActive = null;
      montrerFormeBaie();
      dessiner();
      return;
    }
    baieActive = baies.length;
    baies.push(nouvelleBaie(ancre.mur, ancre.x, ancre.y));
    geste = { type: "baie", mur: ancre.mur, origine: [ancre.x, ancre.y] };
    dessiner();
    return;
  }

  const index = pieceSous(evenement);

  if (index === null) {
    // Une piece n'apparait qu'a partir d'un vrai glissement : un simple clic
    // sur le fond deselectionne, il ne seme pas un carre de 240 a l'ecart.
    selection = null;
    const lignes = lignesVoisines(null);
    geste = {
      type: "creer",
      origine: { x: aimanter(caler(point.x), lignes.x), y: aimanter(caler(point.y), lignes.y) },
      ne: true,
    };
  } else {
    selection = index;
    const piece = pieces[index];
    const surPoignee =
      point.x > piece.x + piece.largeur - 260 && point.y < piece.y + 260;
    geste = surPoignee
      ? { type: "redimensionner" }
      : { type: "deplacer", ecart: { x: point.x - piece.x, y: point.y - piece.y } };
  }
  dessiner();
});

// Une ouverture commencante : une fenetre a l'allege usuelle, reduite a un
// point sur son mur. Le glissement lui donne sa largeur, le formulaire le reste.
function nouvelleBaie(mur, x, y) {
  return {
    id: nomLibre("fenetre"),
    type: "fenetre",
    mur: mur.id,
    depart: [x, y],
    arrivee: [x, y],
    allege: 960,
    hauteur: HAUTEURS.fenetre,
  };
}

// Le sens du geste dit ce qu'on dessine, quand il part d'un mur : **le long**
// du mur, c'est une ouverture ; **en travers**, c'est un mur de plus. C'est la
// seule lecture qui marche dans les deux cas, parce qu'un mur interieur part
// presque toujours d'un mur existant — refuser les gestes qui en partent
// interdirait de tracer, et les prendre tous pour des ouvertures aussi.
//
// Rien n'est tranche avant un deplacement d'un pas : plus tot, la direction
// n'est que du bruit de souris.
function trancherLeGeste(point) {
  const [ox, oy] = geste.origine;
  const dx = caler(point.x) - ox;
  const dy = caler(point.y) - oy;
  if (Math.max(Math.abs(dx), Math.abs(dy)) < PAS_DESSIN) return;
  const { mur, x, y } = geste.ancre;
  const vertical = mur.depart[0] === mur.arrivee[0];
  const long = vertical ? Math.abs(dy) : Math.abs(dx);
  const travers = vertical ? Math.abs(dx) : Math.abs(dy);

  if (long > travers) {
    baieActive = baies.length;
    traceActif = null;
    baies.push(nouvelleBaie(mur, x, y));
    geste = { type: "baie", mur, origine: [x, y] };
    montrerFormeMur();
    return;
  }
  traceActif = traces.length;
  baieActive = null;
  traces.push({
    id: nomLibreMur("refend"),
    type: "refend",
    depart: [ox, oy],
    arrivee: [ox, oy],
  });
  geste = { type: "mur", origine: [ox, oy] };
  montrerFormeBaie();
}

toile.addEventListener("pointermove", (evenement) => {
  if (!geste) return;
  const point = pointSouris(evenement);

  if (geste.type === "ambigu") trancherLeGeste(point);

  if (geste.type === "baie") {
    const baie = baies[baieActive];
    const [ax, ay] = geste.mur.depart;
    const [bx, by] = geste.mur.arrivee;
    if (ax === bx) {
      const y = Math.min(Math.max(caler(point.y), Math.min(ay, by)), Math.max(ay, by));
      baie.depart = [ax, Math.min(geste.origine[1], y)];
      baie.arrivee = [ax, Math.max(geste.origine[1], y)];
    } else {
      const x = Math.min(Math.max(caler(point.x), Math.min(ax, bx)), Math.max(ax, bx));
      baie.depart = [Math.min(geste.origine[0], x), ay];
      baie.arrivee = [Math.max(geste.origine[0], x), ay];
    }
    montrerFormeBaie(); // la cote se lit pendant le glissement, pas apres
    dessiner();
    return;
  }

  if (geste.ne) {
    const { origine } = geste;
    if (Math.abs(point.x - origine.x) < PAS_DESSIN && Math.abs(point.y - origine.y) < PAS_DESSIN) {
      return;
    }
    selection = pieces.length;
    pieces.push({
      nom: `pièce ${pieces.length + 1}`,
      x: origine.x, y: origine.y, largeur: PAS_DESSIN, hauteur: PAS_DESSIN,
    });
    delete geste.ne;
  }
  if (geste && geste.type === "mur") {
    // Un mur est horizontal ou vertical : le plus grand deplacement decide,
    // et l'autre axe est ramene sur l'origine. Pas de mur en biais.
    const [ox, oy] = geste.origine;
    const dx = caler(point.x) - ox;
    const dy = caler(point.y) - oy;
    const mur = traces[traceActif];
    mur.arrivee =
      Math.abs(dx) >= Math.abs(dy) ? [ox + dx, oy] : [ox, oy + dy];
    dessiner();
    return;
  }
  if (selection === null) return;
  const piece = pieces[selection];
  const lignes = lignesVoisines(selection);
  const px = aimanter(caler(point.x), lignes.x);
  const py = aimanter(caler(point.y), lignes.y);

  if (geste.type === "creer") {
    const { origine } = geste;
    piece.x = Math.min(origine.x, px);
    piece.y = Math.min(origine.y, py);
    piece.largeur = Math.max(PAS_DESSIN, Math.abs(px - origine.x));
    piece.hauteur = Math.max(PAS_DESSIN, Math.abs(py - origine.y));
  } else if (geste.type === "deplacer") {
    const x = Math.max(0, caler(point.x - geste.ecart.x));
    const y = Math.max(0, caler(point.y - geste.ecart.y));
    piece.x = aimanter(x, [...lignes.x, ...lignes.x.map((v) => v - piece.largeur)]);
    piece.y = aimanter(y, [...lignes.y, ...lignes.y.map((v) => v - piece.hauteur)]);
  } else {
    piece.largeur = Math.max(PAS_DESSIN, px - piece.x);
    piece.hauteur = Math.max(PAS_DESSIN, piece.y + piece.hauteur - py);
    piece.y = Math.min(piece.y, py);
  }
  dessiner();
});

toile.addEventListener("pointerup", () => {
  if (geste && geste.type === "ambigu") {
    // Un clic sans glissement sur un mur : rien a creer, seulement deselectionner.
    geste = null;
    baieActive = null;
    traceActif = null;
    montrerFormeBaie();
    montrerFormeMur();
    dessiner();
    return;
  }
  if (geste && geste.type === "mur") {
    const mur = traces[traceActif];
    let avis;
    if (longueurDe(mur) < LONGUEUR_MINI_MUR) {
      traces.splice(traceActif, 1);
      traceActif = null;
      avis = `Un mur fait ${LONGUEUR_MINI_MUR} mm au minimum : glissez pour le tracer.`;
    } else {
      avis = resumeDuMur(mur);
    }
    geste = null;
    montrerFormeMur();
    dessiner();
    etat.textContent = avis;
    return;
  }
  if (geste && geste.type === "baie") {
    const baie = baies[baieActive];
    let avis;
    if (largeurDe(baie) < LARGEUR_MINI_BAIE) {
      baies.splice(baieActive, 1);
      baieActive = null;
      avis = `Une ouverture fait ${LARGEUR_MINI_BAIE} mm au minimum : glissez le long du mur, ou tapez sa largeur.`;
    } else {
      avis = resumeDeLaBaie(baie);
    }
    geste = null;
    montrerFormeBaie();
    dessiner();
    // Apres « dessiner », qui reecrit la barre d'etat avec le compte des pieces.
    etat.textContent = avis;
    return;
  }
  if (geste && !geste.ne && selection !== null) {
    const piece = pieces[selection];
    if (piece.largeur < MINI || piece.hauteur < MINI) {
      etat.textContent = `« ${piece.nom} » fait ${piece.largeur} × ${piece.hauteur} : au moins ${MINI} mm dans chaque sens pour rester habitable.`;
    }
  }
  geste = null;
  dessiner();
});

toile.addEventListener("dblclick", (evenement) => {
  if (mode !== "pieces") {
    const cible = evenement.target.dataset && evenement.target.dataset.baie;
    if (cible === undefined || cible === null || cible === "") return;
    const index = Number(cible);
    const nom = window.prompt("Nom de l'ouverture", baies[index].id);
    if (nom && !baies.some((b, i) => i !== index && b.id === nom.trim())) {
      baies[index].id = nom.trim();
      baieActive = index;
      montrerFormeBaie();
      dessiner();
    }
    return;
  }
  const index = pieceSous(evenement);
  if (index === null) return;
  const nom = window.prompt("Nom de la pièce", pieces[index].nom);
  if (nom) {
    pieces[index].nom = nom;
    dessiner();
  }
});

document.addEventListener("keydown", (evenement) => {
  if (evenement.key !== "Delete" && evenement.key !== "Backspace") return;
  const actif = document.activeElement;
  if (actif && (actif.tagName === "TEXTAREA" || actif.tagName === "INPUT")) return;
  if (mode !== "pieces" && baieActive !== null) {
    baies.splice(baieActive, 1);
    baieActive = null;
    montrerFormeBaie();
    dessiner();
  } else if (mode === "murs" && traceActif !== null) {
    traces.splice(traceActif, 1);
    traceActif = null;
    montrerFormeMur();
    dessiner();
  } else if (mode === "baies" && baieActive !== null) {
    baies.splice(baieActive, 1);
    baieActive = null;
    montrerFormeBaie();
    dessiner();
  } else if (mode === "pieces" && selection !== null) {
    pieces.splice(selection, 1);
    selection = null;
    dessiner();
  }
});

// --- la piece selectionnee ---------------------------------------------------
//
// Meme principe que pour les ouvertures : la souris pose la piece a peu pres,
// les champs la posent exactement. Un plan se saisit souvent depuis des cotes
// relevees — « le sejour fait 4,80 sur 3,84 » — et les retrouver a la souris au
// pas de 240 est un exercice inutile.

function montrerFormePiece() {
  const forme = document.getElementById("forme-piece");
  if (mode !== "pieces" || selection === null || !pieces[selection]) {
    forme.hidden = true;
    return;
  }
  const piece = pieces[selection];
  forme.hidden = false;
  document.getElementById("piece-nom").value = piece.nom;
  document.getElementById("piece-largeur").value = piece.largeur;
  document.getElementById("piece-hauteur").value = piece.hauteur;
  document.getElementById("piece-x").value = piece.x;
  document.getElementById("piece-y").value = piece.y;
  document.getElementById("piece-resume").textContent = resumeDeLaPiece(piece);
}

function resumeDeLaPiece(piece) {
  const surface = (piece.largeur * piece.hauteur) / 1e6;
  const lignes = [
    `« ${piece.nom} » : ${piece.largeur} × ${piece.hauteur} mm d'axe à axe, ` +
      `${surface.toFixed(1).replace(".", ",")} m² hors murs`,
  ];
  if (Math.min(piece.largeur, piece.hauteur) < MINI) {
    lignes.push(
      `moins de ${MINI} mm dans un sens : les murs qui la bordent ne lui ` +
        "laisseraient presque pas d'espace habitable"
    );
  }
  if (chevauchements().has(selection)) {
    lignes.push("elle chevauche une voisine : deux pièces se touchent, ne se recouvrent pas");
  }
  return lignes.join(" — ");
}

// Les cotes se calent sur 240 comme le dessin ; « Caler » ramenera l'ensemble
// sur 480 si on le lui demande.
const CHAMPS_DE_PIECE = {
  largeur: (piece, valeur) => {
    piece.largeur = Math.max(PAS_DESSIN, valeur);
  },
  hauteur: (piece, valeur) => {
    piece.hauteur = Math.max(PAS_DESSIN, valeur);
  },
  x: (piece, valeur) => {
    piece.x = Math.max(0, valeur);
  },
  y: (piece, valeur) => {
    piece.y = Math.max(0, valeur);
  },
};

for (const champ of Object.keys(CHAMPS_DE_PIECE)) {
  document.getElementById(`piece-${champ}`).addEventListener("change", (evenement) => {
    if (selection === null) return;
    CHAMPS_DE_PIECE[champ](pieces[selection], caler(Number(evenement.target.value) || 0));
    montrerFormePiece();
    dessiner();
  });
}

document.getElementById("piece-nom").addEventListener("change", (evenement) => {
  if (selection === null) return;
  const nom = evenement.target.value.trim();
  if (!nom) {
    etat.textContent = "Une pièce doit porter un nom.";
    montrerFormePiece();
    return;
  }
  pieces[selection].nom = nom;
  montrerFormePiece();
  dessiner();
});

document.getElementById("piece-supprimer").addEventListener("click", () => {
  if (selection === null) return;
  pieces.splice(selection, 1);
  selection = null;
  montrerFormePiece();
  dessiner();
});

const forme = document.getElementById("forme-baie");

function montrerFormeBaie() {
  // Le mode « murs interieurs » affiche et modifie les ouvertures lui aussi :
  // seul le mode « pieces » ne les connait pas.
  if (mode === "pieces" || baieActive === null || !baies[baieActive]) {
    forme.hidden = true;
    return;
  }
  const baie = baies[baieActive];
  forme.hidden = false;
  document.getElementById("baie-nom").value = baie.id;
  document.getElementById("baie-type").value = baie.type;
  document.getElementById("baie-allege").value = baie.allege;
  document.getElementById("baie-hauteur").value = baie.hauteur;
  document.getElementById("baie-largeur").value = largeurDe(baie);
  document.getElementById("baie-allege").disabled = baie.type !== "fenetre";

  // Les cotes portent sur la tremie : rappeler le passage libre evite la
  // porte de 800 qu'on croyait a 960.
  document.getElementById("baie-resume").textContent = resumeDeLaBaie(baie);
}

// Une cote tapee au clavier passe par la grille de 240 comme celle tiree a la
// souris : le pas du champ n'est qu'une aide aux fleches, rien n'empeche de
// saisir 1 250 — que le plan derive refuserait ensuite (HORS-GRILLE).
const MINIMA = { allege: 0, hauteur: HAUTEUR_MINI_BAIE, largeur: LARGEUR_MINI_BAIE };

for (const champ of ["type", "allege", "hauteur", "largeur"]) {
  document.getElementById(`baie-${champ}`).addEventListener("change", (evenement) => {
    if (baieActive === null) return;
    const valeur = evenement.target.value;
    const baie = baies[baieActive];
    const nomAuto = Object.values(LIBELLES).some((l) => baie.id.startsWith(`${l} `));
    let avis = "";
    if (champ === "type") {
      // Une cote encore automatique suit le type, comme le nom : elle ne bouge
      // que si elle vaut encore l'usuelle de l'ancien type. Sans quoi une porte
      // repassee en fenetre gardait une allege de zero, qui n'etait pas un
      // choix mais le reste de la regle ci-dessous.
      if (baie.hauteur === HAUTEURS[baie.type]) baie.hauteur = HAUTEURS[valeur];
      if (baie.allege === ALLEGES[baie.type]) baie.allege = ALLEGES[valeur];
      baie.type = valeur;
      // La regle, elle, ne se discute pas : une porte part du sol.
      if (valeur !== "fenetre") baie.allege = 0;
      // Un nom encore automatique suit le type ; un nom choisi ne bouge pas.
      if (nomAuto) baie.id = nomLibre(valeur);
    } else {
      const cote = Math.max(MINIMA[champ], caler(Number(valeur) || 0));
      // La largeur n'est pas une propriete de la baie : c'est la longueur de son
      // segment sur le mur. La regler, c'est deplacer sa rive droite.
      if (champ === "largeur") avis = redimensionnerBaie(baie, cote);
      else baie[champ] = cote;
    }
    montrerFormeBaie();
    dessiner();
    // « dessiner » reecrit la barre d'etat : le mot du champ passe apres.
    if (avis) etat.textContent = avis;
  });
}

document.getElementById("baie-nom").addEventListener("change", (evenement) => {
  if (baieActive === null) return;
  const nom = evenement.target.value.trim();
  if (!nom) {
    etat.textContent = "Une ouverture doit porter un nom.";
    montrerFormeBaie();
    return;
  }
  if (baies.some((b, i) => i !== baieActive && b.id === nom)) {
    etat.textContent = `« ${nom} » est déjà pris par une autre ouverture.`;
    montrerFormeBaie();
    return;
  }
  baies[baieActive].id = nom;
  montrerFormeBaie();
  dessiner();
});

document.getElementById("baie-supprimer").addEventListener("click", () => {
  if (baieActive === null) return;
  baies.splice(baieActive, 1);
  baieActive = null;
  montrerFormeBaie();
  dessiner();
});

async function chargerMurs() {
  const reponse = await poster("/esquisse/murs");
  const donnees = await reponse.json();
  murs = donnees.murs || [];
  if (donnees.erreur) etat.textContent = donnees.erreur;
  dessiner();
}

// Ce qu'un mur trace coute vraiment : porteur ou non, et pourquoi.
function resumeDuMur(mur) {
  const sens = mur.depart[0] === mur.arrivee[0] ? "vertical" : "horizontal";
  const lignes = [`${mur.id} : ${sens}, ${longueurDe(mur)} mm`];
  if (mur.type === "refend") {
    lignes.push(
      "refend porteur : il doit rejoindre le contour par ses deux bouts pour " +
        "s'y ancrer, sinon la conversion le repassera en cloison"
    );
  } else {
    lignes.push("cloison légère : dessinée sur les plans, hors calepinage");
  }
  return lignes.join(" — ");
}

function montrerFormeMur() {
  const forme = document.getElementById("forme-mur");
  if (traceActif === null || !traces[traceActif]) {
    forme.hidden = true;
    return;
  }
  const mur = traces[traceActif];
  forme.hidden = false;
  document.getElementById("mur-nom").value = mur.id;
  document.getElementById("mur-type").value = mur.type;
  document.getElementById("mur-longueur").value = longueurDe(mur);
  document.getElementById("mur-resume").textContent = resumeDuMur(mur);
}

function redimensionnerMur(mur, longueur) {
  const vertical = mur.depart[0] === mur.arrivee[0];
  const [ox, oy] = mur.depart;
  const sens = vertical
    ? Math.sign(mur.arrivee[1] - oy) || 1
    : Math.sign(mur.arrivee[0] - ox) || 1;
  mur.arrivee = vertical ? [ox, oy + sens * longueur] : [ox + sens * longueur, oy];
}

for (const champ of ["type", "longueur"]) {
  document.getElementById(`mur-${champ}`).addEventListener("change", (evenement) => {
    if (traceActif === null) return;
    const mur = traces[traceActif];
    const nomAuto = Object.values(LIBELLES_MUR).some((l) => mur.id.startsWith(`${l} `));
    if (champ === "type") {
      mur.type = evenement.target.value;
      // Un nom encore automatique suit le type, comme pour une baie.
      if (nomAuto) mur.id = nomLibreMur(mur.type);
    } else {
      const valeur = Math.max(LONGUEUR_MINI_MUR, caler(Number(evenement.target.value) || 0));
      redimensionnerMur(mur, valeur);
    }
    montrerFormeMur();
    dessiner();
    etat.textContent = resumeDuMur(mur);
  });
}

document.getElementById("mur-nom").addEventListener("change", (evenement) => {
  if (traceActif === null) return;
  const nom = evenement.target.value.trim();
  if (!nom) {
    etat.textContent = "Un mur doit porter un nom.";
    montrerFormeMur();
    return;
  }
  if (traces.some((m, i) => i !== traceActif && m.id === nom)) {
    etat.textContent = `« ${nom} » est déjà pris par un autre mur.`;
    montrerFormeMur();
    return;
  }
  traces[traceActif].id = nom;
  montrerFormeMur();
  dessiner();
});

document.getElementById("mur-supprimer").addEventListener("click", () => {
  if (traceActif === null) return;
  traces.splice(traceActif, 1);
  traceActif = null;
  montrerFormeMur();
  dessiner();
});

function basculer(nouveau) {
  mode = nouveau;
  for (const nom of ["pieces", "baies", "murs"]) {
    document.getElementById(`mode-${nom}`).classList.toggle("mode--actif", mode === nom);
  }
  // Les deux modes qui travaillent sur les murs grisent les pieces de la meme
  // facon : la classe reste `mode-baies`, c'est elle que la feuille connait.
  document.body.classList.toggle("mode-baies", mode !== "pieces");
  selection = null;
  baieActive = null;
  traceActif = null;
  montrerFormeBaie();
  montrerFormeMur();
  if (mode !== "pieces") chargerMurs();
  else dessiner();
}

document.getElementById("mode-pieces").addEventListener("click", () => basculer("pieces"));
document.getElementById("mode-baies").addEventListener("click", () => basculer("baies"));
document.getElementById("mode-murs").addEventListener("click", () => basculer("murs"));

const MEMOIRE = "obqo.esquisse";

function identite() {
  return {
    nom: document.getElementById("nom-esquisse").value.trim() || "esquisse",
    hauteur_sous_chainage: Number(document.getElementById("hauteur-chainage").value) || 2640,
  };
}

function corps() {
  return {
    ...identite(),
    pas: pas(),
    pieces: pieces.map((p) => ({
      nom: p.nom,
      x: Math.round(p.x),
      y: Math.round(p.y),
      largeur: Math.round(p.largeur),
      hauteur: Math.round(p.hauteur),
    })),
    baies: baies.map((b) => ({
      id: b.id,
      type: b.type,
      depart: b.depart.map(Math.round),
      arrivee: b.arrivee.map(Math.round),
      allege: b.allege,
      hauteur: b.hauteur,
    })),
    murs: traces.map((m) => ({
      id: m.id,
      type: m.type,
      depart: m.depart.map(Math.round),
      arrivee: m.arrivee.map(Math.round),
    })),
  };
}

function pretADeriver() {
  if (!pieces.length) {
    etat.textContent = "Dessinez au moins une pièce.";
    return false;
  }
  if (chevauchements().size) {
    dessiner();
    return false;
  }
  return true;
}

async function poster(chemin) {
  return fetch(chemin, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corps()),
  });
}

document.getElementById("caler").addEventListener("click", async () => {
  if (!pretADeriver()) return;
  const reponse = await poster("/esquisse/caler");
  const donnees = await reponse.json();
  if (donnees.erreur) {
    etat.textContent = donnees.erreur;
    return;
  }
  pieces = donnees.pieces;
  traces = donnees.murs || traces;
  selection = null;
  traceActif = null;
  montrerFormeMur();
  dessiner();
  etat.textContent = donnees.ajustements.length
    ? `${donnees.ajustements.length} pièce(s) recalée(s) : ` + donnees.ajustements.join(" · ")
    : "Rien à recaler : le dessin tombait déjà juste.";
});

document.getElementById("generer").addEventListener("click", async () => {
  if (!pretADeriver()) return;
  resultat.innerHTML = '<p class="attente">Conversion en cours…</p>';
  const reponse = await poster("/esquisse/plan");
  resultat.innerHTML = await reponse.text();
  const copier = document.getElementById("copier");
  if (copier) {
    copier.addEventListener("click", () => {
      navigator.clipboard.writeText(document.getElementById("source-derivee").value);
      copier.textContent = "Copié";
    });
  }
});

document.getElementById("vider").addEventListener("click", () => {
  if (pieces.length && !window.confirm("Effacer toutes les pièces, les murs et les ouvertures ?")) return;
  pieces = [];
  baies = [];
  traces = [];
  selection = null;
  baieActive = null;
  traceActif = null;
  montrerFormeBaie();
  montrerFormeMur();
  dessiner();
});

// Un rafraichissement de page ne doit pas coûter une demi-heure de dessin.
// Les murs traces a la main en font partie : `restaurer` les relit sous la clef
// `murs`, et les oublier ici les faisait disparaitre au moindre aller-retour
// par l'onglet « Plan » — qui recharge la page.
function memoriser() {
  try {
    window.localStorage.setItem(
      MEMOIRE,
      JSON.stringify({ ...identite(), pieces, baies, murs: traces })
    );
  } catch (erreur) {
    // Navigation privee ou stockage plein : l'editeur marche quand meme.
  }
}

function restaurer() {
  try {
    const garde = window.localStorage.getItem(MEMOIRE);
    if (!garde) return false;
    const donnees = JSON.parse(garde);
    if (!Array.isArray(donnees.pieces) || !donnees.pieces.length) return false;
    pieces = donnees.pieces;
    baies = donnees.baies || [];
    traces = donnees.murs || [];
    document.getElementById("nom-esquisse").value = donnees.nom || "Ma maison";
    document.getElementById("hauteur-chainage").value = donnees.hauteur_sous_chainage || 2640;
    return true;
  } catch (erreur) {
    return false;
  }
}

function appliquer(donnees) {
  pieces = donnees.pieces || [];
  baies = donnees.baies || [];
  traces = donnees.murs || [];
  document.getElementById("nom-esquisse").value = donnees.nom || "Ma maison";
  document.getElementById("hauteur-chainage").value = donnees.hauteur_sous_chainage || 2640;
  selection = null;
  baieActive = null;
  traceActif = null;
  montrerFormeBaie();
  montrerFormeMur();
  if (mode !== "pieces") chargerMurs();
  else dessiner();
}

document.getElementById("enregistrer").addEventListener("click", async () => {
  const reponse = await poster("/esquisse/fichier");
  if (!reponse.ok) {
    const donnees = await reponse.json();
    etat.textContent = donnees.erreur || "enregistrement impossible";
    return;
  }
  const texte = await reponse.text();
  const lien = document.createElement("a");
  lien.href = URL.createObjectURL(new Blob([texte], { type: "application/yaml" }));
  lien.download = `${identite().nom.replace(/[^\w-]+/g, "-").toLowerCase()}.esquisse.yaml`;
  lien.click();
  URL.revokeObjectURL(lien.href);
  etat.textContent = `Esquisse enregistrée sous ${lien.download}.`;
});

document.getElementById("ouvrir").addEventListener("change", async (evenement) => {
  const fichier = evenement.target.files[0];
  if (!fichier) return;
  const reponse = await fetch("/esquisse/ouvrir", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source: await fichier.text() }),
  });
  const donnees = await reponse.json();
  if (!reponse.ok) {
    etat.textContent = donnees.erreur || "fichier illisible";
    return;
  }
  appliquer(donnees);
  etat.textContent = `« ${donnees.nom} » ouverte : ${pieces.length} pièces, ${baies.length} baies.`;
  evenement.target.value = "";
});

for (const champ of ["nom-esquisse", "hauteur-chainage"]) {
  document.getElementById(champ).addEventListener("change", memoriser);
}

restaurer();
dessiner();
