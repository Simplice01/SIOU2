import { messageFromError } from './api.js';
import { listNotifications, markAllNotificationsRead, markNotificationRead } from './notification-service.js';
import { qs, qsa } from './utils.js';

function escapeText(value) {
  const div = document.createElement('div');
  div.textContent = value ?? '';
  return div.innerHTML;
}

function updateDot(trigger, count) {
  const dot = qs('[data-notifications-dot]', trigger);
  if (dot) dot.hidden = Number(count) <= 0;
}

function renderNotifications(list, items, trigger) {
  if (!items.length) {
    list.innerHTML = `
      <div class="notification-item">
        <p class="notification-item__title">Aucune notification</p>
        <p class="notification-item__meta">Vous êtes à jour.</p>
      </div>
    `;
    updateDot(trigger, 0);
    return;
  }

  list.innerHTML = items.slice(0, 5).map((item) => `
    <button class="notification-item ${item.is_read ? '' : 'is-unread'}" data-notification-id="${item.id}" type="button">
      <p class="notification-item__title">${escapeText(item.title)}</p>
      <p class="notification-item__meta">${escapeText(item.message)}</p>
    </button>
  `).join('');
  updateDot(trigger, items.filter((item) => !item.is_read).length);
}

export function initNotifications() {
  const trigger = qs('[data-notifications-trigger]');
  const panel = qs('[data-notifications-panel]');
  const list = panel ? qs('[data-notifications-list]', panel) : null;
  if (!trigger || !panel || !list) return;

  function toggle(forceState) {
    const willOpen = forceState ?? !panel.classList.contains('is-open');
    panel.classList.toggle('is-open', willOpen);
    trigger.setAttribute('aria-expanded', String(willOpen));
  }

  async function refresh() {
    try {
      const items = await listNotifications();
      renderNotifications(list, items || [], trigger);
    } catch (error) {
      list.innerHTML = `
        <div class="notification-item">
          <p class="notification-item__title">Notifications indisponibles</p>
          <p class="notification-item__meta">${escapeText(messageFromError(error, 'Impossible de charger les notifications.'))}</p>
        </div>
      `;
      updateDot(trigger, 0);
    }
  }

  trigger.addEventListener('click', (event) => {
    event.stopPropagation();
    toggle();
  });

  document.addEventListener('click', (event) => {
    if (!panel.contains(event.target) && !trigger.contains(event.target)) toggle(false);
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') toggle(false);
  });

  list.addEventListener('click', async (event) => {
    const item = event.target.closest('[data-notification-id]');
    if (!item) return;
    await markNotificationRead(item.dataset.notificationId);
    item.classList.remove('is-unread');
    updateDot(trigger, qsa('.notification-item.is-unread', panel).length);
  });

  qs('[data-notifications-mark-read]', panel)?.addEventListener('click', async () => {
    await markAllNotificationsRead();
    qsa('.notification-item.is-unread', panel).forEach((item) => item.classList.remove('is-unread'));
    updateDot(trigger, 0);
  });

  refresh();
}
