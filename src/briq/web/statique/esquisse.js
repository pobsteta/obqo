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
let selection = null;
let geste = null;

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

  if (conflits.size) {
    const noms = [...conflits].map((i) => `« ${pieces[i].nom} »`).join(", ");
    etat.textContent = `${noms} se chevauchent : déplacez-en une. Une pièce ne peut pas empiéter sur sa voisine, elles se partagent un mur.`;
    etat.classList.add("etat--conflit");
  } else {
    etat.classList.remove("etat--conflit");
    etat.textContent = pieces.length
      ? `${pieces.length} pièce${pieces.length > 1 ? "s" : ""} — emprise ${emprise()}`
      : "Aucune pièce. Glissez sur le fond pour en créer une.";
  }
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
  const index = pieceSous(evenement);
  toile.setPointerCapture(evenement.pointerId);

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
  const index = pieceSous(evenement);
  if (index === null) return;
  const nom = window.prompt("Nom de la pièce", pieces[index].nom);
  if (nom) {
    pieces[index].nom = nom;
    dessiner();
  }
});

document.addEventListener("keydown", (evenement) => {
  if ((evenement.key === "Delete" || evenement.key === "Backspace") && selection !== null) {
    if (document.activeElement && document.activeElement.tagName === "TEXTAREA") return;
    pieces.splice(selection, 1);
    selection = null;
    dessiner();
  }
});

function corps() {
  return {
    nom: "esquisse",
    hauteur_sous_chainage: 2640,
    pas: pas(),
    pieces: pieces.map((p) => ({
      nom: p.nom,
      x: Math.round(p.x),
      y: Math.round(p.y),
      largeur: Math.round(p.largeur),
      hauteur: Math.round(p.hauteur),
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
  pieces = [];
  selection = null;
  dessiner();
});

dessiner();
