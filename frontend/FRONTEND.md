# SIOU - Système Intelligent d'Orientation des Usagers

Interface Front-End du chatbot d'orientation administrative du **Ministère de la
Transformation Digitale et de l'Innovation du Bénin**.

HTML5 / CSS3 / JavaScript ES6+ natifs aucun framework, aucune dépendance de build.

---

## 1. Structure du projet

```
frontend/
├── login.html                 # Page de connexion (hors shell applicatif)
├── index.html                 # Accueil = assistant (injecte pages/chat-content.html)
├── dashboard.html             # Tableau de bord / statistiques
├── pages/
│   ├── chat.html               # Interface conversationnelle (page dédiée)
│   ├── chat-content.html       # Fragment du chat injecté dans index.html
│   ├── historique.html         # Historique des conversations
│   ├── documents.html          # Base documentaire (RAG) — protégée par rôle
│   ├── parametres.html         # Paramètres utilisateur
│   ├── profil.html             # Profil utilisateur
│   ├── utilisateurs.html       # Administration des comptes — réservée au rôle admin
│   ├── feedbacks.html          # Modération des signalements — réservée au rôle admin
│   ├── aide.html                # Centre d'aide / FAQ
│   └── 404.html                 # Page introuvable
├── components/                 # Fragments HTML partagés (injectés en JS)
│   ├── sidebar.html
│   └── topbar.html
├── assets/
│   ├── css/
│   │   ├── 00-variables.css     # Design tokens (couleurs, typo, espacements)
│   │   ├── 01-base.css          # Reset + accessibilité
│   │   ├── 02-layout.css        # Sidebar, topbar, grille
│   │   ├── 03-components.css    # Boutons, cartes, modales, toasts...
│   │   ├── 04-chat.css          # Interface de chat
│   │   ├── 05-animations.css    # Keyframes et transitions
│   │   ├── 06-responsive.css    # Media queries
│   │   └── 07-auth.css          # Écran de connexion (chargé par login.html)
│   ├── js/
│   │   ├── main.js              # Point d'entrée : garde d'auth + orchestration
│   │   └── modules/
│   │       │  # — Infrastructure API / authentification —
│   │       ├── api.js               # Cœur HTTP : base URL, Bearer, refresh, erreurs
│   │       ├── auth.js              # login / logout / refresh / rôles (RBAC)
│   │       ├── route-guard.js       # requireAuth / requireGuest / enforcePageRole
│   │       ├── login.js             # Contrôleur de la page de connexion
│   │       ├── chat-service.js      # POST /api/chat
│   │       ├── feedback-service.js  # POST /api/feedbacks + admin (liste/suppression)
│   │       ├── feedbacks-admin.js   # Contrôleur de la page Signalements (modération)
│   │       ├── user-service.js      # GET/POST/PATCH/DELETE /api/admin/users
│   │       ├── users-admin.js       # Contrôleur de la page Administration des comptes
│   │       ├── stats-service.js     # GET /api/stats (statistiques du tableau de bord)
│   │       ├── dashboard.js         # Contrôleur du tableau de bord (chiffres réels)
│   │       │  # — UI / composants —
│   │       ├── component-loader.js  # Injection sidebar/topbar
│   │       ├── theme.js             # Thème clair/sombre
│   │       ├── settings.js          # Préférences (page Paramètres) + effacement historique
│   │       ├── sidebar.js           # Sidebar rétractable + tiroir mobile
│   │       ├── modal.js             # Modales accessibles
│   │       ├── toast.js             # Notifications toast
│   │       ├── context-menu.js      # Menus contextuels
│   │       ├── search.js            # Recherche instantanée
│   │       ├── filters.js           # Filtres à puces
│   │       ├── notifications.js     # Panneau de notifications
│   │       ├── skeleton.js          # États de chargement
│   │       ├── chat.js              # Logique de la conversation (branchée API)
│   │       ├── streaming.js         # Utilitaire d'affichage progressif
│   │       ├── voice-recorder.js    # Saisie vocale (dictée dans le composer)
│   │       ├── storage.js           # Persistance localStorage + sessionStorage
│   │       └── utils.js             # Fonctions utilitaires génériques
│   ├── images/
│   └── icons/
```

## 2. Lancer le projet en local

Le chargement des composants (`component-loader.js`) utilise `fetch()`, qui
nécessite un serveur HTTP (il ne fonctionne pas en ouvrant le fichier
directement avec `file://`).

```bash
python -m http.server 8080 --directory frontend
# puis ouvrir http://localhost:8080/login.html
```

> Pour la mise en route **complète** (backend, base de données, variables
> d'environnement, comptes de test, réglage de l'URL d'API en cross-origin,
> guide de test de toutes les pages), voir la **section 0 du `README.md`** à la
> racine du dépôt. `http.server` n'envoie pas d'en-têtes de cache : après une
> modification `.js`/`.css`, faites un rechargement forcé (Ctrl+Shift+R).

## 3. Communication avec l'API (couche centralisée)

Le frontend ne fait **jamais** d'appel `fetch` direct depuis les contrôleurs :
tout transite par une couche HTTP unique, `assets/js/modules/api.js`, qui gère :

- la **base d'URL** (`window.SIOU_API_BASE` ou `<html data-api-base>`, défaut `/api`) ;
- l'ajout automatique du **jeton JWT** (`Authorization: Bearer …`) ;
- le **rafraîchissement transparent** du jeton sur `401` (mutualisé), et la
  déconnexion propre si le refresh échoue ;
- un **timeout** et la **normalisation des erreurs** (`ApiError` : réseau,
  timeout, http) + `messageFromError()` pour un message affichable cohérent.

Au-dessus de `api.js`, des **services** minces exposent chaque domaine
métier (un fichier = un domaine) :

```js
// assets/js/modules/chat-service.js
import { apiFetch } from './api.js';

export function askQuestion({ question, conversationId = null, documentIds = [] }) {
  const body = { question };
  if (conversationId) body.conversation_id = conversationId;
  if (documentIds.length) body.document_ids = documentIds;
  return apiFetch('/chat', { method: 'POST', body }); // → /api/chat
}
```

Un contrôleur d'UI (ex. `chat.js`) importe le service, jamais `fetch` :

```js
import { askQuestion } from './chat-service.js';
import { messageFromError } from './api.js';
import { showToast } from './toast.js';

try {
  const data = await askQuestion({ question, conversationId });
  addAssistantMessage(data.text, data.sources, { confidence: data.confidence });
} catch (error) {
  showToast({ title: 'Échec de la requête', text: messageFromError(error), type: 'danger' });
}
```

Services disponibles : `chat-service.js` (`POST /api/chat`),
`feedback-service.js` (`POST /api/feedbacks`), `conversation-service.js`
(`GET /api/conversations`), `document-service.js` (`GET/POST/PUT/DELETE
/api/documents`, `validate`). Le détail de l'architecture d'intégration figure
en **section 0.8 du `README.md`**.

> `streaming.js` reste disponible pour un affichage progressif du texte (le
> backend actuel renvoie une réponse complète en JSON, sans SSE).

## 3 bis. Authentification, session et rôles

- **Connexion** : `login.html` + `login.js` → `auth.login()` (`POST /api/auth/login`).
  Les jetons et le profil sont stockés via `storage.js`, en `localStorage`
  (« Rester connecté ») ou `sessionStorage` (session d'onglet).
- **Protection des pages** : `main.js` (importé par toutes les pages applicatives)
  appelle `requireAuth()` — pas de jeton ⇒ redirection vers `login.html`.
- **Autorisation par rôle (RBAC)** : déclarative, via un attribut sur la page :
  `<body data-require-role="admin, responsable_ministere, point_focal">`.
  `enforcePageRole()` (dans `route-guard.js`) redirige vers l'accueil si le rôle
  ne convient pas ; les liens de navigation interdits sont masqués.
- **Déconnexion** : bouton de la topbar → `auth.logout()` + nettoyage de session.

## 4. Conventions de code

- **CSS** : tokens uniquement (`var(--color-...)`), jamais de valeurs codées en
  dur pour les couleurs. Nommage BEM (`.card__header`, `.card--hover`).
- **JS** : modules ES natifs, une responsabilité par fichier, aucune variable
  globale implicite. Chaque module vérifie la présence de son point d'ancrage
  DOM avant d'agir (sûr sur toutes les pages).
- **API** : jamais de `fetch` direct dans un contrôleur. Passer par un service
  (`*-service.js`) qui s'appuie sur `api.js`. Les erreurs se traduisent via
  `messageFromError()` et s'affichent en toast/bulle — **jamais d'`alert()`**.
- **Accessibilité** : focus visible, `aria-*` sur les composants interactifs,
  piège de focus dans les modales, lien d'évitement, respect de
  `prefers-reduced-motion`.

## 5. Identité visuelle

- Bleu-nuit administratif (`--color-primary`) comme couleur d'autorité.
- Vert, jaune, rouge du Bénin utilisés uniquement comme **fil signature**
  discret (dégradé 3px sur les liens actifs, le logo, la page 404) jamais en
  aplat large, pour rester sobre et institutionnel.
- Typographies : **Sora** (titres), **Inter** (texte courant), **JetBrains
  Mono** (données/code).
