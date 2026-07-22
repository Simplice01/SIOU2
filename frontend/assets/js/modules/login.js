/**
 * login.js
 * Contrôleur de la page de connexion (login.html).
 *
 * - empêche l'accès si l'utilisateur est déjà connecté (requireGuest) ;
 * - valide le formulaire, gère l'état de chargement du bouton ;
 * - délègue l'authentification à `auth.login` ;
 * - affiche les erreurs de façon intégrée (message inline + toast),
 *   jamais via alert() ;
 * - redirige vers la destination demandée (?next=) ou l'accueil.
 */

import { login } from './auth.js';
import { requireGuest } from './route-guard.js';
import { ApiError } from './api.js';
import { showToast } from './toast.js';
import { qs } from './utils.js';

const HOME_PAGE = '/index.html';

function safeNextTarget() {
  const next = new URLSearchParams(window.location.search).get('next');
  if (next && next.startsWith('/') && !next.startsWith('//')) return next;
  return HOME_PAGE;
}

function setLoading(button, isLoading) {
  button.disabled = isLoading;
  button.classList.toggle('is-loading', isLoading);
  button.setAttribute('aria-busy', isLoading ? 'true' : 'false');
}

function showError(errorEl, message) {
  errorEl.textContent = message;
  errorEl.hidden = !message;
}

function initLogin() {
  // Si déjà authentifié, on ne reste pas sur le formulaire.
  if (!requireGuest()) return;

  const form = qs('[data-login-form]');
  if (!form) return;

  const usernameInput = qs('[data-login-username]', form);
  const passwordInput = qs('[data-login-password]', form);
  const submitButton = qs('[data-login-submit]', form);
  const errorEl = qs('[data-login-error]', form);
  const toggleButton = qs('[data-password-toggle]', form);
  const rememberInput = qs('[data-login-remember]', form);

  // Affichage / masquage du mot de passe.
  if (toggleButton && passwordInput) {
    toggleButton.addEventListener('click', () => {
      const revealed = passwordInput.type === 'text';
      passwordInput.type = revealed ? 'password' : 'text';
      toggleButton.setAttribute('aria-pressed', String(!revealed));
      toggleButton.setAttribute(
        'aria-label',
        revealed ? 'Afficher le mot de passe' : 'Masquer le mot de passe',
      );
      toggleButton.classList.toggle('is-revealed', !revealed);
    });
  }

  // Effacer l'erreur dès que l'utilisateur corrige sa saisie.
  [usernameInput, passwordInput].forEach((input) => {
    input?.addEventListener('input', () => showError(errorEl, ''));
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const username = usernameInput.value.trim();
    const password = passwordInput.value;

    if (!username || !password) {
      showError(errorEl, 'Veuillez renseigner votre identifiant et votre mot de passe.');
      (!username ? usernameInput : passwordInput).focus();
      return;
    }

    showError(errorEl, '');
    setLoading(submitButton, true);

    try {
      const user = await login(username, password, Boolean(rememberInput?.checked));
      showToast({
        title: 'Connexion réussie',
        text: user?.first_name ? `Bienvenue, ${user.first_name}.` : 'Bienvenue sur SIOU.',
        type: 'success',
      });
      window.location.assign(safeNextTarget());
    } catch (error) {
      setLoading(submitButton, false);

      let message = 'Une erreur est survenue. Veuillez réessayer.';
      if (error instanceof ApiError) {
        if (error.status === 401) {
          message = 'Identifiant ou mot de passe incorrect.';
        } else if (error.type === 'network') {
          message = 'Impossible de joindre le serveur. Vérifiez votre connexion Internet.';
        } else if (error.type === 'timeout') {
          message = 'Le serveur met trop de temps à répondre. Veuillez réessayer.';
        } else if (error.message) {
          message = error.message;
        }
      }

      showError(errorEl, message);
      showToast({ title: 'Connexion impossible', text: message, type: 'danger' });
      passwordInput.focus();
      passwordInput.select();
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLogin);
} else {
  initLogin();
}
