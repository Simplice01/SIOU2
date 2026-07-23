import { apiFetch } from './api.js';

export function listNotifications() {
  return apiFetch('/notifications');
}

export function unreadNotificationCount() {
  return apiFetch('/notifications/unread-count');
}

export function markNotificationRead(id) {
  return apiFetch(`/notifications/${id}/read`, { method: 'POST' });
}

export function markAllNotificationsRead() {
  return apiFetch('/notifications/read-all', { method: 'POST' });
}

export function listAdminNotifications() {
  return apiFetch('/admin/notifications');
}

export function createAdminNotification(payload) {
  return apiFetch('/admin/notifications', { method: 'POST', body: payload });
}

export function updateAdminNotification(id, payload) {
  return apiFetch(`/admin/notifications/${id}`, { method: 'PATCH', body: payload });
}

export function deleteAdminNotification(id) {
  return apiFetch(`/admin/notifications/${id}`, { method: 'DELETE' });
}
