/**
 * feedbacks-admin.js
 * Contrôleur de la page « Signalements » (feedbacks.html), réservée au rôle
 * admin (RBAC déclaratif sur <body>).
 *
 * - liste réelle via `GET /api/admin/feedbacks` (rendu en tableau) ;
 * - suppression (`DELETE /api/admin/feedbacks/{id}`) avec confirmation.
 *
 * Un signalement = une note (1-5) laissée sur une réponse de l'assistant,
 * avec un commentaire optionnel. Le bouton « Signaler » du chat crée une
 * note de 1 sans commentaire ; d'autres notes restent possibles via l'API.
 */

import { listFeedbacks, deleteFeedback } from './feedback-service.js';
import { messageFromError } from './api.js';
import { initInstantSearch } from './search.js';
import { showToast } from './toast.js';
import { escapeHtml, formatRelativeDate, formatTime } from './utils.js';

/* ------------------------------------------------------------------ */
/*  Présentation                                                       */
/* ------------------------------------------------------------------ */

function ratingBadge(rating) {
  const value = Number(rating) || 0;
  const cls = value <= 2 ? 'badge--danger' : value === 3 ? 'badge--warning' : 'badge--success';
  const stars = '★'.repeat(value) + '☆'.repeat(Math.max(0, 5 - value));
  const badge = document.createElement('span');
  badge.className = `badge ${cls}`;
  badge.title = `${value}/5`;
  badge.textContent = `${stars} ${value}/5`;
  return badge;
}

/* ------------------------------------------------------------------ */
/*  Rendu du tableau                                                   */
/* ------------------------------------------------------------------ */

function createRow(feedback) {
  const row = document.createElement('tr');
  row.dataset.searchItem = '';
  row.dataset.feedbackId = feedback.id;
  row.dataset.searchText = (feedback.comment || '').toLowerCase();
  row.style.borderBottom = '1px solid var(--color-border)';

  const ratingCell = document.createElement('td');
  ratingCell.style.padding = 'var(--sp-4)';
  ratingCell.appendChild(ratingBadge(feedback.rating));

  const commentCell = document.createElement('td');
  commentCell.style.cssText = 'padding: var(--sp-4); max-width: 380px;';
  commentCell.textContent = feedback.comment || '—';
  if (!feedback.comment) commentCell.style.color = 'var(--color-text-tertiary)';

  const convCell = document.createElement('td');
  convCell.style.cssText = 'padding: var(--sp-4); color: var(--color-text-secondary); font-family: var(--font-mono, monospace); font-size: var(--fs-sm);';
  convCell.textContent = feedback.conversation_id ? feedback.conversation_id.slice(0, 8) : '—';
  if (feedback.conversation_id) convCell.title = feedback.conversation_id;

  const dateCell = document.createElement('td');
  dateCell.style.cssText = 'padding: var(--sp-4); color: var(--color-text-secondary); font-size: var(--fs-sm); white-space:nowrap;';
  dateCell.textContent = feedback.created_at
    ? `${formatRelativeDate(feedback.created_at)}, ${formatTime(feedback.created_at)}`
    : '—';

  const actionsCell = document.createElement('td');
  actionsCell.style.cssText = 'padding: var(--sp-4); text-align:right; white-space:nowrap;';
  actionsCell.innerHTML = '<button class="btn btn--ghost btn--sm" data-feedback-delete type="button">Supprimer</button>';

  row.append(ratingCell, commentCell, convCell, dateCell, actionsCell);
  return row;
}

function messageRow(text, color) {
  return `<tr><td colspan="5" style="padding: var(--sp-6); color: ${color};">${escapeHtml(text)}</td></tr>`;
}

function updateCount(count) {
  const desc = document.querySelector('.page__header .page__desc');
  if (!desc) return;
  desc.textContent =
    count === 0
      ? 'Aucun signalement pour le moment.'
      : `${count} signalement${count > 1 ? 's' : ''} laissé${count > 1 ? 's' : ''} sur les réponses de l'assistant.`;
}

async function loadFeedbacks(tbody, emptyState) {
  tbody.innerHTML = messageRow('Chargement…', 'var(--color-text-secondary)');
  try {
    const feedbacks = (await listFeedbacks()) || [];
    tbody.innerHTML = '';
    feedbacks.forEach((f) => tbody.appendChild(createRow(f)));
    updateCount(feedbacks.length);
    if (emptyState) emptyState.hidden = feedbacks.length > 0;
  } catch (error) {
    tbody.innerHTML = messageRow(
      messageFromError(error, 'Impossible de charger les signalements.'),
      'var(--color-danger)',
    );
  }
}

/* ------------------------------------------------------------------ */
/*  Suppression (confirmation en deux temps)                           */
/* ------------------------------------------------------------------ */

function confirmDelete(row, tbody, emptyState) {
  const id = row.dataset.feedbackId;
  const actionsCell = row.lastElementChild;
  const original = actionsCell.innerHTML;

  actionsCell.innerHTML = `
    <span style="color: var(--color-text-secondary); margin-right: var(--sp-2);">Supprimer&nbsp;?</span>
    <button class="btn btn--danger btn--sm" data-feedback-del-confirm type="button">Oui</button>
    <button class="btn btn--ghost btn--sm" data-feedback-del-cancel type="button">Non</button>
  `;

  actionsCell.querySelector('[data-feedback-del-cancel]').addEventListener('click', () => {
    actionsCell.innerHTML = original;
  });

  actionsCell.querySelector('[data-feedback-del-confirm]').addEventListener('click', async (event) => {
    event.currentTarget.disabled = true;
    try {
      await deleteFeedback(id);
      row.remove();
      const remaining = tbody.querySelectorAll('tr[data-feedback-id]').length;
      updateCount(remaining);
      if (remaining === 0 && emptyState) emptyState.hidden = false;
      showToast({ title: 'Signalement supprimé', type: 'success' });
    } catch (error) {
      actionsCell.innerHTML = original;
      showToast({ title: 'Suppression impossible', text: messageFromError(error), type: 'danger' });
    }
  });
}

/* ------------------------------------------------------------------ */
/*  Initialisation                                                     */
/* ------------------------------------------------------------------ */

async function initFeedbacksAdmin() {
  const tbody = document.querySelector('[data-feedback-table] tbody');
  if (!tbody) return;
  const emptyState = document.querySelector('[data-search-empty]');

  await loadFeedbacks(tbody, emptyState);
  initInstantSearch();

  tbody.addEventListener('click', (event) => {
    const row = event.target.closest('tr[data-feedback-id]');
    if (!row) return;
    if (event.target.closest('[data-feedback-delete]')) {
      confirmDelete(row, tbody, emptyState);
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initFeedbacksAdmin);
} else {
  initFeedbacksAdmin();
}
