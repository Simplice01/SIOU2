/**
 * dashboard.js
 * Contrôleur du tableau de bord (dashboard.html). Remplace les chiffres codés
 * en dur par les données réelles de `GET /api/stats` (via stats-service.js) et
 * personnalise l'accueil avec l'utilisateur connecté.
 *
 * La carte « Répartition des documents » est calculée sur les statuts réels
 * (Actifs / En traitement / Refusés) — l'ancienne carte « Démarches les plus
 * consultées » reposait sur des catégories de conversations qui n'existent pas
 * dans le schéma.
 */

import { getStatistics } from './stats-service.js';
import { getUser } from './auth.js';
import { messageFromError } from './api.js';
import { showToast } from './toast.js';
import { escapeHtml } from './utils.js';

const ARROW_UP = 'M18 15 12 9l-6 6';
const ARROW_DOWN = 'M6 9l6 6 6-6';

function arrowSvg(path) {
  return `<svg aria-hidden="true" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3"><path d="${path}"/></svg>`;
}

function fr(n) {
  return Number(n || 0).toLocaleString('fr-FR');
}

/* ------------------------------------------------------------------ */
/*  Accueil personnalisé                                               */
/* ------------------------------------------------------------------ */

function personalizeGreeting() {
  const el = document.querySelector('[data-greeting]');
  if (!el) return;
  const user = getUser();
  const name = user?.first_name || user?.username || '';
  el.textContent = name ? `Bonjour, ${name}` : 'Bonjour';
}

/* ------------------------------------------------------------------ */
/*  Rendu des statistiques                                             */
/* ------------------------------------------------------------------ */

function renderConversations(cv = {}) {
  const value = document.querySelector('[data-stat="conversations-value"]');
  if (value) value.textContent = fr(cv.current_month);

  const delta = document.querySelector('[data-stat="conversations-delta"]');
  if (delta) {
    const pct = Number(cv.change_percent || 0);
    const up = pct >= 0;
    delta.className = `stat-card__delta stat-card__delta--${up ? 'up' : 'down'}`;
    delta.innerHTML = `${arrowSvg(up ? ARROW_UP : ARROW_DOWN)} ${up ? '+' : ''}${pct.toFixed(1).replace('.', ',')} % vs mois dernier`;
  }
}

function renderDocuments(doc = {}) {
  const value = document.querySelector('[data-stat="documents-value"]');
  if (value) value.textContent = fr(doc.total);

  const delta = document.querySelector('[data-stat="documents-delta"]');
  if (delta) {
    const recent = Number(doc.recent || 0);
    delta.className = 'stat-card__delta stat-card__delta--up';
    delta.innerHTML = recent > 0
      ? `${arrowSvg(ARROW_UP)} +${recent} nouveau${recent > 1 ? 'x' : ''} cette semaine`
      : 'Aucun nouveau cette semaine';
  }

  renderStatusList(doc.by_status || []);
}

function renderStatusList(items) {
  const list = document.querySelector('[data-doc-status-list]');
  if (!list) return;

  if (!items.length) {
    list.innerHTML = '<li class="progress-list__item"><span style="color: var(--color-text-tertiary);">Aucun document indexé pour le moment.</span></li>';
    return;
  }

  list.innerHTML = items
    .map((item, index) => {
      const pct = Number(item.percentage || 0);
      const colorClass = `progress-bar__fill--${(index % 4) + 1}`;
      return `
        <li class="progress-list__item">
          <div class="progress-list__row">
            <span>${escapeHtml(item.label)} <span style="color: var(--color-text-tertiary);">(${fr(item.count)})</span></span>
            <span class="progress-list__percent">${pct} %</span>
          </div>
          <div class="progress-bar" aria-hidden="true">
            <div class="progress-bar__fill ${colorClass}" style="--fill: ${pct}%;"></div>
          </div>
        </li>`;
    })
    .join('');
}

/* ------------------------------------------------------------------ */
/*  Initialisation                                                     */
/* ------------------------------------------------------------------ */

async function initDashboard() {
  if (document.body.dataset.page !== 'dashboard') return;

  personalizeGreeting();

  try {
    const stats = await getStatistics();
    renderConversations(stats.conversations);
    renderDocuments(stats.documents);
  } catch (error) {
    // On garde l'affichage en place et on signale l'échec sans casser la page.
    showToast({
      title: 'Statistiques indisponibles',
      text: messageFromError(error, 'Impossible de charger les statistiques.'),
      type: 'warning',
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initDashboard);
} else {
  initDashboard();
}
