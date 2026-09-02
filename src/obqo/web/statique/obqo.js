// Trois interactions : soumettre un plan, changer de planche, et signaler
// l'attente. Pas de bibliotheque : le serveur renvoie du HTML deja rendu.
const resultat = document.getElementById("resultat");
const bouton = document.getElementById("calepiner");

async function remplacer(cible, reponse) {
  cible.innerHTML = await reponse.text();
}

async function calepiner() {
  bouton.disabled = true;
  resultat.innerHTML = '<p class="attente">Calepinage en cours…</p>';
  try {
    const reponse = await fetch("/etude", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan: document.getElementById("plan").value,
        exact: document.getElementById("exact").checked,
      }),
    });
    await remplacer(resultat, reponse);
    if (reponse.ok) brancherPlanches();
  } catch (erreur) {
    resultat.innerHTML =
      '<p class="constat constat--erreur">Le serveur n\'a pas répondu : ' +
      erreur.message +
      "</p>";
  } finally {
    bouton.disabled = false;
  }
}

function brancherPlanches() {
  const etude = resultat.querySelector(".etude");
  const choix = document.getElementById("choix-planche");
  const vue = document.getElementById("planche");
  if (!etude || !choix || !vue) return;

  const afficher = async () => {
    vue.innerHTML = '<p class="attente">Rendu…</p>';
    const reponse = await fetch(
      `/etude/${etude.dataset.cle}/planche/${choix.value}`
    );
    await remplacer(vue, reponse);
  };
  choix.addEventListener("change", afficher);
  afficher();
}

bouton.addEventListener("click", calepiner);

// Un plan derive d'une esquisse arrive deja rempli, avec l'ordre de partir :
// l'onglet Esquisse a fait le trajet, l'utilisateur n'a rien a recopier.
if (document.getElementById("plan").dataset.lancer) calepiner();
