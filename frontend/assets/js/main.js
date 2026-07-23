import { requireAuth, enforcePageRole, takeFlash } from './modules/route-guard.js';
import { logout, getUser, hasRole, normalizeRole } from './modules/auth.js';
import { showToast } from './modules/toast.js';
import { initSidebar } from './modules/sidebar.js';
import { initTheme } from './modules/theme.js';
import { initNotifications } from './modules/notifications.js';

/**
 * Câble la déconnexion et personnalise la topbar une fois les composants
 * partagés injectés (sidebar/topbar arrivent après le chargement de main.js).
 */
function initSessionUI() {
  // Déconnexion : nettoie la session puis renvoie vers la page de connexion.
  document.querySelectorAll('[data-logout]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      await logout();
      window.location.assign('/login.html');
    });
  });

  // Masque les liens de navigation réservés à des rôles que l'utilisateur
  // n'a pas (ex. Base documentaire). `:not(body)` évite le gate de page.
  document.querySelectorAll('[data-require-role]:not(body)').forEach((el) => {
    const roles = el.dataset.requireRole.split(',').map((r) => normalizeRole(r.trim())).filter(Boolean);
    if (roles.length && !hasRole(...roles)) el.hidden = true;
  });

  // Personnalisation de l'avatar/nom à partir de l'utilisateur en cache.
  const user = getUser();
  if (!user) return;

  const fullName = [user.first_name, user.last_name].filter(Boolean).join(' ').trim();
  const initials = fullName
    ? fullName.split(/\s+/).map((part) => part[0]).slice(0, 2).join('').toUpperCase()
    : (user.username || '?').slice(0, 2).toUpperCase();

  const avatar = document.querySelector('[data-user-avatar]');
  if (avatar) avatar.textContent = initials;

  const userLink = document.querySelector('[data-user-link]');
  if (userLink && fullName) userLink.setAttribute('aria-label', `Voir le profil de ${fullName}`);
}

// Protection des pages privées : toute page « app » importe main.js, donc
// ces appels uniques gardent l'ensemble de l'espace de travail.
//   1. requireAuth       → session valide, sinon redirection /login.html ;
//   2. enforcePageRole   → autorisation par rôle (<body data-require-role>).
const isAuthorized = requireAuth() && enforcePageRole();

if (isAuthorized) {
  // Message éventuel déposé avant une redirection (ex. accès refusé).
  const flash = takeFlash();
  if (flash) {
    showToast({
      title: flash.type === 'danger' ? 'Accès refusé' : 'Information',
      text: flash.message,
      type: flash.type,
    });
  }

  document.addEventListener('siou:components-ready', initSidebar);
  document.addEventListener('siou:components-ready', initSessionUI);
  document.addEventListener('siou:components-ready', initNotifications);
  initTheme();
}

isAuthorized && (async () => {
    // Gestion de la sidebar
    const sidebar = document.querySelector('.sidebar');

    // Gestion des menus contextuels
    const menuTriggers = document.querySelectorAll('[data-menu-trigger]');
    menuTriggers.forEach(trigger => {
        const menuId = trigger.getAttribute('data-menu-trigger');
        const menu = document.getElementById(menuId);
        if (!menu) return;

        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            menu.classList.toggle('is-open');
            trigger.setAttribute('aria-expanded', menu.classList.contains('is-open'));
        });
    });

    document.addEventListener('click', (e) => {
        menuTriggers.forEach(trigger => {
            const menuId = trigger.getAttribute('data-menu-trigger');
            const menu = document.getElementById(menuId);
            if (menu && !menu.contains(e.target) && e.target !== trigger) {
                menu.classList.remove('is-open');
                trigger.setAttribute('aria-expanded', 'false');
            }
        });
    });

    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape') return;
        menuTriggers.forEach(trigger => {
            const menuId = trigger.getAttribute('data-menu-trigger');
            const menu = document.getElementById(menuId);
            if (menu && menu.classList.contains('is-open')) {
                menu.classList.remove('is-open');
                trigger.setAttribute('aria-expanded', 'false');
                trigger.focus();
            }
        });
    });


    // Gestion des suggestions de chat
    document.querySelectorAll('[data-suggestion]').forEach(suggestion => {
        suggestion.addEventListener('click', () => {
            const question = suggestion.getAttribute('data-suggestion');
            const input = document.querySelector('[data-composer-input]');
            if (input) {
                input.value = question;
                input.focus();
                // Déclencher l'événement input pour les éventuels listeners
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
        });
    });

    // Gestion du panneau d'historique rétractable
    const historyToggleCollapse = document.getElementById('history-toggle-collapse');
    const historyToggleExpand = document.getElementById('history-toggle-expand');
    const chatLayout = document.querySelector('.chat-layout');

    // Vérifier si les éléments existent (seulement sur la page de chat)
    if (historyToggleCollapse && historyToggleExpand && chatLayout) {
        // Charger l'état précédent depuis localStorage
        const isHistoryCollapsed = localStorage.getItem('chatHistoryCollapsed') === 'true';

        // Appliquer l'état initial avec gestion améliorée
        if (isHistoryCollapsed) {
            chatLayout.classList.add('history-collapsed');
            historyToggleCollapse.style.display = 'none';
            historyToggleExpand.style.display = 'block';
            // Mettre à jour les attributs ARIA pour accessibilité
            historyToggleCollapse.setAttribute('aria-expanded', 'false');
            historyToggleExpand.setAttribute('aria-expanded', 'true');
        } else {
            // S'assurer que le bouton collapse est visible par défaut
            historyToggleCollapse.style.display = 'block';
            historyToggleExpand.style.display = 'none';
            historyToggleCollapse.setAttribute('aria-expanded', 'true');
            historyToggleExpand.setAttribute('aria-expanded', 'false');
        }

        // Toggle pour masquer l'historique
        historyToggleCollapse.addEventListener('click', () => {
            chatLayout.classList.add('history-collapsed');
            historyToggleCollapse.style.display = 'none';
            historyToggleExpand.style.display = 'block';
            // Mettre à jour les attributs ARIA
            historyToggleCollapse.setAttribute('aria-expanded', 'false');
            historyToggleExpand.setAttribute('aria-expanded', 'true');
            // Sauvegarder l'état dans localStorage
            localStorage.setItem('chatHistoryCollapsed', 'true');
        });

        // Toggle pour afficher l'historique
        historyToggleExpand.addEventListener('click', () => {
            chatLayout.classList.remove('history-collapsed');
            historyToggleCollapse.style.display = 'block';
            historyToggleExpand.style.display = 'none';
            // Mettre à jour les attributs ARIA
            historyToggleCollapse.setAttribute('aria-expanded', 'true');
            historyToggleExpand.setAttribute('aria-expanded', 'false');
            // Sauvegarder l'état dans localStorage
            localStorage.setItem('chatHistoryCollapsed', 'false');
        });

        // Gestion du clavier pour accessibilité
        historyToggleCollapse.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                historyToggleCollapse.click();
            }
        });

        historyToggleExpand.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                historyToggleExpand.click();
            }
        });
    }

})();
