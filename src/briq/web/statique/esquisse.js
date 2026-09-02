// Editeur d'esquisse : des rectangles sur une grille, rien de plus.
// Le SVG travaille directement en millimetres du plan grace a son viewBox :
// pas de conversion a maintenir, seulement une inversion de matrice a la souris.

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
let mode = "pieces";
let selection = null;
let baieActive = null;
let geste = null;
const LARGEUR_MINI_BAIE = 720;
const LIBELLES = { porte: "porte", fenetre: "fenêtre", porte_fenetre: "porte-fenêtre" };

// « porte 1 » se relit dans une nomenclature ; « B1 » ne dit rien a personne.
function nomLibre(type) {
  const base = LIBELLES[type];
  let numero = 1;
  while (baies.some((b) => b.id === `${base} ${numero}`)) numero += 1;
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

  if (conflits.size) {
    const noms = [...conflits].map((i) => `« ${pieces[i].nom} »`).join(", ");
    etat.textContent = `${noms} se chevauchent : déplacez-en une. Une pièce ne peut pas empiéter sur sa voisine, elles se partagent un mur.`;
    etat.classList.add("etat--conflit");
  } else {
    etat.classList.remove("etat--conflit");
    if (mode === "baies") {
    const couche = svg("g", { class: "murs" });
    murs.forEach((mur) => {
      const ligne = svg("line", {
        x1: mur.depart[0], y1: MONDE.hauteur - mur.depart[1],
        x2: mur.arrivee[0], y2: MONDE.hauteur - mur.arrivee[1],
        class: "mur" + (mur.interieur ? " mur--interieur" : ""),
      });
      ligne.dataset.mur = mur.id;
      couche.appendChild(ligne);
    });
    baies.forEach((baie, index) => {
      const ligne = svg("line", {
        x1: baie.depart[0], y1: MONDE.hauteur - baie.depart[1],
        x2: baie.arrivee[0], y2: MONDE.hauteur - baie.arrivee[1],
        class: "baie" + (index === baieActive ? " baie--active" : ""),
      });
      ligne.dataset.baie = index;
      couche.appendChild(ligne);
      const mx = (baie.depart[0] + baie.arrivee[0]) / 2;
      const my = MONDE.hauteur - (baie.depart[1] + baie.arrivee[1]) / 2;
      couche.appendChild(
        Object.assign(svg("text", { x: mx, y: my - 260, class: "baie__cote" }), {
          textContent: `${baie.id} ${largeurDe(baie)}`,
        })
      );
    });
    toile.appendChild(couche);
  }

  etat.textContent = pieces.length
      ? `${pieces.length} pièce${pieces.length > 1 ? "s" : ""} — emprise ${emprise()}`
      : "Aucune pièce. Glissez sur le fond pour en créer une.";
  }
}

function largeurDe(baie) {
  return (
    Math.abs(baie.arrivee[0] - baie.depart[0]) + Math.abs(baie.arrivee[1] - baie.depart[1])
  );
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
  const x0 = Math.min(...pieces.map((p) => p.x));
  const y0 = Math.min(...pieces.map((p) => p.y));
  const x1 = Math.max(...pieces.map((p) => p.x + p.largeur));
  const y1 = Math.max(...pieces.map((p) => p.y + p.hauteur));
  return `${x1 - x0} × ${y1 - y0} mm hors tout`;
}

function pieceSous(evenement) {
  const groupe = evenement.target.closest("g.piece");
  return groupe ? Number(groupe.dataset.index) : null;
}

toile.addEventListener("pointerdown", (evenement) => {
  const point = pointSouris(evenement);
  toile.setPointerCapture(evenement.pointerId);

  if (mode === "baies") {
    const surBaie = evenement.target.dataset && evenement.target.dataset.baie;
    if (surBaie !== undefined && surBaie !== null && surBaie !== "") {
      baieActive = Number(surBaie);
      montrerFormeBaie();
      restaurer();
dessiner();
      return;
    }
    const ancre = surLeMur(point);
    if (!ancre) {
      baieActive = null;
      montrerFormeBaie();
      dessiner();
      return;
    }
    baieActive = baies.length;
    baies.push({
      id: nomLibre("fenetre"),
      type: "fenetre",
      mur: ancre.mur.id,
      depart: [ancre.x, ancre.y],
      arrivee: [ancre.x, ancre.y],
      allege: 960,
      hauteur: 1200,
    });
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

toile.addEventListener("pointermove", (evenement) => {
  if (!geste) return;
  const point = pointSouris(evenement);

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
  if (geste && geste.type === "baie") {
    const baie = baies[baieActive];
    if (largeurDe(baie) < LARGEUR_MINI_BAIE) {
      baies.splice(baieActive, 1);
      baieActive = null;
      etat.textContent = `Une baie fait ${LARGEUR_MINI_BAIE} mm au minimum : glissez le long du mur.`;
    } else {
      etat.textContent = `${baie.id} : ${largeurDe(baie)} mm de trémie, passage libre ${largeurDe(baie) - (largeurDe(baie) > 1800 ? 320 : 160)} mm.`;
    }
    geste = null;
    montrerFormeBaie();
    dessiner();
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
  if (mode === "baies") {
    const cible = evenement.target.dataset && evenement.target.dataset.baie;
    if (cible === undefined || cible === null || cible === "") return;
    const index = Number(cible);
    const nom = window.prompt("Nom de la baie", baies[index].id);
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
  if (mode === "baies" && baieActive !== null) {
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

const forme = document.getElementById("forme-baie");

function montrerFormeBaie() {
  if (mode !== "baies" || baieActive === null || !baies[baieActive]) {
    forme.hidden = true;
    return;
  }
  const baie = baies[baieActive];
  forme.hidden = false;
  document.getElementById("baie-nom").value = baie.id;
  document.getElementById("baie-type").value = baie.type;
  document.getElementById("baie-allege").value = baie.allege;
  document.getElementById("baie-hauteur").value = baie.hauteur;
  document.getElementById("baie-allege").disabled = baie.type !== "fenetre";

  // Les cotes portent sur la tremie : rappeler le passage libre evite la
  // porte de 800 qu'on croyait a 960.
  const tremie = largeurDe(baie);
  const passage = tremie - (tremie > 1800 ? 320 : 160);
  const linteau = tremie > 2400 ? " — au-delà de 2400, linteau en lamellé-collé" : "";
  document.getElementById("baie-resume").textContent =
    `${baie.id} sur ${baie.mur || "un mur"} : trémie ${tremie} mm, passage libre ${passage} mm${linteau}`;
}

for (const champ of ["type", "allege", "hauteur"]) {
  document.getElementById(`baie-${champ}`).addEventListener("change", (evenement) => {
    if (baieActive === null) return;
    const valeur = evenement.target.value;
    const baie = baies[baieActive];
    const nomAuto = Object.values(LIBELLES).some((l) => baie.id.startsWith(`${l} `));
    baie[champ] = champ === "type" ? valeur : Number(valeur);
    if (champ === "type") {
      if (valeur !== "fenetre") baie.allege = 0;
      // Un nom encore automatique suit le type ; un nom choisi ne bouge pas.
      if (nomAuto) baie.id = nomLibre(valeur);
    }
    montrerFormeBaie();
    dessiner();
  });
}

document.getElementById("baie-nom").addEventListener("change", (evenement) => {
  if (baieActive === null) return;
  const nom = evenement.target.value.trim();
  if (!nom) {
    etat.textContent = "Une baie doit porter un nom.";
    montrerFormeBaie();
    return;
  }
  if (baies.some((b, i) => i !== baieActive && b.id === nom)) {
    etat.textContent = `« ${nom} » est déjà pris par une autre baie.`;
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

function basculer(nouveau) {
  mode = nouveau;
  document.getElementById("mode-pieces").classList.toggle("mode--actif", mode === "pieces");
  document.getElementById("mode-baies").classList.toggle("mode--actif", mode === "baies");
  document.body.classList.toggle("mode-baies", mode === "baies");
  selection = null;
  baieActive = null;
  montrerFormeBaie();
  if (mode === "baies") chargerMurs();
  else dessiner();
}

document.getElementById("mode-pieces").addEventListener("click", () => basculer("pieces"));
document.getElementById("mode-baies").addEventListener("click", () => basculer("baies"));

const MEMOIRE = "briq.esquisse";

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
  selection = null;
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
  if (pieces.length && !window.confirm("Effacer toutes les pièces et les baies ?")) return;
  pieces = [];
  baies = [];
  selection = null;
  baieActive = null;
  montrerFormeBaie();
  dessiner();
});

// Un rafraichissement de page ne doit pas coûter une demi-heure de dessin.
function memoriser() {
  try {
    window.localStorage.setItem(MEMOIRE, JSON.stringify({ ...identite(), pieces, baies }));
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
  document.getElementById("nom-esquisse").value = donnees.nom || "Ma maison";
  document.getElementById("hauteur-chainage").value = donnees.hauteur_sous_chainage || 2640;
  selection = null;
  baieActive = null;
  montrerFormeBaie();
  if (mode === "baies") chargerMurs();
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
