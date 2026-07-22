/**
 * profile.js
 * Contrôleur de la page « Mon profil » (profil.html).
 *
 * - charge le profil réel via `GET /api/auth/me` et remplit l'en-tête + le
 *   formulaire (avatar, nom, rôle, identifiant) ;
 * - enregistre les modifications d'identité (prénom / nom) via
 *   `PATCH /api/auth/me` (self-service), puis rafraîchit le cache local.
 *
 * Limites backend assumées : le modèle `User` n'expose que
 * username / first_name / last_name / role / is_active. Les champs e-mail,
 * téléphone, service, photo et mot de passe n'existent pas côté serveur et
 * ne figurent donc pas sur la page. Le rôle et l'identifiant sont en lecture
 * seule (modifiables uniquement par un administrateur, ou pas du tout).
 */

import { fetchCurrentUser, updateCurrentUser, getUser } from './auth.js';
import { messageFromError } from './api.js';
import { showToast } from './toast.js';

/** Libellés lisibles pour les rôles techniques du backend. */
const ROLE_LABELS = {
  admin: 'Administrateur',
  responsable_ministere: 'Responsable ministère',
  point_focal: 'Point focal',
  user: 'Utilisateur',
};

function roleLabel(role) {
  if (!role) return 'Utilisateur';
  return ROLE_LABELS[role] || role;
}

function initials(user) {
  const full = [user?.first_name, user?.last_name].filter(Boolean).join(' ').trim();
  if (full) {
    return full
      .split(/\s+/)
      .map((part) => part[0])
      .slice(0, 2)
      .join('')
      .toUpperCase();
  }
  return (user?.username || '?').slice(0, 2).toUpperCase();
}

/* ------------------------------------------------------------------ */
/*  Rendu                                                              */
/* ------------------------------------------------------------------ */

function renderProfile(user) {
  const fullName = [user.first_name, user.last_name].filter(Boolean).join(' ').trim();

  const avatar = document.querySelector('[data-profile-avatar]');
  if (avatar) avatar.textContent = initials(user);

  const nameEl = document.querySelector('[data-profile-fullname]');
  if (nameEl) nameEl.textContent = fullName || user.username || 'Utilisateur';

  const roleEl = document.querySelector('[data-profile-role]');
  if (roleEl) roleEl.textContent = roleLabel(user.role);

  const statusEl = document.querySelector('[data-profile-status]');
  if (statusEl) {
    const active = user.is_active !== false;
    statusEl.textContent = active ? 'Compte actif' : 'Compte désactivé';
    statusEl.classList.toggle('badge--success', active);
    statusEl.classList.toggle('badge--danger', !active);
    statusEl.hidden = false;
  }

  const firstInput = document.getElementById('profile-first-name');
  if (firstInput) firstInput.value = user.first_name || '';

  const lastInput = document.getElementById('profile-last-name');
  if (lastInput) lastInput.value = user.last_name || '';

  const usernameInput = document.getElementById('profile-username');
  if (usernameInput) usernameInput.value = user.username || '';

  const roleInput = document.getElementById('profile-role');
  if (roleInput) roleInput.value = roleLabel(user.role);
}

/* ------------------------------------------------------------------ */
/*  Chargement                                                         */
/* ------------------------------------------------------------------ */

async function loadProfile() {
  // Affichage immédiat depuis le cache pour éviter un écran vide, puis
  // rafraîchissement depuis le serveur (source de vérité).
  const cached = getUser();
  if (cached) renderProfile(cached);

  try {
    const user = await fetchCurrentUser();
    renderProfile(user);
  } catch (error) {
    showToast({
      title: 'Chargement impossible',
      text: messageFromError(error, 'Impossible de charger votre profil.'),
      type: 'danger',
    });
  }
}

/* ------------------------------------------------------------------ */
/*  Enregistrement                                                     */
/* ------------------------------------------------------------------ */

async function handleSubmit(form) {
  const submit = form.querySelector('[data-profile-submit]');
  const firstName = form.elements.first_name?.value.trim() ?? '';
  const lastName = form.elements.last_name?.value.trim() ?? '';

  if (submit) submit.disabled = true;
  try {
    const user = await updateCurrentUser({ first_name: firstName, last_name: lastName });
    renderProfile(user);
    // Répercute le nouveau nom/avatar sur la topbar déjà affichée.
    syncTopbar(user);
    showToast({ title: 'Profil mis à jour', type: 'success' });
  } catch (error) {
    showToast({ title: 'Enregistrement impossible', text: messageFromError(error), type: 'danger' });
  } finally {
    if (submit) submit.disabled = false;
  }
}

/** Met à jour l'avatar de la topbar sans recharger la page. */
function syncTopbar(user) {
  const avatar = document.querySelector('[data-user-avatar]');
  if (avatar) avatar.textContent = initials(user);
}

/* ------------------------------------------------------------------ */
/*  Initialisation                                                     */
/* ------------------------------------------------------------------ */

async function initProfile() {
  const form = document.querySelector('[data-profile-form]');
  if (!form) return;

  await loadProfile();

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    handleSubmit(form);
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initProfile);
} else {
  initProfile();
}
