/**
 * component-loader.js
 * Injecte les fragments HTML partagés (sidebar, topbar) déclarés dans
 * components/, afin d'éviter la duplication entre les 8 pages de SIOU.
 *
 * Nécessite d'être servi via un serveur HTTP (fetch ne fonctionne pas en
 * file://). En développement : `python -m http.server` à la racine du projet.
 *
 * Marque automatiquement le lien de navigation actif à partir de
 * l'attribut [data-page] posé sur <body>.
 */

const COMPONENTS_BASE = '/components';

async function injectComponent(placeholderSelector, file) {
  const placeholder = document.querySelector(placeholderSelector);
  if (!placeholder) return;

  try {
    const response = await fetch(`${COMPONENTS_BASE}/${file}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    placeholder.innerHTML = await response.text();
  } catch (error) {
    console.error(`[component-loader] Échec du chargement de "${file}"`, error);
    placeholder.innerHTML = `<p class="sr-only">Un composant d'interface n'a pas pu être chargé.</p>`;
  }
}

function markActiveNavLink() {
  const currentPage = document.body.dataset.page;
  if (!currentPage) return;
  document.querySelectorAll('[data-nav]').forEach((link) => {
    const isActive = link.dataset.nav === currentPage;
    link.classList.toggle('is-active', isActive);
    if (isActive) link.setAttribute('aria-current', 'page');
  });
}

/**
 * Charge tous les composants partagés puis résout une fois le DOM prêt.
 * @returns {Promise<void>}
 */
export async function loadSharedComponents() {
  await Promise.all([
    injectComponent('[data-component="sidebar"]', 'sidebar.html'),
    injectComponent('[data-component="topbar"]', 'topbar.html'),
  ]);
  markActiveNavLink();
  document.dispatchEvent(new CustomEvent('siou:components-ready'));
}
