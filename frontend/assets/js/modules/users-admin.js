/**
 * users-admin.js
 * Contrôleur de la page « Utilisateurs » (utilisateurs.html), réservée au
 * rôle admin (RBAC déclaratif sur <body>).
 *
 * - liste réelle via `GET /api/admin/users` (rendu en tableau) ;
 * - modale d'ajout (`POST`) / d'édition (`PATCH /api/admin/users/{id}`) ;
 * - suppression (`DELETE`) avec confirmation en deux temps.
 *
 * Garde-fou : l'administrateur connecté ne peut ni se supprimer ni se
 * rétrograder lui-même depuis cette page (évite de se verrouiller dehors).
 */

import { listUsers, getAdminUser, createUser, updateUser, deleteUser } from './user-service.js';
import { messageFromError } from './api.js';
import { getUser, normalizeRole } from './auth.js';
import { initModals, openModal, closeModal } from './modal.js';
import { initInstantSearch } from './search.js';
import { showToast } from './toast.js';
import { escapeHtml } from './utils.js';

const ROLE_LABELS = {
  admin: 'Administrateur',
  responsable_ministere: 'Responsable ministère',
  point_focal: 'Point focal',
  user: 'Usager',
  usager_anonyme: 'Usager',
  secretary: 'Secrétaire',
  secretaire: 'Secrétaire',
  validator: 'Validateur / point focal',
  ministry_manager: 'Responsable ministère',
  administrateur: 'Administrateur',
};

function roleLabel(role) {
  return ROLE_LABELS[role] || ROLE_LABELS[normalizeRole(role)] || role || 'Utilisateur';
}

let editingId = null;

/* ------------------------------------------------------------------ */
/*  Rendu du tableau                                                   */
/* ------------------------------------------------------------------ */

function fullName(user) {
  return [user.first_name, user.last_name].filter(Boolean).join(' ').trim();
}

function createRow(user) {
  const isSelf = getUser()?.id === user.id;

  const row = document.createElement('tr');
  row.dataset.searchItem = '';
  row.dataset.userId = user.id;
  row.dataset.searchText = `${fullName(user)} ${user.username} ${roleLabel(user.role)}`.toLowerCase();
  row.style.borderBottom = '1px solid var(--color-border)';

  const nameCell = document.createElement('td');
  nameCell.style.padding = 'var(--sp-4)';
  nameCell.style.fontWeight = '600';
  nameCell.textContent = fullName(user) || '—';
  if (isSelf) {
    const you = document.createElement('span');
    you.className = 'badge badge--info';
    you.style.marginLeft = 'var(--sp-2)';
    you.textContent = 'Vous';
    nameCell.appendChild(you);
  }

  const usernameCell = document.createElement('td');
  usernameCell.style.cssText = 'padding: var(--sp-4); color: var(--color-text-secondary); font-family: var(--font-mono, monospace); font-size: var(--fs-sm);';
  usernameCell.textContent = user.username;

  const roleCell = document.createElement('td');
  roleCell.style.padding = 'var(--sp-4)';
  roleCell.textContent = roleLabel(user.role);

  const statusCell = document.createElement('td');
  statusCell.style.padding = 'var(--sp-4)';
  const active = user.is_active !== false;
  const badge = document.createElement('span');
  badge.className = `badge ${active ? 'badge--success' : 'badge--danger'}`;
  badge.textContent = active ? 'Actif' : 'Désactivé';
  statusCell.appendChild(badge);

  const actionsCell = document.createElement('td');
  actionsCell.style.cssText = 'padding: var(--sp-4); text-align:right; white-space:nowrap;';
  // Pas de suppression de son propre compte (garde-fou anti-verrouillage).
  actionsCell.innerHTML = `
    <button class="btn btn--ghost btn--sm" data-user-view type="button">Voir</button>
    <button class="btn btn--ghost btn--sm" data-user-edit type="button">Modifier</button>
    ${isSelf ? '' : '<button class="btn btn--ghost btn--sm" data-user-delete type="button">Supprimer</button>'}
  `;

  row.append(nameCell, usernameCell, roleCell, statusCell, actionsCell);
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
      ? 'Aucun compte enregistré pour le moment.'
      : `${count} compte${count > 1 ? 's' : ''} ayant accès à SIOU.`;
}

// Cache les utilisateurs pour retrouver leurs données à l'édition.
let usersById = new Map();

async function loadUsers(tbody, emptyState) {
  tbody.innerHTML = messageRow('Chargement…', 'var(--color-text-secondary)');
  try {
    const users = (await listUsers()) || [];
    usersById = new Map(users.map((u) => [u.id, u]));
    tbody.innerHTML = '';
    users.forEach((u) => tbody.appendChild(createRow(u)));
    updateCount(users.length);
    if (emptyState) emptyState.hidden = users.length > 0;
  } catch (error) {
    tbody.innerHTML = messageRow(
      messageFromError(error, "Impossible de charger les utilisateurs."),
      'var(--color-danger)',
    );
  }
}

/* ------------------------------------------------------------------ */
/*  Modale ajout / édition                                             */
/* ------------------------------------------------------------------ */

function modalRefs() {
  const overlay = document.getElementById('user-modal');
  return {
    overlay,
    form: overlay?.querySelector('[data-user-form]'),
    title: document.getElementById('user-modal-title'),
    submit: overlay?.querySelector('[data-user-submit]'),
    username: document.getElementById('user-username'),
    usernameHint: overlay?.querySelector('[data-username-hint]'),
    passwordField: overlay?.querySelector('[data-password-field]'),
    password: document.getElementById('user-password'),
    firstName: document.getElementById('user-first-name'),
    lastName: document.getElementById('user-last-name'),
    role: document.getElementById('user-role'),
    active: document.getElementById('user-active'),
  };
}

function openAddModal() {
  editingId = null;
  const r = modalRefs();
  if (!r.overlay) return;
  if (r.title) r.title.textContent = 'Ajouter un utilisateur';
  if (r.submit) r.submit.textContent = 'Créer le compte';
  r.form?.reset();
  if (r.username) r.username.disabled = false;
  if (r.usernameHint) r.usernameHint.hidden = false;
  if (r.passwordField) r.passwordField.hidden = false;
  if (r.active) r.active.checked = true;
  openModal(r.overlay);
  r.firstName?.focus();
}

function openEditModal(user) {
  editingId = user.id;
  const r = modalRefs();
  if (!r.overlay) return;
  if (r.title) r.title.textContent = "Modifier l'utilisateur";
  if (r.submit) r.submit.textContent = 'Enregistrer';
  if (r.firstName) r.firstName.value = user.first_name || '';
  if (r.lastName) r.lastName.value = user.last_name || '';
  if (r.username) {
    r.username.value = user.username || '';
    r.username.disabled = true; // l'identifiant n'est pas modifiable
  }
  if (r.usernameHint) r.usernameHint.hidden = true;
  // Le mot de passe ne se change pas ici (pas d'endpoint dédié).
  if (r.passwordField) r.passwordField.hidden = true;
  if (r.password) r.password.value = '';
  if (r.role) r.role.value = normalizeRole(user.role) || 'user';
  if (r.active) r.active.checked = user.is_active !== false;

  // Un admin ne peut pas se rétrograder lui-même (garde-fou).
  const isSelf = getUser()?.id === user.id;
  if (r.role) r.role.disabled = isSelf;
  if (r.active) r.active.disabled = isSelf;

  openModal(r.overlay);
  r.firstName?.focus();
}

function detailRefs() {
  const overlay = document.getElementById('user-detail-modal');
  return {
    overlay,
    body: overlay?.querySelector('[data-user-detail]'),
  };
}

function detailItem(label, value, options = {}) {
  const display = value === null || value === undefined || value === '' ? '—' : value;
  return `
    <div class="detail-item">
      <span class="detail-label">${escapeHtml(label)}</span>
      <span class="detail-value ${options.mono ? 'detail-value--mono' : ''}">${escapeHtml(String(display))}</span>
    </div>
  `;
}

async function openUserDetail(id) {
  const r = detailRefs();
  if (!r.overlay || !r.body) return;
  r.body.innerHTML = '<p style="color: var(--color-text-secondary);">Chargement du détail...</p>';
  openModal(r.overlay);

  try {
    const user = await getAdminUser(id);
    const active = user.is_active !== false ? 'Actif' : 'Désactivé';
    r.body.innerHTML = `
      <div class="detail-summary">
        <div class="avatar avatar--lg">${escapeHtml(((user.first_name || user.username || 'U')[0] || 'U').toUpperCase())}</div>
        <div>
          <h3>${escapeHtml(fullName(user) || user.username || 'Utilisateur')}</h3>
          <p>${escapeHtml(roleLabel(user.role))}</p>
        </div>
      </div>
      <div class="detail-grid">
        ${detailItem('Identifiant', user.username, { mono: true })}
        ${detailItem('Prénom', user.first_name)}
        ${detailItem('Nom', user.last_name)}
        ${detailItem('Rôle', roleLabel(user.role))}
        ${detailItem('Statut', active)}
        ${detailItem('Créé le', user.created_at ? new Date(user.created_at).toLocaleString('fr-FR') : null)}
        ${detailItem('ID technique', user.id, { mono: true })}
      </div>
    `;
  } catch (error) {
    r.body.innerHTML = `<p style="color: var(--color-danger);">${escapeHtml(messageFromError(error, "Impossible de charger le détail de l'utilisateur."))}</p>`;
  }
}

async function handleSubmit(tbody, emptyState) {
  const r = modalRefs();

  const first = r.firstName?.value.trim() || null;
  const last = r.lastName?.value.trim() || null;
  const role = r.role?.value || 'user';
  const isActive = Boolean(r.active?.checked);

  if (r.submit) r.submit.disabled = true;
  try {
    if (editingId) {
      await updateUser(editingId, {
        first_name: first,
        last_name: last,
        role,
        is_active: isActive,
      });
      showToast({ title: 'Utilisateur mis à jour', type: 'success' });
    } else {
      const username = r.username?.value.trim();
      const password = r.password?.value || '';
      if (!username) {
        showToast({ title: 'Identifiant requis', text: 'Veuillez renseigner un identifiant.', type: 'warning' });
        r.username?.focus();
        return;
      }
      if (password.length < 8) {
        showToast({ title: 'Mot de passe trop court', text: '8 caractères minimum.', type: 'warning' });
        r.password?.focus();
        return;
      }
      await createUser({
        username,
        password,
        first_name: first,
        last_name: last,
        role,
        is_active: isActive,
      });
      showToast({ title: 'Compte créé', type: 'success' });
    }
    if (r.overlay) closeModal(r.overlay);
    await loadUsers(tbody, emptyState);
  } catch (error) {
    showToast({ title: 'Enregistrement impossible', text: messageFromError(error), type: 'danger' });
  } finally {
    if (r.submit) r.submit.disabled = false;
  }
}

/* ------------------------------------------------------------------ */
/*  Suppression (confirmation en deux temps)                           */
/* ------------------------------------------------------------------ */

function confirmDelete(row, tbody, emptyState) {
  const id = row.dataset.userId;
  const actionsCell = row.lastElementChild;
  const original = actionsCell.innerHTML;

  actionsCell.innerHTML = `
    <span style="color: var(--color-text-secondary); margin-right: var(--sp-2);">Supprimer&nbsp;?</span>
    <button class="btn btn--danger btn--sm" data-user-del-confirm type="button">Oui</button>
    <button class="btn btn--ghost btn--sm" data-user-del-cancel type="button">Non</button>
  `;

  actionsCell.querySelector('[data-user-del-cancel]').addEventListener('click', () => {
    actionsCell.innerHTML = original;
  });

  actionsCell.querySelector('[data-user-del-confirm]').addEventListener('click', async (event) => {
    event.currentTarget.disabled = true;
    try {
      await deleteUser(id);
      row.remove();
      usersById.delete(id);
      const remaining = tbody.querySelectorAll('tr[data-user-id]').length;
      updateCount(remaining);
      if (remaining === 0 && emptyState) emptyState.hidden = false;
      showToast({ title: 'Utilisateur supprimé', type: 'success' });
    } catch (error) {
      actionsCell.innerHTML = original;
      showToast({ title: 'Suppression impossible', text: messageFromError(error), type: 'danger' });
    }
  });
}

/* ------------------------------------------------------------------ */
/*  Initialisation                                                     */
/* ------------------------------------------------------------------ */

async function initUsersAdmin() {
  const tbody = document.querySelector('[data-user-table] tbody');
  if (!tbody) return;
  const emptyState = document.querySelector('[data-search-empty]');

  await loadUsers(tbody, emptyState);
  initInstantSearch();
  initModals();

  // Ouverture de la modale d'ajout.
  document.querySelectorAll('[data-modal-open="user-modal"]').forEach((btn) => {
    btn.addEventListener('click', openAddModal);
  });

  // Soumission de la modale (ajout / édition).
  const form = document.querySelector('[data-user-form]');
  if (form) {
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      handleSubmit(tbody, emptyState);
    });
  }

  // Actions par ligne, en délégation.
  tbody.addEventListener('click', (event) => {
    const row = event.target.closest('tr[data-user-id]');
    if (!row) return;
    if (event.target.closest('[data-user-view]')) {
      openUserDetail(row.dataset.userId);
    } else if (event.target.closest('[data-user-edit]')) {
      const user = usersById.get(row.dataset.userId);
      if (user) openEditModal(user);
    } else if (event.target.closest('[data-user-delete]')) {
      confirmDelete(row, tbody, emptyState);
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initUsersAdmin);
} else {
  initUsersAdmin();
}
