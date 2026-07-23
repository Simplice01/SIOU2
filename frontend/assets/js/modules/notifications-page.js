import { messageFromError } from './api.js';
import { hasRole } from './auth.js';
import {
  createAdminNotification,
  deleteAdminNotification,
  listAdminNotifications,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from './notification-service.js';
import { initInstantSearch } from './search.js';
import { showToast } from './toast.js';
import { escapeHtml, formatRelativeDate, formatTime } from './utils.js';

const ROLE_LABELS = {
  all: 'Tous',
  user: 'Usagers',
  secretary: 'Secrétaires',
  validator: 'Validateurs',
  ministry_manager: 'Responsables ministère',
  admin: 'Administrateurs',
};

function badgeClass(type) {
  return {
    success: 'badge--success',
    warning: 'badge--warning',
    danger: 'badge--danger',
    system: 'badge--neutral',
  }[type] || 'badge--info';
}

function notificationCard(item, isAdmin) {
  const date = item.created_at ? `${formatRelativeDate(item.created_at)}, ${formatTime(item.created_at)}` : 'Date inconnue';
  const target = ROLE_LABELS[item.target_role] || item.target_role;
  return `
    <article class="notification-card ${item.is_read ? '' : 'is-unread'}" data-search-item data-notification-id="${item.id}" data-search-text="${escapeHtml(`${item.title} ${item.message} ${target}`.toLowerCase())}">
      <div class="notification-card__main">
        <div class="notification-card__heading">
          <span class="badge ${badgeClass(item.notification_type)}">${escapeHtml(item.notification_type)}</span>
          <span class="badge badge--neutral">${escapeHtml(target)}</span>
          ${item.is_system ? '<span class="badge badge--warning">Système</span>' : ''}
        </div>
        <h2 class="notification-card__title">${escapeHtml(item.title)}</h2>
        <p class="notification-card__message">${escapeHtml(item.message)}</p>
        <p class="notification-card__meta">${date} · Priorité ${escapeHtml(item.priority)}</p>
      </div>
      <div class="notification-card__actions">
        ${item.action_url ? `<a class="btn btn--ghost btn--sm" href="${escapeHtml(item.action_url)}">Ouvrir</a>` : ''}
        ${item.is_read ? '' : '<button class="btn btn--secondary btn--sm" data-notification-read type="button">Marquer lu</button>'}
        ${isAdmin ? '<button class="btn btn--ghost btn--sm" data-notification-delete type="button">Supprimer</button>' : ''}
      </div>
    </article>
  `;
}

function setAdminVisibility() {
  const isAdmin = hasRole('admin');
  document.querySelectorAll('[data-admin-only]').forEach((el) => {
    el.hidden = !isAdmin || el.hasAttribute('data-notification-form-wrap');
  });
}

async function loadPage() {
  const list = document.querySelector('[data-notification-list]');
  if (!list) return;
  const isAdmin = hasRole('admin');
  list.innerHTML = '<p style="padding: var(--sp-5); color: var(--color-text-secondary);">Chargement...</p>';
  try {
    const notifications = isAdmin ? await listAdminNotifications() : await listNotifications();
    list.innerHTML = notifications.length
      ? notifications.map((item) => notificationCard(item, isAdmin)).join('')
      : '<p style="padding: var(--sp-5); color: var(--color-text-secondary);">Aucune notification pour le moment.</p>';
  } catch (error) {
    list.innerHTML = `<p style="padding: var(--sp-5); color: var(--color-danger);">${escapeHtml(messageFromError(error, 'Impossible de charger les notifications.'))}</p>`;
  }
}

function initComposer() {
  const openBtn = document.querySelector('[data-notification-compose]');
  const wrap = document.querySelector('[data-notification-form-wrap]');
  const cancelBtn = document.querySelector('[data-notification-cancel]');
  const form = document.querySelector('[data-notification-form]');
  if (!openBtn || !wrap || !form) return;

  openBtn.addEventListener('click', () => {
    wrap.hidden = false;
    form.querySelector('[name="title"]')?.focus();
  });

  cancelBtn?.addEventListener('click', () => {
    form.reset();
    wrap.hidden = true;
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    const data = Object.fromEntries(new FormData(form).entries());
    try {
      await createAdminNotification(data);
      showToast({ title: 'Notification envoyée', text: 'Les destinataires ciblés la verront dans leur espace.', type: 'success' });
      form.reset();
      wrap.hidden = true;
      await loadPage();
    } catch (error) {
      showToast({ title: 'Envoi impossible', text: messageFromError(error), type: 'danger' });
    } finally {
      submit.disabled = false;
    }
  });
}

function initActions() {
  document.addEventListener('click', async (event) => {
    const card = event.target.closest('[data-notification-id]');
    if (!card) return;
    const id = card.dataset.notificationId;

    if (event.target.closest('[data-notification-read]')) {
      await markNotificationRead(id);
      card.classList.remove('is-unread');
      event.target.closest('[data-notification-read]').remove();
    }

    if (event.target.closest('[data-notification-delete]')) {
      await deleteAdminNotification(id);
      card.remove();
      showToast({ title: 'Notification supprimée', type: 'success' });
    }
  });

  document.querySelector('[data-notifications-read-all]')?.addEventListener('click', async () => {
    await markAllNotificationsRead();
    document.querySelectorAll('.notification-card.is-unread').forEach((card) => card.classList.remove('is-unread'));
    document.querySelectorAll('[data-notification-read]').forEach((button) => button.remove());
  });
}

setAdminVisibility();
initComposer();
initActions();
initInstantSearch();
loadPage();
