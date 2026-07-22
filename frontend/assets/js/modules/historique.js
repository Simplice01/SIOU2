/**
 * historique.js
 * Contrôleur de la page « Historique des conversations » (historique.html).
 * Remplace les lignes de démonstration statiques par les données réelles de
 * `GET /api/conversations`, tout en conservant la compatibilité avec la
 * recherche (search.js) et les filtres (filters.js) via les attributs
 * `data-search-item` / `data-search-text` / `data-filter-category`.
 */

import { listConversations, updateConversation, deleteConversation } from './conversation-service.js';
import { messageFromError } from './api.js';
import { showToast } from './toast.js';
import { formatRelativeDate, formatTime, escapeHtml } from './utils.js';

function messageRow(text, color) {
  return `<tr><td colspan="3" style="padding: var(--sp-6); color: ${color};">${escapeHtml(text)}</td></tr>`;
}

function renderRows(tbody, conversations, emptyState) {
  tbody.innerHTML = '';

  if (!conversations.length) {
    if (emptyState) emptyState.hidden = false;
    return;
  }
  if (emptyState) emptyState.hidden = true;

  conversations.forEach((conversation) => {
    const row = document.createElement('tr');
    row.dataset.searchItem = '';
    row.dataset.filterCategory = 'all';
    row.dataset.searchText = (conversation.title || '').toLowerCase();
    row.dataset.conversationId = conversation.id;
    row.style.borderBottom = '1px solid var(--color-border)';

    const titleCell = document.createElement('td');
    titleCell.style.padding = 'var(--sp-4)';
    const link = document.createElement('a');
    link.href = '/pages/chat.html';
    link.style.fontWeight = '600';
    link.className = 'history-row__title';
    link.textContent = conversation.title || 'Conversation';
    titleCell.appendChild(link);

    const dateCell = document.createElement('td');
    dateCell.style.cssText = 'padding: var(--sp-4); color: var(--color-text-secondary); font-size: var(--fs-sm);';
    dateCell.textContent = conversation.created_at
      ? `${formatRelativeDate(conversation.created_at)}, ${formatTime(conversation.created_at)}`
      : '—';

    const actionsCell = document.createElement('td');
    actionsCell.style.cssText = 'padding: var(--sp-4); text-align:right; white-space:nowrap;';
    actionsCell.innerHTML = `
      <button class="btn btn--ghost btn--sm" data-hist-rename type="button">Renommer</button>
      <button class="btn btn--ghost btn--sm" data-hist-delete type="button">Supprimer</button>
    `;

    row.append(titleCell, dateCell, actionsCell);
    tbody.appendChild(row);
  });
}

/* ------------------------------------------------------------------ */
/*  Actions par ligne : renommer / supprimer                          */
/* ------------------------------------------------------------------ */

// Renommage en place du lien-titre de la ligne.
function startRename(row) {
  const cell = row.querySelector('td');
  const link = cell?.querySelector('.history-row__title');
  if (!link) return;
  const id = row.dataset.conversationId;
  const current = link.textContent;

  const input = document.createElement('input');
  input.className = 'input';
  input.value = current;
  input.setAttribute('aria-label', 'Nouveau nom de la conversation');
  input.style.maxWidth = '340px';
  link.replaceWith(input);
  input.focus();
  input.select();

  let done = false;
  const finish = async (save) => {
    if (done) return;
    done = true;
    const newTitle = input.value.trim();
    const restored = document.createElement('a');
    restored.href = '/pages/chat.html';
    restored.style.fontWeight = '600';
    restored.className = 'history-row__title';

    if (save && newTitle && newTitle !== current) {
      try {
        const updated = await updateConversation(id, { title: newTitle });
        restored.textContent = updated.title || newTitle;
        input.replaceWith(restored);
        row.dataset.searchText = restored.textContent.toLowerCase();
        showToast({ title: 'Conversation renommée', type: 'success' });
      } catch (error) {
        restored.textContent = current;
        input.replaceWith(restored);
        showToast({ title: 'Renommage impossible', text: messageFromError(error), type: 'danger' });
      }
    } else {
      restored.textContent = current;
      input.replaceWith(restored);
    }
  };

  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      finish(true);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      finish(false);
    }
  });
  input.addEventListener('blur', () => finish(true));
}

// Suppression avec confirmation en deux temps dans la cellule d'actions.
function confirmDelete(row, tbody, emptyState) {
  const id = row.dataset.conversationId;
  const actionsCell = row.lastElementChild;
  const original = actionsCell.innerHTML;

  actionsCell.innerHTML = `
    <span style="color: var(--color-text-secondary); margin-right: var(--sp-2);">Supprimer&nbsp;?</span>
    <button class="btn btn--danger btn--sm" data-hist-del-confirm type="button">Oui</button>
    <button class="btn btn--ghost btn--sm" data-hist-del-cancel type="button">Non</button>
  `;

  actionsCell.querySelector('[data-hist-del-cancel]').addEventListener('click', () => {
    actionsCell.innerHTML = original;
  });

  actionsCell.querySelector('[data-hist-del-confirm]').addEventListener('click', async (event) => {
    event.currentTarget.disabled = true;
    try {
      await deleteConversation(id);
      row.remove();
      const remaining = tbody.querySelectorAll('tr[data-conversation-id]').length;
      updateCount(remaining);
      if (remaining === 0 && emptyState) emptyState.hidden = false;
      showToast({ title: 'Conversation supprimée', type: 'success' });
    } catch (error) {
      actionsCell.innerHTML = original;
      showToast({ title: 'Suppression impossible', text: messageFromError(error), type: 'danger' });
    }
  });
}

function updateCount(count) {
  const desc = document.querySelector('.page__header .page__desc');
  if (!desc) return;
  desc.textContent =
    count === 0
      ? 'Aucune conversation enregistrée pour le moment.'
      : `${count} conversation${count > 1 ? 's' : ''} enregistrée${count > 1 ? 's' : ''}.`;
}

async function initHistorique() {
  const tbody = document.querySelector('[data-history-table] tbody');
  if (!tbody) return;
  const emptyState = document.querySelector('[data-search-empty]');

  // Délégation des actions par ligne (fonctionne avec les lignes rendues à la volée).
  tbody.addEventListener('click', (event) => {
    const row = event.target.closest('tr[data-conversation-id]');
    if (!row) return;
    if (event.target.closest('[data-hist-rename]')) startRename(row);
    else if (event.target.closest('[data-hist-delete]')) confirmDelete(row, tbody, emptyState);
  });

  tbody.innerHTML = messageRow('Chargement…', 'var(--color-text-secondary)');

  try {
    const conversations = (await listConversations()) || [];
    renderRows(tbody, conversations, emptyState);
    updateCount(conversations.length);
  } catch (error) {
    tbody.innerHTML = messageRow(
      messageFromError(error, "L'historique est momentanément indisponible."),
      'var(--color-danger)',
    );
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initHistorique);
} else {
  initHistorique();
}
