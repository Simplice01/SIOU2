/**
 * settings.js
 * Préférences utilisateur locales (couche partagée) + contrôleur de la page
 * « Paramètres » (parametres.html).
 *
 * Les préférences sont purement côté client (aucun endpoint dédié côté
 * backend) : elles sont persistées dans le Web Storage via `storage.js`.
 *   - `getSettings()` est consommé ailleurs (ex. chat.js) pour adapter l'UI ;
 *   - `initSettingsPage()` câble les contrôles de la page Paramètres.
 *
 * Le thème sombre est géré à part par `theme.js` (déjà persistant) et n'est
 * donc pas dupliqué ici.
 */

import { storage, KEYS } from './storage.js';
import { showToast } from './toast.js';
import { initModals, closeModal } from './modal.js';
import { listConversations, deleteConversation } from './conversation-service.js';
import { messageFromError } from './api.js';

const DEFAULTS = {
  language: 'Français',
  showConfidence: true,
  citeSources: true,
};

/** @returns {{language: string, showConfidence: boolean, citeSources: boolean}} */
export function getSettings() {
  const stored = storage.get(KEYS.SETTINGS) || {};
  return { ...DEFAULTS, ...stored };
}

/** Persiste une préférence unique en fusionnant avec l'existant. */
function saveSetting(key, value) {
  storage.set(KEYS.SETTINGS, { ...getSettings(), [key]: value });
}

/* ------------------------------------------------------------------ */
/*  Contrôleur de la page Paramètres                                   */
/* ------------------------------------------------------------------ */

// Restaure l'état des contrôles [data-setting] et enregistre à chaque change.
function bindControls() {
  const settings = getSettings();
  document.querySelectorAll('[data-setting]').forEach((el) => {
    const key = el.dataset.setting;
    const isCheckbox = el.type === 'checkbox';

    if (isCheckbox) el.checked = Boolean(settings[key]);
    else el.value = settings[key];

    el.addEventListener('change', () => {
      saveSetting(key, isCheckbox ? el.checked : el.value);
      showToast({ title: 'Préférence enregistrée', type: 'success' });
    });
  });
}

// Zone sensible : supprime réellement toutes les conversations de l'utilisateur.
async function clearHistory(button) {
  button.disabled = true;
  try {
    const conversations = (await listConversations()) || [];
    await Promise.all(conversations.map((c) => deleteConversation(c.id)));
    const n = conversations.length;
    showToast({
      title: 'Historique effacé',
      text: n
        ? `${n} conversation${n > 1 ? 's' : ''} supprimée${n > 1 ? 's' : ''}.`
        : 'Aucune conversation à supprimer.',
      type: 'success',
    });
  } catch (error) {
    showToast({ title: 'Suppression impossible', text: messageFromError(error), type: 'danger' });
  } finally {
    button.disabled = false;
    const overlay = document.getElementById('delete-history-modal');
    if (overlay) closeModal(overlay);
  }
}

export function initSettingsPage() {
  if (document.body.dataset.page !== 'parametres') return;

  bindControls();
  initModals(); // câble l'ouverture/fermeture du modal « Effacer l'historique »

  const clearBtn = document.querySelector('[data-clear-history]');
  if (clearBtn) clearBtn.addEventListener('click', () => clearHistory(clearBtn));
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initSettingsPage);
} else {
  initSettingsPage();
}
