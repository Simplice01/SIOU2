# Étude d'architecture - SIOU
### Système Intelligent d'Orientation des Usagers
**Document de référence technique - du prototype académique au produit institutionnel**

---

*Concepteurs : Omotola, Freud-Arthur et Halil - IFRI, Université d'Abomey-Calavi.*
*Commanditaire fonctionnel : Ministère de la Transformation Digitale et de l'Innovation (MTDI), République du Bénin.*

---

## Comment lire ce document

Ce document est écrit pour trois étudiants qui maîtrisent les bases de la programmation mais découvrent l'ingénierie logicielle à l'échelle d'un produit réel. Chaque décision technique est donc justifiée avant d'être posée : on explique **le problème**, **les options disponibles**, **pourquoi telle option gagne** et **ce qu'on perd en échange**. Aucune technologie n'est choisie « parce que c'est à la mode » chaque choix a un compromis explicite (coût, complexité, courbe d'apprentissage, dépendance à un fournisseur).

Le document est long par nécessité : il doit pouvoir être ouvert à n'importe quelle étape des six prochains mois de développement et répondre à la question « pourquoi a-t-on fait ce choix, déjà ? ». Il n'est pas nécessaire de le lire d'une traite. La table des matières ci-dessous permet d'aller directement à la section utile.

## 0. Démarrage rapide et guide de test

> Cette section est le **mode d'emploi opérationnel** du projet : comment lancer le
> backend et le frontend, comment se connecter, et comment tester chaque page.
> Le reste du document (à partir de la section 1) reste l'étude d'architecture.

### 0.1. Vue d'ensemble et pile technique

SIOU est une application **3-tiers** (cf. section 3) :

| Tiers | Technologie | Rôle |
|---|---|---|
| **Frontend** | HTML5 / CSS3 / JavaScript ES6+ natif, **sans build** | Interface (chat, documents, historique, auth) |
| **Backend** | **FastAPI** (Python ≥ 3.12), SQLAlchemy async, `python-jose` (JWT), `bcrypt` | API REST `/api/*` |
| **Base de données** | **PostgreSQL** (asyncpg, extension `pgvector` prévue) | Utilisateurs, documents, conversations… |

> **État actuel** : **tous les endpoints sont branchés sur PostgreSQL et protégés
> par JWT** (auth, chat, conversations, documents, feedbacks). Le chat persiste
> conversations et messages ; seule la *génération* de la réponse reste un stub
> (`generate_demo_answer`) en attendant le pipeline RAG + LLM (Ollama, embeddings,
> pgvector). L'ancien `backend/services/mock_store.py` n'est plus utilisé.

### 0.2. Prérequis

- **Python 3.12** (voir `.python-version`)
- **[uv](https://docs.astral.sh/uv/)** (gestionnaire de dépendances ; `uv.lock` fait foi)
- **PostgreSQL ≥ 13** *(uniquement pour tester la connexion réelle ; facultatif pour le reste - voir 0.6)*
- Un navigateur moderne

### 0.3. Configuration (`.env` à la racine du dépôt)

Le backend lit un fichier `.env` (via `pydantic-settings`). Deux variables sont
**obligatoires**  sans elles, le serveur ne démarre pas :

```dotenv
# .env  (à la racine du projet)
DATABASE_URL=postgresql+asyncpg://siou:siou@localhost:5432/siou
JWT_SECRET_KEY=une-cle-secrete-longue-et-aleatoire
```

> Au démarrage, le `lifespan` du backend exécute `create_all` (création idempotente
> des tables manquantes) : une **`DATABASE_URL` joignable est donc requise dès le
> lancement**. Tous les endpoints de données passent désormais par la base.

### 0.4. Lancer le backend

```bash
uv sync                                   # installe les dépendances
uv run uvicorn main:app --reload          # démarre l'API sur http://localhost:8000
```

- Documentation interactive (Swagger, générée automatiquement) : <http://localhost:8000/docs>
- Contrôle de santé : <http://localhost:8000/health>

### 0.5. Lancer le frontend

Le frontend a besoin d'un serveur HTTP (les composants sont chargés via `fetch`,
qui ne fonctionne pas en `file://`) :

```bash
python -m http.server 8080 --directory frontend
# puis ouvrir http://localhost:8080/login.html
```

> **Alternative « tout-en-un » (recommandée pour un test rapide)** : le backend
> sert aussi le frontend sur la **même origine** (montage `StaticFiles`). Il suffit
> donc de lancer le backend (0.4) et d'ouvrir directement
> **`http://localhost:8000/login.html`**  pas de second serveur, pas de
> `SIOU_API_BASE` à régler, pas de CORS (`/api` fonctionne par défaut).

Deux points **indispensables** si vous servez le frontend séparément (dev) :

1. **Base d'API** par défaut le frontend appelle `/api` (même origine, cas de
   production). En dev, frontend (`:8080`) et backend (`:8000`) sont sur des
   origines différentes : il faut indiquer l'URL du backend. Le plus simple, dans
   la **console du navigateur** avant de naviguer :

   ```js
   window.SIOU_API_BASE = 'http://localhost:8000/api';
   ```

   (équivalent persistant : ajouter `data-api-base="http://localhost:8000/api"`
   sur la balise `<html>`). Les origines `:8080` sont déjà autorisées côté CORS
   (`backend/core/config.py`).

2. **Cache**  `python -m http.server` **n'envoie aucun en-tête de cache**. Après
   toute modification d'un fichier `.js` / `.css`, le navigateur peut servir
   l'**ancienne** version. **Faites systématiquement un rechargement forcé
   (Ctrl+Shift+R)** après une modification.

### 0.6. Deux façons de tester

**A. Connexion réelle (recommandé).** La base (Neon PostgreSQL) est déjà
provisionnée : tables créées, `pgvector` activé, et un compte **admin** est seedé.
Les tables manquantes éventuelles (`message_sources`, `feedbacks`) sont créées
automatiquement au démarrage du backend (`create_all` idempotent dans le
`lifespan`). Il suffit donc de :

1. lancer le backend (0.4) et le frontend (0.5), et régler `SIOU_API_BASE` ;
2. ouvrir `/login.html` et se connecter avec le compte admin (identifiants dans le
   `.env` : variables `USERNAME_ADMIN` / `PASSWORD_ADMIN`).

Pour créer d'autres comptes, un admin peut appeler `POST /api/users` (hash bcrypt
automatique). Générer un hash manuellement si besoin :

```bash
.venv/Scripts/python -c "from backend.core.security import hash_password; print(hash_password('motdepasse'))"
```

**B. Aperçu de l'interface sans se connecter (maquettes uniquement).** On peut
amorcer une session factice pour voir les pages **statiques** (dashboard, profil,
aide…) sans backend :

```js
const api = await import('/assets/js/modules/api.js');
api.persistSession({ access: 'dev', refresh: 'dev',
  user: { id: '0', username: 'demo', first_name: 'Demo', role: 'admin' }, remember: true });
location.href = '/index.html';
```

> Depuis le branchement du vrai backend, les pages **branchées sur l'API**
> (chat, historique, base documentaire) exigent un **JWT valide** : un jeton factice
> renverra `401` (puis déconnexion automatique). Pour ces pages, utilisez la
> **connexion réelle** (A). Le rôle du compte détermine l'accès RBAC (`user` → la
> Base documentaire redirige ; `admin` → accès autorisé).

### 0.7. Guide de test - toutes les pages

Légende d'intégration : ✅ branché sur l'API · 🚧 intégration en cours · 🎨 maquette statique.

| Page | URL | Rôle requis | Intégration | Quoi tester |
|---|---|---|---|---|
| **Connexion** | `/login.html` | public | ✅ `POST /api/auth/login` | Identifiants corrects/incorrects, « Rester connecté » (localStorage vs sessionStorage), afficher/masquer le mot de passe, messages d'erreur (réseau, 401), redirection après connexion |
| **Accueil / Chat** | `/index.html` | connecté | ✅ `POST /api/chat`, `POST /api/feedbacks` | Poser une question → réponse + **sources** + score de confiance (stocké) ; bouton **« Signaler »** ; erreurs réseau/serveur affichées en bulle + toast |
| **Assistant SIOU** | `/pages/chat.html` | connecté | ✅ idem chat | Même logique de conversation |
| **Historique** | `/pages/historique.html` | connecté | ✅ `GET /api/conversations` | Liste des conversations (titres + dates). *Rejeu impossible : le backend ne renvoie pas les messages.* |
| **Base documentaire** | `/pages/documents.html` | `admin` / `responsable_ministere` / `point_focal` | ✅ `GET/POST/PUT/DELETE /api/documents`, `validate` | Liste, ajout (métadonnées), modification, suppression, validation ; **redirection si rôle insuffisant** |
| **Statistiques** | `/dashboard.html` | connecté | 🎨 | Affichage, thème clair/sombre |
| **Mon profil** | `/pages/profil.html` | connecté | 🎨 | Affichage (à brancher ultérieurement) |
| **Paramètres** | `/pages/parametres.html` | connecté | 🎨 | Bascule de thème, préférences |
| **Centre d'aide** | `/pages/aide.html` | connecté | 🎨 | Contenu statique / FAQ |
| **Déconnexion** | bouton topbar | connecté | ✅ `POST /api/auth/logout` | Nettoie la session → retour `/login.html` |
| **Introuvable** | `/pages/404.html` | — | 🎨 | Page 404 |

### 0.8. Architecture d'intégration côté frontend

Tout passe par une **couche HTTP centralisée**  aucune duplication :

```
assets/js/modules/
├── api.js                 # cœur HTTP : base URL, Bearer auto, timeout,
│                          #   refresh JWT (single-flight), 401→refresh→déconnexion,
│                          #   erreurs normalisées (ApiError), messageFromError()
├── auth.js                # login / logout / refresh / rôles (RBAC)
├── route-guard.js         # requireAuth / requireGuest / enforcePageRole
├── storage.js             # localStorage + sessionStorage (namespacés)
├── chat-service.js          # POST /api/chat
├── feedback-service.js      # POST /api/feedbacks
├── conversation-service.js  # GET /api/conversations
└── document-service.js      # GET/POST/PUT/DELETE /api/documents (+validate)
```

- **Configuration de l'URL d'API** : `window.SIOU_API_BASE` ou `<html data-api-base>` (défaut `/api`).
- **Jeton JWT** : ajouté automatiquement à chaque requête ; rafraîchi de façon transparente sur `401` ; déconnexion propre si le refresh échoue.
- **Erreurs** : réseau, timeout, serveur, 401/403 → messages intégrés (toasts / bulles), **jamais d'`alert()`**.

### 0.9. Dépannage

| Symptôme | Cause probable / solution |
|---|---|
| Modif JS/CSS sans effet | Cache du serveur de dev → **Ctrl+Shift+R** |
| Redirigé vers `/login.html` | Aucun jeton (normal) ou session expirée → se (re)connecter |
| Redirigé vers l'accueil sur `/documents.html` | Rôle insuffisant (RBAC) → utiliser un compte `admin`/`responsable_ministere`/`point_focal` |
| Erreur CORS dans la console | `SIOU_API_BASE` non défini, ou origine absente de `cors_origins` |
| Le backend ne démarre pas | `DATABASE_URL` ou `JWT_SECRET_KEY` absents du `.env` |
| `500` à la connexion | Base non joignable ou table `users` absente (seul `/auth/*` utilise la base) |

### 0.10. Structure du dépôt

```
SIOU-MTDI/
├── main.py                 # point d'entrée FastAPI (uvicorn main:app)
├── pyproject.toml, uv.lock # dépendances (uv)
├── .env                    # DATABASE_URL, JWT_SECRET_KEY (à créer)
├── backend/
│   ├── core/               # config, database, security (JWT/bcrypt), deps (RBAC)
│   ├── routers/            # auth, chat, conversation, documents, feedbacks, users
│   ├── models/             # SQLAlchemy + schémas Pydantic + SQL (models/db/*.sql)
│   └── services/           # mock_store (données de démo), llm
└── frontend/
    ├── login.html, index.html, dashboard.html, pages/*.html
    ├── components/         # sidebar, topbar (injectés en JS)
    └── assets/{css,js}/    # voir FRONTEND.md pour le détail
```

Voir aussi **`frontend/FRONTEND.md`** (conventions front) et **`backend/api.md`**
(détail des endpoints). *Note : la section « Brancher l'API » de `FRONTEND.md` est
désormais partiellement obsolète l'intégration réelle est décrite ici en 0.8.*

---

## Table des matières

0. [Démarrage rapide et guide de test](#0-démarrage-rapide-et-guide-de-test)
1. [Analyse du prototype existant](#1-analyse-du-prototype-existant)
2. [Analyse fonctionnelle](#2-analyse-fonctionnelle)
3. [Architecture globale](#3-architecture-globale)
4. [Frontend](#4-frontend)
5. [Backend](#5-backend)
6. [Base de données](#6-base-de-données)
7. [Architecture RAG en profondeur](#7-architecture-rag-en-profondeur)
8. [Modèles d'embeddings](#8-modèles-dembeddings)
9. [Choix du LLM](#9-choix-du-llm)
10. [Collecte et sources de données](#10-collecte-et-sources-de-données)
11. [Mise à jour automatique des données](#11-mise-à-jour-automatique-des-données)
12. [Sécurité](#12-sécurité)
13. [Hébergement](#13-hébergement)
14. [DevOps](#14-devops)
15. [Monitoring](#15-monitoring)
16. [Tests](#16-tests)
17. [Performance](#17-performance)
18. [Accessibilité](#18-accessibilité)
19. [Gouvernance des données](#19-gouvernance-des-données) *(section ajoutée facteur clé de réussite identifié par le commanditaire)*
20. [Conformité légale béninoise](#20-conformité-légale-béninoise) *(section ajoutée)*
21. [Feuille de route](#21-feuille-de-route)
22. [Ressources par technologie](#22-ressources-par-technologie)

---

## 1. Analyse du prototype existant

### 1.1. Ce que fait le prototype aujourd'hui

D'après le README et le code du dépôt `MessireFreud/DTDI_MANAGEMENT`, le prototype actuel est une application **Streamlit monolithique** :

```
app.py            → interface (Streamlit) + historique de session
main_freud.py      → filtrage des entrées, prompt système, appel au LLM
utils.py           → découpage du corpus, FAISS, recherche par similarité
data/infos.md       → corpus unique (Markdown) sur DD, DN, ASIN, SBIN
```

Le flux est linéaire : l'usager tape une question → `ask()` filtre les cas triviaux (salutations, message vide, tentative d'injection) → `build_context()` interroge un index FAISS construit à partir de `data/infos.md` → les 5 passages les plus proches sont concaténés → le tout est envoyé au modèle `meta-llama/Llama-3.1-8B-Instruct` via l'API d'inférence Hugging Face → la réponse est affichée.

C'est une architecture RAG **naïve** au sens technique du terme (chunking simple, un seul document source, pas de reranking, pas de citations structurées, pas de mémoire de conversation persistée) ce qui est **normal et attendu** pour un prototype académique construit en quelques semaines. Le rôle de ce document est de faire la liste précise de ce qui doit changer pour passer au produit suivant, sans jeter ce qui fonctionne déjà.

### 1.2. Points forts à conserver

- **La logique métier est déjà séparée de l'interface** (`main_freud.py` / `utils.py` vs `app.py`). C'est la meilleure nouvelle du prototype : cela veut dire qu'on peut remplacer Streamlit par une vraie API sans réécrire le cœur du RAG, seulement le réorganiser.
- **Le filtrage des entrées existe déjà** (salutations, entrées vides, tentative d'injection basique). C'est un embryon de sécurité qu'il faut renforcer, pas jeter.
- **Le choix du RAG plutôt que du fine-tuning** était le bon choix dès le départ : les informations institutionnelles (adresses, attributions, procédures) changent souvent, et un modèle fine-tuné coûterait cher à réentraîner à chaque changement. Le RAG permet de mettre à jour le comportement du système en changeant simplement les documents sources.
- **Un modèle d'embedding multilingue** (`paraphrase-multilingual-MiniLM-L12-v2`) a été choisi dès le prototype, ce qui montre une bonne intuition : le contexte béninois mélange français, expressions locales et parfois anglais administratif.

### 1.3. Limites techniques identifiées

| Limite | Pourquoi c'est un problème à l'échelle d'un produit |
|---|---|
| **Un seul fichier `data/infos.md`** comme base documentaire | Aucune structuration par direction/agence, aucune métadonnée (date, source, validité), impossible de savoir *quel document* a produit une réponse donnée. |
| **FAISS reconstruit en mémoire à chaque démarrage** | Pas de persistance, pas de mise à jour incrémentale : ajouter un document oblige à réindexer tout le corpus. Ne supporte pas plusieurs instances de l'application en parallèle. |
| **Streamlit comme interface** | Excellent pour prototyper, mais pas conçu pour un site public à fort trafic, difficile à styliser finement, pas de gestion fine des sessions multi-utilisateurs, pas d'authentification native robuste, rechargements de page peu fluides comparés à une SPA moderne. |
| **Pas de couche API séparée** | Le frontend et la logique métier sont dans le même processus Python. Impossible de brancher une future application mobile, un widget à intégrer au portail vitrine du ministère, ou un canal WhatsApp/Telegram sans dupliquer la logique. |
| **Pas de citations structurées** | La réponse ne précise pas explicitement *quel document* a permis de répondre, essentiel pour la confiance dans un contexte administratif (cf. présentation : « aucune réponse sans document source »). |
| **Pas de reranking** | La recherche vectorielle pure (top-5 par similarité cosinus) rate parfois le bon passage quand la question est formulée très différemment du document source. |
| **Pas de mémoire de conversation persistée en base** | `memory.json` existe mais son rôle exact n'est pas industrialisé ; pas de historique consultable, pas de traçabilité. |
| **Un seul modèle de génération codé en dur** | `meta-llama/Llama-3.1-8B-Instruct` via l'API Hugging Face crée une dépendance à un service tiers payant, avec latence réseau, alors que la présentation officielle du projet mentionne désormais un objectif d'auto-hébergement via Ollama (Mistral), cohérent avec un souci de souveraineté des données publiques. |
| **Pas de gestion des rôles** | Le prototype ne distingue pas usager, secrétaire, et responsable de direction alors que la présentation identifie explicitement ces deux derniers profils avec des besoins différents (consultation rapide vs édition des fiches de service). |
| **Secrets en clair dans `.env` / `secrets.toml` committables** | Risque classique de fuite de jeton d'API si le `.gitignore` n'est pas strictement respecté. |

### 1.4. Améliorations possibles (aperçu détaillées section par section)

- Passage à une architecture **trois tiers** : frontend web découplé, API backend, base de données + moteur RAG.
- Structuration du corpus documentaire par **direction/agence**, avec métadonnées (source, date de validité, responsable).
- **Back-office** pour que chaque direction/agence corrige ses propres fiches (répond directement au besoin du persona « Responsable de direction »).
- **Auto-hébergement du LLM via Ollama**, aligné avec la présentation officielle et avec les impératifs de souveraineté des données publiques béninoises.
- **Vector store persistant** (et non reconstruit en mémoire) avec réindexation incrémentale.
- **Citations systématiques** des sources dans chaque réponse, avec score de confiance.
- **Authentification et rôles** (usager anonyme / secrétaire / responsable de direction / administrateur).

### 1.5. Risques techniques à anticiper

1. **Hallucination résiduelle** : même avec du RAG, un LLM peut produire une réponse plausible mais fausse si le contexte récupéré est incomplet ou ambigu. Il faut un mécanisme de refus explicite (« je ne trouve pas cette information dans les documents disponibles ») plutôt que de laisser le modèle deviner c'est le rôle du **confidence gate**, détaillé en section 7.
2. **Dérive du corpus** : sans processus de gouvernance, la base documentaire devient obsolète en quelques mois (adresses qui changent, nouvelles procédures). C'est le facteur de risque n°1 identifié par le commanditaire lui-même (cf. section 19).
3. **Dépendance à un unique modèle hébergé par un tiers** : un changement de tarification, de disponibilité ou de politique d'un fournisseur d'API peut interrompre le service. L'auto-hébergement réduit ce risque mais en introduit un autre : la responsabilité de maintenir l'infrastructure d'inférence.
4. **Charge de calcul sous-estimée** : un LLM auto-hébergé (même « petit », 7-14 milliards de paramètres) demande des ressources GPU/CPU que les hébergements gratuits ou peu coûteux (Render, Railway, Vercel) ne fournissent pas nativement c'est un point de décision majeur en section 13.
5. **Sécurité des injections de prompt** : un usager malveillant qui tente de faire ignorer les consignes système au modèle, ou qui insère des instructions cachées dans un document indexé (injection indirecte). Détaillé en section 12.
6. **Effet tunnel du prototype étudiant** : le risque n'est pas seulement technique c'est de continuer à développer en solo sans jamais faire valider le périmètre de données et le canal de diffusion par le ministère, ce que la feuille de route officielle place justement comme « Étape 1 · Décision » avant toute consolidation.

---

## 2. Analyse fonctionnelle

### 2.1. Le vrai problème à résoudre

D'après la présentation officielle, SIOU ne répond pas à « comment faire ma carte d'identité » en général il répond à trois questions précises, formulées par le commanditaire lui-même :

- **Qui fait quoi** : quelle direction, agence ou société est compétente pour une démarche donnée (ex. qui délivre le label Startup ?).
- **Où** : la localisation exacte d'un service (adresse, téléphone, horaires).
- **Quoi de neuf** : les événements en cours ou à venir dans le secteur numérique/IA béninois.

C'est un système d'**orientation**, pas un système d'**exécution de démarche**. Cette distinction doit rester au centre de toutes les décisions de conception : SIOU ne remplace pas le service public, il réduit le temps avant que l'usager parle à la bonne personne.

### 2.2. Utilisateurs et besoins

| Persona | Contexte d'usage | Besoin principal | Critère de succès |
|---|---|---|---|
| **Secrétaire** (utilisateur principal) | Au guichet, usager en face d'elle, questions formulées librement et parfois imprécises | Réponse courte, fiable, quasi immédiate | Réponse structurée affichée en moins de 15 secondes |
| **Responsable de direction / point focal agence** | Back-office, hors interaction directe avec l'usager | Pouvoir corriger/valider les informations concernant son propre service | Fiche mise à jour et validée en moins de 24h |
| **Usager final** (indirect, via la secrétaire ou via le portail vitrine) | Premier contact avec l'administration, ne connaît pas l'organigramme | Être orienté sans avoir à connaître la structure interne du ministère | Orientation correcte dès le premier échange |
| **Administrateur / responsable désigné (gouvernance)** | Pilotage global de la base de connaissances | Vue d'ensemble sur la fraîcheur des données, les signalements d'erreur | Cycle de révision respecté (ex. mensuel) |

### 2.3. Cas d'utilisation détaillés

**UC1 - Orientation directe (secrétaire → SIOU → réponse)**
1. La secrétaire reçoit un usager et pose la question à SIOU en langage libre, éventuellement reformulée.
2. SIOU comprend l'intention même sans mots-clés exacts (ex. « je veux créer une startup, par où commencer ? »).
3. SIOU identifie la direction/l'agence compétente, avec ses sources.
4. La secrétaire lit la réponse et oriente l'usager physiquement ou par contact direct.

**UC2 - Recherche de localisation**
1. Question du type « où se trouve l'ASIN ? ».
2. SIOU retourne adresse, téléphone, horaires idéalement avec une carte si intégré au portail.

**UC3- Information sur les événements**
1. Question du type « y a-t-il un événement sur l'IA ce mois-ci ? ».
2. SIOU retourne les événements officiels avec date, lieu, organisateur ce qui suppose une source de données *changeante* et pas seulement des PDF statiques (voir section 10 et 11).

**UC4 - Mise à jour d'une fiche de service (back-office)**
1. Un point focal d'agence se connecte au back-office avec ses identifiants.
2. Il consulte les informations actuellement publiées sur son service.
3. Il propose une modification (nouvelle adresse, nouvelle procédure).
4. Selon la gouvernance retenue (voir section 19), la modification est soit publiée directement, soit soumise à validation par le responsable désigné du ministère.
5. Le corpus documentaire est réindexé automatiquement et de façon incrémentale (voir section 11).

**UC5 - Signalement d'erreur**
1. Un usager ou une secrétaire remarque une réponse incorrecte.
2. Un mécanisme simple (bouton « signaler ») envoie l'information au responsable désigné.
3. Le cycle de révision intègre ce signalement.

### 2.4. Parcours utilisateur (exemple filé — secrétaire)

```
Arrivée usager au guichet
        │
        ▼
Secrétaire ouvre SIOU (déjà connectée, session active)
        │
        ▼
Tape la question de l'usager telle quelle, sans reformulation experte
        │
        ▼
SIOU affiche : réponse courte + direction/agence compétente
              + adresse/contact + document(s) source(s) cité(s)
        │
        ▼
Secrétaire confirme oralement à l'usager, ou imprime/partage la fiche
        │
        ▼
(optionnel) Secrétaire signale une réponse imprécise en un clic
```

Ce parcours dicte une contrainte de conception forte : **l'interface de chat doit rester secondaire à la lisibilité de la réponse**. Contrairement à un assistant conversationnel grand public, l'enjeu n'est pas la fluidité de l'échange mais la vitesse de compréhension d'une réponse unique d'où l'importance des citations visibles, du score de confiance, et d'une réponse structurée plutôt qu'un simple paragraphe.

---

## 3. Architecture globale

### 3.1. Qu'est-ce qu'on compare exactement

Avant de choisir une architecture, il faut fixer le vocabulaire : une architecture logicielle, ici, répond à la question « où vit chaque responsabilité, et comment les morceaux communiquent-ils ? ». Trois grandes familles sont pertinentes pour un projet comme SIOU.

### 3.2. Option A - Monolithe amélioré (évolution directe du prototype)

Garder une seule application (par exemple Flask ou Django) qui sert à la fois les pages web et la logique RAG, mais mieux structurée en modules internes.

- **Avantages** : simple à déployer (un seul processus), pas de communication réseau interne à gérer, courbe d'apprentissage plus douce pour une équipe débutante, coût d'hébergement minimal.
- **Inconvénients** : difficile à faire évoluer vers plusieurs canaux (portail vitrine + back-office + éventuelle appli mobile) sans dupliquer du code ; un pic de charge sur le RAG (calcul lourd) ralentit aussi les pages statiques ; toute l'équipe travaille dans la même base de code, ce qui devient source de conflits Git à mesure que le projet grossit.

### 3.3. Option B - Frontend découplé + API backend (architecture trois tiers)

Une application frontend autonome (ce que vous avez déjà commencé à construire en HTML/CSS/JS) qui consomme une API REST (par exemple FastAPI), elle-même connectée à une base de données et à un moteur RAG.

- **Avantages** : le frontend peut évoluer (styles, pages) sans toucher au backend ; la même API peut servir plus tard un widget embarqué dans le portail vitrine du ministère, une application mobile, ou un canal WhatsApp, sans dupliquer la logique métier ; les deux parties peuvent être développées, testées et déployées indépendamment ; c'est l'architecture standard de l'industrie en 2026 pour ce type de produit.
- **Inconvénients** : plus de pièces à faire fonctionner ensemble (CORS, authentification via jetons, versionnement d'API) ; nécessite de comprendre le concept de requêtes HTTP asynchrones côté frontend.

### 3.4. Option C - Microservices (RAG, authentification, back-office en services séparés)

Chaque grande fonction (recherche RAG, gestion des utilisateurs, back-office documentaire) devient un service indépendant, avec sa propre base de données si besoin, communiquant par API interne.

- **Avantages** : scalabilité fine (on peut donner plus de ressources uniquement au service RAG, qui est le plus gourmand) ; équipes différentes peuvent posséder des services différents ; résilience (la panne d'un service n'arrête pas forcément les autres).
- **Inconvénients** : complexité opérationnelle largement disproportionnée pour une équipe de deux étudiants et un trafic encore modeste ; coût d'infrastructure plus élevé (plusieurs bases de données, plusieurs déploiements) ; risques de bugs liés à la communication réseau interne (latence, pannes partielles) qui n'existeraient pas dans un système plus simple.

### 3.5. Comparatif synthétique

| Critère | A. Monolithe | B. Frontend/API découplés | C. Microservices |
|---|---|---|---|
| Complexité de mise en œuvre | Faible | Moyenne | Élevée |
| Coût d'hébergement de départ | Très faible | Faible à moyen | Élevé |
| Facilité d'ajout d'un nouveau canal (mobile, WhatsApp) | Difficile | Facile | Facile |
| Adapté à une équipe de 2 personnes débutantes | Oui | Oui | Non, prématuré |
| Adapté à une évolution vers un vrai produit institutionnel | Limité | Oui | Oui, mais trop tôt |
| Scalabilité indépendante des composants | Non | Partielle | Totale |

### 3.6. Choix retenu et justification

**Option B - Frontend découplé + API backend.** C'est le point d'équilibre entre les deux contraintes réelles du projet : (1) une équipe de deux étudiants qui ne peut pas absorber la complexité opérationnelle des microservices, et (2) une ambition affichée d'évoluer vers un produit institutionnel multi-canal (portail vitrine, back-office, potentiellement un canal mobile plus tard), ce qu'un monolithe rendrait pénible.

Concrètement, cela donne quatre grandes pièces :

```
┌─────────────────┐      HTTPS/JSON       ┌──────────────────────┐
│  Frontend Web     │ ───────────────────▶ │   API Backend          │
│  (HTML/CSS/JS,      │ ◀─────────────────── │   (FastAPI, Python)     │
│   déjà commencé)    │                       │                        │
└─────────────────┘                       └──────────┬─────────────┘
                                                       │
                          ┌────────────────────────────┼─────────────────────────┐
                          ▼                            ▼                         ▼
                ┌──────────────────┐        ┌───────────────────┐      ┌──────────────────┐
                │  Base de données   │        │  Orchestrateur RAG   │      │  LLM auto-hébergé   │
                │  relationnelle       │        │  (recherche vecto-    │      │  (Ollama + Mistral)  │
                │  (PostgreSQL)        │        │  rielle + reranking)  │      │                        │
                └──────────────────┘        └─────────┬───────────┘      └──────────────────┘
                                                        ▼
                                              ┌───────────────────┐
                                              │  Vector store         │
                                              │  (pgvector, dans le    │
                                              │  même PostgreSQL)      │
                                              └───────────────────┘
```

Ce schéma introduit un choix qu'on justifie en détail section 6 et 7 : faire cohabiter la base relationnelle et le vector store dans **un seul moteur PostgreSQL** (extension `pgvector`), plutôt que d'ajouter une base vectorielle séparée (Qdrant, Weaviate...) dès le départ. Ce choix réduit le nombre de services à opérer cohérent avec la contrainte « équipe de 2 personnes, budget étudiant ».

### 3.7. Flux de bout en bout (résumé)

1. La secrétaire tape une question dans le frontend.
2. Le frontend envoie la question à l'API backend (`POST /api/chat`).
3. Le backend authentifie la requête (session secrétaire), journalise la question.
4. L'orchestrateur RAG transforme la question en vecteur, interroge `pgvector`, récupère les passages pertinents, les reclasse (reranking), construit le prompt final.
5. Le prompt est envoyé au LLM auto-hébergé (Ollama).
6. La réponse générée est enrichie des citations de sources et d'un score de confiance, puis renvoyée au frontend.
7. Le frontend affiche la réponse en streaming (mot par mot) pour réduire la sensation d'attente.

---

## 4. Frontend

### 4.1. Ce qui existe déjà

Le front-end SIOU a déjà été construit en HTML5/CSS3/JavaScript ES6+ natif, sans framework, avec une architecture par pages (Dashboard, Chat, Historique, Base documentaire, Paramètres, Profil, Aide, 404), un système de composants HTML partagés (sidebar/topbar injectés en JS), des modules JS strictement séparés par responsabilité (thème, sidebar, modales, toasts, recherche, chat...), et un point de branchement unique vers l'API (`requestAssistantReply()` dans `chat.js`). Cette section explique **pourquoi** cette architecture est adaptée, et ce qu'il faudra ajouter pour coller aux vrais besoins identifiés en section 2 (back-office pour les responsables de direction notamment).

### 4.2. Vanilla JS vs framework (React/Vue) pourquoi le choix actuel tient la route

| Critère | Vanilla JS (existant) | Framework (React/Vue/Svelte) |
|---|---|---|
| Courbe d'apprentissage pour débutants | Faible - HTML/CSS/JS classiques | Élevée - JSX, state management, build tools |
| Taille du bundle / performance au chargement | Minimal, aucun bundler nécessaire | Plus lourd, nécessite Webpack/Vite |
| Adapté à un site principalement informationnel + un chat | Oui | Oui, mais overkill pour 8 pages |
| Facilité de maintenance à long terme (équipe qui grandit) | Moyenne  discipline manuelle nécessaire | Meilleure à grande échelle (composants réutilisables imposés par le framework) |
| Recrutement / transmission du projet | N'importe quel développeur web sait lire du HTML/CSS/JS | Nécessite de connaître le framework choisi |

**Recommandation : garder le vanilla JS pour la V1**, mais avec une règle claire : si le projet dépasse ~15-20 pages ou si l'état partagé entre composants devient difficile à suivre (ce qui arrivera probablement avec le back-office multi-rôles), une migration progressive vers un framework léger (Svelte ou Vue, plus simples à apprendre que React) devient raisonnable. Ce n'est pas un chantier à faire « au cas où » - react/Vue résolvent un problème (synchronisation d'état complexe) que le projet n'a pas encore.

### 4.3. Organisation des dossiers (déjà en place, rappel des principes)

```
siou/
├── index.html, pages/*.html      # une page = un fichier, pas de SPA
├── components/                    # fragments HTML injectés en JS (DRY)
├── assets/css/                    # design tokens → base → layout → composants → pages spécifiques
├── assets/js/modules/             # un fichier = une responsabilité (SRP)
```

Le principe directeur est le **SRP (Single Responsibility Principle)** appliqué au JS : chaque module (`theme.js`, `modal.js`, `chat.js`...) ne connaît qu'une chose et l'expose via une fonction `init...()`. Cela permet d'ajouter le back-office (section 4.5) comme un nouvel ensemble de pages + modules, sans toucher à l'existant.

### 4.4. Responsive et accessibilité (déjà posés, à faire vivre)

Le responsive est géré par des media queries à trois paliers (desktop, tablette ≤1024px, mobile ≤600px) et l'accessibilité par des attributs ARIA, un piège de focus dans les modales et le respect de `prefers-reduced-motion`. Le point d'attention pour la suite : **tester réellement avec un lecteur d'écran** (NVDA gratuit sous Windows, VoiceOver sous macOS) avant la mise en production, car les attributs ARIA mal posés donnent une fausse impression de conformité.

### 4.5. Ce qu'il faut ajouter pour coller aux vrais besoins (section 2)

- **Espace back-office** pour les responsables de direction/points focaux : une nouvelle famille de pages (`/backoffice/fiches.html`, `/backoffice/fiche-edit.html`, `/backoffice/validations.html`) protégée par authentification, avec un rôle distinct de l'espace secrétaire.
- **Suggestions de questions réalignées** sur les vrais cas d'usage (« qui délivre le label Startup », « où se trouve l'ASIN », plutôt que des démarches citoyennes génériques).
- **Widget embarquable** : à terme, une version compacte du chat conçue pour être intégrée en `<iframe>` ou en web component dans le portail vitrine existant du ministère (cf. présentation, slide 4 : « pourrait être intégré au portail vitrine »).

### 4.6. Performance

Trois leviers, par ordre d'impact réel pour ce projet :

1. **Ne charger que ce qui est nécessaire par page** (déjà le cas : pas de bundle JS unique de 2 Mo, chaque page importe ses propres modules).
2. **Mettre en cache les polices et assets statiques** via des en-têtes HTTP appropriés côté hébergeur (Cache-Control), et servir les images en formats modernes (WebP/AVIF) si la base documentaire inclut des visuels.
3. **Streaming de la réponse du chat** (déjà simulé côté front, à brancher sur un vrai flux SSE voir section 5.4) : le principal problème de performance perçue dans un RAG n'est pas le rendu de page mais le temps d'attente de la réponse du modèle ; le streaming réduit la latence perçue même si la latence réelle ne change pas.

---

## 5. Backend

### 5.1. Choix du framework : FastAPI

| Critère | FastAPI | Django | Flask |
|---|---|---|---|
| Performance (async natif) | Élevée | Moyenne (Django async encore jeune) | Faible sans extensions |
| Documentation d'API automatique | Oui (Swagger/OpenAPI générés automatiquement) | Non nativement | Non nativement |
| Validation des données | Native (Pydantic) | Via formulaires/serializers (DRF) | Manuelle ou via extensions |
| Courbe d'apprentissage pour débutants | Moyenne | Élevée (ORM, admin, conventions nombreuses) | Faible mais peu structurant |
| Adapté à une API pure (pas de rendu de pages serveur) | Oui, conçu pour ça | Oui mais plus lourd que nécessaire | Oui mais moins outillé |
| Écosystème RAG/IA (LangChain, clients LLM) | Très bien supporté, async compatible | Supporté mais moins naturel | Supporté |

**Choix retenu : FastAPI.** Trois raisons concrètes pour ce projet précis : (1) le support natif de l'**asynchrone**, indispensable pour ne pas bloquer le serveur pendant qu'on attend la réponse (parfois longue) du LLM ; (2) la **documentation Swagger générée automatiquement**, qui aide énormément une équipe débutante à tester son API sans outil supplémentaire ; (3) **Pydantic**, qui force à définir précisément la forme des données échangées (question, réponse, sources, score de confiance) et attrape une grande partie des bugs avant même l'exécution.

### 5.2. Architecture interne de l'API (organisation des dossiers)

```
backend/
├── app/
│   ├── main.py                 # point d'entrée FastAPI
│   ├── api/
│   │   ├── routes_chat.py       # POST /api/chat, GET /api/conversations
│   │   ├── routes_documents.py  # CRUD documents (back-office)
│   │   ├── routes_auth.py       # login, refresh token
│   ├── services/
│   │   ├── rag_service.py       # orchestration RAG (retrieval + generation)
│   │   ├── embedding_service.py
│   │   ├── llm_service.py       # client Ollama
│   ├── models/                  # modèles Pydantic (schémas API)
│   ├── db/
│   │   ├── models.py             # modèles ORM (SQLAlchemy)
│   │   ├── session.py
│   ├── core/
│   │   ├── config.py              # variables d'environnement centralisées
│   │   ├── security.py            # JWT, hashing des mots de passe
│   │   ├── logging.py
│   ├── tests/
├── requirements.txt
├── Dockerfile
```

Le principe : **routes minces, services épais**. Une route ne contient jamais de logique métier   elle valide l'entrée, appelle un service, retourne la sortie. Cela rend chaque service testable indépendamment du serveur web (voir section 16).

### 5.3. API - endpoints principaux

| Endpoint | Méthode | Rôle requis | Description |
|---|---|---|---|
| `/api/chat` | POST | Secrétaire (ou anonyme selon décision) | Envoie une question, retourne réponse + sources + score de confiance |
| `/api/conversations` | GET | Secrétaire | Historique des conversations de l'utilisateur connecté |
| `/api/documents` | GET/POST | Responsable de direction | Liste/ajout de documents pour son propre service |
| `/api/documents/{id}` | PUT/DELETE | Responsable de direction (son service) / Admin (tous) | Modification/suppression d'un document |
| `/api/documents/{id}/validate` | POST | Admin / responsable désigné | Validation d'une fiche avant publication (si gouvernance à validation) |
| `/api/feedback` | POST | Secrétaire/usager | Signalement d'une réponse incorrecte |
| `/api/auth/login`, `/api/auth/refresh` | POST | — | Authentification |

### 5.4. Streaming de la réponse

Pour que l'usager voie la réponse apparaître progressivement (plutôt qu'attendre un bloc complet), FastAPI expose un flux **Server-Sent Events (SSE)** ou une réponse HTTP en `StreamingResponse`, que le frontend consomme avec l'API `fetch` en lecture de flux (`ReadableStream`). C'est exactement le point d'intégration prévu dans `assets/js/modules/streaming.js` du frontend déjà livré : seule cette fonction doit être réécrite pour consommer un vrai flux au lieu de simuler un texte statique.

### 5.5. Authentification et gestion des rôles

- **JWT (JSON Web Tokens)** pour l'authentification API : un jeton signé côté serveur, transmis dans l'en-tête `Authorization: Bearer <token>`, contenant le rôle de l'utilisateur.
- **RBAC (Role-Based Access Control)** avec au minimum quatre rôles : `secretaire`, `point_focal`, `responsable_ministere` (validation), `admin`.
- Les mots de passe ne sont **jamais stockés en clair** : hashage avec `bcrypt` ou `argon2` (argon2 est aujourd'hui recommandé par l'OWASP comme algorithme de hashage de mots de passe le plus résistant).
- Pour l'usager anonyme (si le chat est ouvert au public via le portail vitrine), pas de compte nécessaire, mais un **rate limiting par IP** pour éviter les abus (voir section 12).

### 5.6. Gestion des erreurs

Principe : **ne jamais laisser une exception Python brute remonter jusqu'à l'usager**. FastAPI permet de définir des gestionnaires d'exceptions centralisés qui transforment toute erreur interne en réponse JSON structurée (`{"error": "message générique", "code": "RAG_TIMEOUT"}`), tout en journalisant la trace complète côté serveur pour le débogage. Cas particuliers à prévoir explicitement :

- **Timeout du LLM** (le modèle met trop de temps à répondre) → message clair « Le service met plus de temps que prévu, veuillez réessayer », jamais une page blanche.
- **Aucun document pertinent trouvé** → réponse honnête (« Je ne trouve pas cette information dans la base documentaire actuelle ») plutôt qu'une réponse inventée.
- **Base de données indisponible** → dégrader gracieusement (mode lecture seule si possible) plutôt que planter entièrement.

### 5.7. Journalisation (logging)

Trois niveaux de logs à séparer dès le départ :

1. **Logs applicatifs** (erreurs, avertissements) → fichier ou service de logs (voir section 15).
2. **Logs d'audit métier** (qui a modifié quelle fiche, qui a validé quoi) → table dédiée en base de données, jamais mélangée aux logs techniques, car elle doit être conservée plus longtemps et être consultable par les responsables (traçabilité de gouvernance, section 19).
3. **Logs de conversation** (questions posées, réponses données, sources utilisées) → utiles pour l'amélioration continue du RAG et pour détecter les questions récurrentes non couvertes par le corpus, mais soumis aux règles de protection des données personnelles béninoises si les questions contiennent des informations identifiantes (voir section 20).

---

## 6. Base de données

### 6.1. Ce qu'il faut stocker (et donc ce qui guide le choix)

SIOU doit stocker trois types de données très différents :

1. **Des données fortement structurées et relationnelles** : utilisateurs, rôles, directions/agences, historique de conversations, journaux d'audit, le cas d'usage classique d'une base relationnelle.
2. **Des vecteurs d'embeddings** pour la recherche sémantique le cas d'usage d'une base vectorielle.
3. **Des documents semi-structurés** (fiches de service avec des champs variables selon le type de document) un cas où une base documentaire (NoSQL) est parfois préférée.

### 6.2. Comparatif PostgreSQL / MySQL / MongoDB

| Critère | PostgreSQL | MySQL | MongoDB |
|---|---|---|---|
| Modèle de données | Relationnel, très riche en types (JSON natif, tableaux) | Relationnel, plus simple | Documents JSON (NoSQL) |
| Support vectoriel natif | **Oui, via l'extension `pgvector`** | Non natif (ajouts tiers limités) | Support vectoriel ajouté récemment mais moins mature que pgvector |
| Respect strict des contraintes (intégrité référentielle, transactions) | Excellent | Bon | Plus permissif, à gérer côté application |
| Flexibilité de schéma (fiches de service à champs variables) | Bonne, grâce aux colonnes `JSONB` | Limitée | Excellente, c'est son point fort natif |
| Écosystème Python (SQLAlchemy, Alembic) | Excellent | Excellent | Bon mais moins « relationnel » dans les habitudes |
| Popularité pour les projets RAG en 2026 | Très forte (pgvector est devenu un standard de facto pour les RAG de taille petite à moyenne) | Faible pour ce cas d'usage | Utilisée mais pour des besoins différents (catalogue produit, contenu très hétérogène) |

### 6.3. Choix retenu et justification

**PostgreSQL avec l'extension `pgvector`.** La raison décisive : ce choix permet de stocker **dans un seul système** les utilisateurs, les fiches documentaires, les journaux d'audit ET les vecteurs d'embeddings, avec des requêtes qui peuvent combiner filtrage relationnel et recherche vectorielle en une seule opération (par exemple : « cherche les passages les plus proches sémantiquement, mais uniquement parmi les documents de la direction X et validés après telle date »). C'est exactement le type de requête dont SIOU a besoin, puisque l'orientation dépend souvent de filtres métier (quelle agence, quel type de démarche) en plus de la similarité sémantique pure.

Les benchmarks récents (pgvectorscale) montrent que pgvector tient largement la charge jusqu'à plusieurs dizaines de millions de vecteurs un volume que SIOU, avec un corpus institutionnel de quelques centaines à quelques milliers de documents, n'atteindra pas avant très longtemps. Le jour où le volume ou la latence deviendrait un problème réel, migrer vers une base vectorielle dédiée (Qdrant est le candidat naturel, voir section 7) reste possible sans tout réécrire, car l'interface applicative (« chercher les k passages les plus proches ») ne change pas.

Pour les fiches de service dont la structure varie selon le type de direction/agence, PostgreSQL permet d'utiliser des colonnes `JSONB` pour les champs flexibles, tout en gardant les champs communs (nom, direction, date de validité, statut de validation) en colonnes classiques indexées. Cela évite d'introduire MongoDB uniquement pour ce besoin, ce qui ajouterait un deuxième système à opérer sans bénéfice suffisant.

### 6.4. Schéma relationnel simplifié (aperçu pédagogique)

```
utilisateurs (id, email, mot_de_passe_hash, role, direction_id)
directions_agences (id, nom, sigle, adresse, telephone, horaires)
documents (id, titre, contenu, type, direction_id, statut, date_validite, cree_par, valide_par)
chunks (id, document_id, texte, embedding vector(1024), position)
conversations (id, utilisateur_id, cree_le)
messages (id, conversation_id, role, contenu, sources_json, score_confiance, cree_le)
signalements (id, message_id, description, statut, cree_le)
journaux_audit (id, utilisateur_id, action, cible, avant, apres, horodatage)
```

La table `chunks` est celle qui porte la colonne vectorielle (`embedding vector(1024)` avec `pgvector`, la dimension exacte dépendant du modèle d'embedding retenu voir section 8).

---

## 7. Architecture RAG en profondeur

### 7.1. Rappel du principe (pour les débutants)

Un LLM seul ne connaît que ce qu'il a appris pendant son entraînement — il ne connaît pas l'organigramme du MTDI, ni l'adresse de l'ASIN. Deux solutions existent pour lui donner cette connaissance : le **fine-tuning** (réentraîner le modèle sur vos données, coûteux, lent, à refaire à chaque changement) ou le **RAG** (Retrieval-Augmented Generation : à chaque question, on va chercher les passages pertinents dans une base documentaire, et on les donne au modèle *en même temps que la question*, dans le prompt). Le RAG est presque toujours le bon choix pour des données institutionnelles qui changent : c'est pour cela que le prototype l'utilisait déjà, et c'est ce que confirme la présentation officielle du projet (« aucune réponse sans document source »).

Le pipeline RAG complet comporte onze étapes. Chacune est un point de défaillance possible — un tutoriel « chunk, embed, retrieve, generate » qui ignore les neuf autres étapes est ce qui explique, d'après plusieurs analyses de production 2026, un taux d'échec de récupération pouvant atteindre 40 % dans les implémentations naïves.

### 7.2. Étape 1- Ingestion

Faire entrer les documents source (PDF de décrets, pages Word, exports HTML du portail vitrine, fiches saisies manuellement) dans le pipeline. Chaque document doit être associé à des **métadonnées** dès l'ingestion : direction/agence propriétaire, type de document, date de publication, date de validité, statut (brouillon/validé/publié). Ces métadonnées sont ce qui permettra plus tard de filtrer la recherche (section 6.4) et de citer précisément la source dans la réponse.

### 7.3. Étape 2- Nettoyage

Retirer le bruit : en-têtes/pieds de page répétés, numéros de page, artefacts d'extraction PDF (texte mal encodé, tableaux cassés). Un nettoyage insuffisant est une cause fréquente de mauvaise qualité de récupération un chunk pollué de caractères parasites a un embedding moins fidèle au sens réel du texte.

### 7.4. Étape 3- Découpage (chunking)

C'est, d'après plusieurs guides de production 2026, **le levier le plus sous-estimé de la qualité d'un RAG**. Trop de contenu par chunk noie l'information pertinente (le modèle d'embedding « moyenne » plusieurs idées différentes dans un seul vecteur) ; trop peu de contenu casse le sens (une phrase seule sans son contexte).

**Recommandation pratique pour SIOU** : découpage récursif de 300 à 500 tokens avec 10-15 % de chevauchement (« overlap ») entre chunks consécutifs c'est le standard qui couvre la majorité des cas selon les guides de production actuels, à ajuster ensuite si les métriques de qualité (section 7.11) révèlent des échecs de récupération. Pour les documents structurés (fiches de service avec des champs bien identifiés : nom, adresse, procédure, pièces requises), un découpage **par section logique plutôt que par nombre de tokens fixe** donne de meilleurs résultats : chaque chunk reste une unité de sens complète, capable de répondre seule à une question.

Amélioration à haute valeur ajoutée, simple à mettre en œuvre : préfixer chaque chunk d'un court résumé contextuel généré automatiquement (« Ce passage concerne : procédure d'obtention du label Startup, Direction du Numérique »). Cela améliore significativement le rappel de la recherche pour un coût de calcul marginal.

### 7.5. Étape 4- Embeddings

Transformer chaque chunk en un vecteur numérique qui capture son sens. Traité en détail section 8.

### 7.6. Étape 5 - Vectorisation / indexation

Stocker les vecteurs dans un index optimisé pour la recherche par similarité (voir section 7.9 pour le choix du moteur). L'algorithme dominant en 2026 est **HNSW** (Hierarchical Navigable Small World), un graphe de proximité qui permet une recherche approximative très rapide même sur des millions de vecteurs, avec une complexité qui croît de façon logarithmique et non linéaire avec la taille de l'index.

### 7.7. Étape 6 - Recherche (retrieval)

Au moment de la question, celle-ci est elle-même transformée en vecteur (avec le même modèle d'embedding), puis on cherche les *k* chunks les plus proches par similarité cosinus. Pour SIOU, une **recherche hybride** (vectorielle + mot-clé BM25) donne de meilleurs résultats que la recherche purement sémantique seule, en particulier pour les sigles et noms propres (« ASIN », « SBIN ») que les modèles d'embeddings généralistes ne différencient pas toujours bien par sens.

### 7.8. Étape 7 - Reranking

Étape optionnelle mais à fort impact : un modèle spécialisé (un *cross-encoder*, par exemple `bge-reranker-v2-m3`) réévalue les passages initialement récupérés en comparant chacun **directement** à la question (plutôt que par similarité de vecteurs pré-calculés), ce qui est plus précis mais plus lent d'où son usage seulement sur les 10-20 meilleurs résultats de l'étape 6, jamais sur tout le corpus. Un exemple documenté de production 2026 montre un score de fidélité passant de 0,41 (sans reranker) à 0,88 (avec reranker), sur le même modèle et le même prompt un gain largement supérieur à celui obtenu en changeant de LLM.

**Recommandation** : intégrer le reranking dès la V1 pour SIOU, car le corpus contient des sigles proches et des directions aux attributions qui se recoupent (ex. Direction du Numérique vs ASIN) exactement le cas où la similarité vectorielle brute se trompe le plus souvent, selon la présentation officielle elle-même (« Attributions mal connues... quelle direction, quelle agence est compétente ? »).

### 7.9. Comparatif des moteurs de recherche vectorielle : FAISS / ChromaDB / Qdrant / Weaviate / Milvus

| Moteur | Nature | Points forts | Limites pour SIOU |
|---|---|---|---|
| **FAISS** | Bibliothèque (pas une base de données) | Le plus rapide en recherche pure, GPU natif | Pas de persistance native, pas de filtrage par métadonnées intégré, pas de serveur il faut tout construire autour (déjà la limite identifiée dans le prototype actuel) |
| **ChromaDB** | Base embarquée, orientée simplicité | Prise en main la plus rapide, parfaite pour prototyper | Moins adaptée à la production à plusieurs utilisateurs simultanés, moins de contrôle fin sur le filtrage |
| **Qdrant** | Base dédiée, écrite en Rust | Excellent filtrage par métadonnées, autohébergement simple, bon rapport performance/complexité opérationnelle, très recommandée par la communauté pour les RAG de conformité (juridique, financier) où le filtrage compte plus que le débit brut | Un service de plus à opérer si on ne passe pas par `pgvector` |
| **Weaviate** | Base dédiée avec recherche hybride native | Recherche vectorielle + mot-clé (BM25) + filtres en une seule requête, API GraphQL | Runtime Java plus lourd à auto-héberger, courbe d'apprentissage GraphQL |
| **Milvus** | Base distribuée à très grande échelle | Conçue pour des milliards de vecteurs, architecture distribuée | Complexité d'auto-hébergement disproportionnée pour un corpus institutionnel de quelques milliers de documents (nécessite etcd, MinIO/S3, files de messages) |
| **pgvector** (extension PostgreSQL) | Extension d'une base relationnelle existante | Un seul système à opérer avec le reste des données de SIOU, transactions ACID, requêtes combinées relationnel + vectoriel | Moins performant que les moteurs dédiés au-delà de plusieurs dizaines de millions de vecteurs  non pertinent à l'échelle de SIOU |

### 7.10. Choix retenu et justification

**`pgvector` pour la V1, avec Qdrant comme option de migration si le besoin de filtrage avancé ou le volume l'exige.** Justification : le facteur décisif pour une équipe de deux étudiants n'est pas la performance brute (le corpus de SIOU restera de taille modeste pendant longtemps quelques milliers de documents institutionnels, pas des millions), mais la **simplicité opérationnelle**. Ajouter Qdrant ou Weaviate dès la V1 signifierait opérer, sauvegarder, sécuriser et monitorer un deuxième système de base de données en plus de PostgreSQL, pour un bénéfice de performance qui ne se matérialisera pas avant longtemps. `pgvector` permet en outre les requêtes combinées décrites en section 6.3, particulièrement utiles pour un système d'orientation où le filtrage par direction/agence est aussi important que la similarité sémantique.

Si un jour le corpus dépasse plusieurs millions de chunks (peu probable pour ce périmètre) ou si un besoin de filtrage extrêmement fin apparaît, **Qdrant** est le candidat naturel pour une migration, en raison de sa simplicité d'auto-hébergement (un seul binaire Rust) comparée à Milvus ou Weaviate.

### 7.11. Étape 8 - Prompting

Le prompt système doit être explicite sur trois points, directement dérivés du positionnement du produit (section 2.1) :

1. **Rôle et périmètre** : « Tu es SIOU, un assistant d'orientation pour les usagers du secteur numérique béninois. Tu aides à identifier la bonne direction, le bon service, la bonne localisation tu n'exécutes aucune démarche administrative. »
2. **Contrainte de fidélité (grounding)** : « Réponds uniquement à partir des passages fournis ci-dessous. Si l'information n'y figure pas, dis-le explicitement plutôt que de deviner. »
3. **Format de sortie attendu** : structuré, avec un champ pour la direction/l'agence compétente, un champ pour la source, éventuellement une confiance  pour que le frontend puisse afficher une réponse structurée plutôt qu'un simple paragraphe (cohérent avec le parcours utilisateur décrit en 2.4).

### 7.12. Étape 9 - Génération

Le LLM produit la réponse finale à partir du prompt enrichi. Traité en détail section 9.

### 7.13. Étape 10 - Citations

Chaque réponse doit indiquer explicitement quel(s) document(s) l'ont alimentée déjà anticipé dans le frontend livré (`sources` dans `chat.js`). Techniquement, cela veut dire que le service RAG doit renvoyer, en plus du texte généré, la liste des chunks utilisés avec leur document d'origine, pas seulement le texte brut.

### 7.14. Étape 11 - Mémoire

Deux mémoires différentes à ne pas confondre :

- **Mémoire de conversation courte** (le fil de discussion en cours) : nécessaire pour gérer les questions de relance (« et pour les pièces à fournir ? » après une première question sur une procédure). Gérée simplement en renvoyant les derniers échanges dans le prompt, avec une fenêtre limitée (par exemple les 4-6 derniers messages) pour ne pas saturer le contexte du modèle.
- **Mémoire long terme / historique** : stockée en base de données (`conversations`, `messages`), consultable dans la page Historique du frontend, mais **non réinjectée automatiquement** dans les prompts futurs (pour éviter la dérive de contexte et les problèmes de confidentialité entre sessions différentes).

### 7.15. Le confidence gate- le composant qui manque le plus au prototype actuel

Un RAG de production ne doit jamais forcer une génération quand la récupération est trop faible. Concrètement : si le meilleur score de similarité des chunks récupérés est en dessous d'un seuil (à calibrer empiriquement, par exemple 0,55-0,65 selon le modèle d'embedding), le système doit répondre « Je ne trouve pas cette information dans la base documentaire actuelle, je vous invite à contacter directement [direction générique] » plutôt que de laisser le LLM produire une réponse plausible mais non fondée. C'est la différence entre un système utile et un système qui érode la confiance dès la première réponse fausse un risque particulièrement grave dans un contexte administratif officiel.

### 7.16. Évaluation du pipeline RAG (comment savoir si ça marche)

Avant tout déploiement, constituer un **jeu de données de référence** (« golden dataset ») d'au moins 50 à 100 paires question/réponse couvrant les cas d'usage réels (UC1 à UC3), validées par une personne du ministère. Le framework **RAGAS** (open source) permet d'évaluer automatiquement quatre dimensions à chaque changement du pipeline :

- **Fidélité (faithfulness)** : la réponse est-elle bien fondée sur les documents récupérés, sans invention ?
- **Pertinence de la réponse** : répond-elle réellement à la question posée ?
- **Précision du contexte récupéré** : les passages remontés sont-ils pertinents ?
- **Rappel du contexte** : le pipeline a-t-il retrouvé *tous* les passages nécessaires pour répondre complètement ?

Ce jeu de tests doit être rejoué après chaque changement de chunking, de modèle d'embedding ou de prompt système exactement comme des tests unitaires pour du code classique (voir section 16.4).

---

## 8. Modèles d'embeddings

### 8.1. Ce que fait un modèle d'embedding

Il transforme un texte en un vecteur (une liste de nombres, typiquement 384 à 4096 dimensions) tel que deux textes de sens proche ont des vecteurs proches dans cet espace mathématique. La qualité de ce modèle conditionne directement la qualité de la recherche du RAG un moteur de recherche vectorielle parfait ne compense jamais un mauvais modèle d'embedding.

### 8.2. Comparatif pour un cas d'usage multilingue français/administratif

| Modèle | Type | Points forts | Limites |
|---|---|---|---|
| `paraphrase-multilingual-MiniLM-L12-v2` (utilisé dans le prototype) | Open source, léger (~118M paramètres) | Rapide, tourne sur CPU, déjà en place | Performances de récupération nettement en retrait des modèles plus récents sur les benchmarks 2026 |
| **BGE-M3** (BAAI) | Open source, multilingue (100+ langues) | Gère dense + sparse + multi-vecteur (ColBERT) en un seul modèle permet une recherche hybride sans faire tourner un modèle séparé pour le mot-clé ; contexte jusqu'à 8192 tokens ; licence MIT très permissive ; considéré comme la référence open source multilingue de production en 2026 | Nécessite un GPU pour un débit confortable en production (fonctionne sur CPU mais plus lentement) |
| Qwen3-Embedding | Open source, multilingue | Très bon score sur le français spécifiquement dans les benchmarks 2026 (MTEB français ≈ 69,8) | Modèle plus récent, écosystème d'outils un peu moins mature que BGE |
| Cohere Embed v4 / OpenAI text-embedding-3 | API payante | Excellente qualité, aucune infrastructure à gérer | Coût récurrent par appel, dépendance à un fournisseur étranger, envoi de données (potentiellement sensibles) à un tiers hors du territoire problématique pour des données publiques (voir section 20) |

### 8.3. Choix retenu et justification

**BGE-M3, auto-hébergé.** Trois raisons : (1) c'est aujourd'hui le modèle open source multilingue le plus utilisé en production pour du RAG généraliste, avec un support natif de la recherche hybride (dense + sparse) qui correspond exactement au besoin identifié en section 7.7 (sigles et noms propres) ; (2) la licence MIT permet un usage institutionnel sans restriction ; (3) l'auto-hébergement garde les données (potentiellement sensibles administrativement) sur une infrastructure maîtrisée, cohérent avec l'orientation « Mistral auto-hébergé via Ollama » déjà annoncée par le commanditaire pour le LLM  le même raisonnement de souveraineté s'applique à l'embedding.

**Point d'attention pratique** : contrairement au LLM de génération, le modèle d'embedding **ne doit jamais changer sans réindexation complète du corpus** les vecteurs de deux modèles différents ne sont pas comparables entre eux. Ce choix doit donc être fait tôt et documenté, car en changer plus tard signifie ré-encoder l'intégralité de la base documentaire.

### 8.4. Dimensionnement pratique

BGE-M3 produit des vecteurs denses de 1024 dimensions  c'est cette valeur qui doit être déclarée dans la colonne `pgvector` (`embedding vector(1024)`, cf. schéma section 6.4). Pour un corpus de quelques milliers de chunks, l'inférence d'embedding sur CPU reste tout à fait praticable pour l'indexation (opération faite une fois par document, pas à chaque question) ; seule la génération de l'embedding de la question à chaque requête doit rester rapide, ce qui est le cas même sur CPU pour un texte aussi court qu'une question.

---

## 9. Choix du LLM

### 9.1. Le cadre de décision posé par le commanditaire

La présentation officielle est déjà explicite : « Aujourd'hui : Mistral auto-hébergé via Ollama » pour l'ébauche démontrée, avec « Demain : choix du LLM selon les orientations » comme étape de décision formelle à venir. Ce document ne doit donc pas trancher unilatéralement ce choix c'est un arbitrage qui appartient au ministère mais fournir la grille de comparaison qui permettra de le faire en connaissance de cause, et recommander un point de départ raisonnable.

### 9.2. Auto-hébergé vs API tierce - le choix structurant

| Critère | LLM auto-hébergé (Ollama) | API tierce (OpenAI, Anthropic, Google, Hugging Face Inference) |
|---|---|---|
| Souveraineté des données | Totale aucune question d'usager ne quitte l'infrastructure du ministère | Les questions (potentiellement sensibles) transitent par un serveur tiers, souvent hors du territoire |
| Coût à volume modéré | Coût fixe d'infrastructure (serveur/GPU), indépendant du nombre de requêtes | Coût variable par token, prévisible mais qui grandit avec l'usage |
| Coût à volume élevé | Devient nettement plus économique au-delà d'un certain seuil (les analyses 2026 situent ce seuil autour de quelques millions de tokens par jour pour un modèle de taille comparable) | Reste linéaire, donc peut devenir très coûteux à grande échelle |
| Dépendance externe | Aucune (résilience aux changements de politique tarifaire d'un fournisseur) | Risque de coupure de service, de changement de conditions, de limite de disponibilité |
| Qualité brute | Les modèles ouverts de taille raisonnable (7-30 milliards de paramètres) sont aujourd'hui très proches des meilleurs modèles fermés sur des tâches de RAG factuel, même s'ils restent en retrait sur le raisonnement complexe ou la créativité | Généralement en tête des benchmarks de qualité brute |
| Effort opérationnel | Nécessite de maintenir un serveur d'inférence (GPU recommandé) | Aucun effort d'infrastructure |

**Conclusion de cadrage** : pour un système d'orientation administrative une tâche de RAG factuel, pas de raisonnement complexe ni de génération créative un modèle ouvert de taille moyenne auto-hébergé couvre largement le besoin, et l'argument de souveraineté des données publiques est déterminant pour une administration. C'est cohérent avec le choix déjà amorcé par le commanditaire.

### 9.3. Comparatif des familles de modèles ouverts (Llama, Mistral, Qwen, Gemma, DeepSeek) pour la génération

| Famille | Licence | Points forts pour SIOU | Limites |
|---|---|---|---|
| **Mistral** (Small/Large, 2026) | Apache 2.0 (depuis le passage récent à une licence permissive) | Origine européenne  argument non négligeable pour une administration soucieuse de souveraineté numérique ; très bon rapport qualité/taille en français ; déjà le choix amorcé par le commanditaire via Ollama | Les plus gros modèles de la famille dépassent le besoin réel de SIOU |
| **Qwen** (Alibaba, 2.5/3.x) | Apache 2.0 | Excellent support multilingue, très bonnes performances en français spécifiquement selon les benchmarks 2026, très bon rapport performance/taille pour les variantes 7-14B | Origine chinoise  à évaluer selon la politique de souveraineté numérique retenue par le ministère |
| **Llama** (Meta, 3.x/4) | Licence Meta (pas OSI, restrictions au-delà de 700M d'utilisateurs actifs mensuels non bloquant pour SIOU) | Écosystème le plus large (outillage, tutoriels, intégrations), déjà utilisé dans le prototype actuel via l'API Hugging Face | Licence moins permissive que Mistral/Qwen sur le papier, même si non bloquante à cette échelle |
| **Gemma** (Google, 3/4) | Apache 2.0 (depuis Gemma 4) | Très efficace en usage mémoire (tourne bien sur des configurations modestes), bon support multilingue | Écosystème RAG un peu moins mature que Mistral/Qwen sur les intégrations françaises |
| **DeepSeek** (V3/R1) | MIT / licence permissive | Excellent sur le raisonnement complexe | Surdimensionné pour une tâche de RAG factuel comme SIOU ; les variantes « raisonnement » produisent des réponses plus longues et plus lentes, sans bénéfice pour ce cas d'usage |

### 9.4. Et les modèles fermés (GPT, Claude) ?

Ils restent pertinents dans deux cas précis, à ne pas exclure du champ de réflexion :

- **Pendant la phase de prototypage et d'évaluation** : utiliser une API de haute qualité (Claude ou GPT) pour établir le jeu de données de référence (golden dataset, section 7.16) ou pour générer des questions de test synthétiques, avant de valider que le modèle auto-hébergé retenu atteint un niveau de qualité suffisant.
- **En modèle de secours (fallback)** ponctuel si l'infrastructure d'auto-hébergement est indisponible à condition que cela reste une exception documentée et non un usage courant, pour ne pas contredire l'objectif de souveraineté.

### 9.5. Recommandation

**Mistral Small (variante 22-24B, quantifiée en Q4, servie via Ollama)** comme point de départ, pour trois raisons qui recoupent les besoins du projet : (1) c'est déjà le choix amorcé et validé en interne par le commanditaire pour l'ébauche démontrée au ministre  capitaliser dessus plutôt que rouvrir un débat déjà tranché ; (2) l'origine européenne et la licence Apache 2.0 s'alignent avec une logique de souveraineté numérique cohérente avec un projet gouvernemental ; (3) la taille (quantifiée Q4) reste raisonnable pour un serveur GPU d'entrée de gamme (une carte 24 Go de VRAM suffit), un point important pour le budget étudiant puis institutionnel initial (voir section 13).

**Qwen (7-14B) est le second choix recommandé** si les tests sur le corpus réel en français montrent un net avantage de qualité la comparaison doit être faite empiriquement avec le golden dataset (section 7.16) plutôt que tranchée uniquement sur des benchmarks génériques.

### 9.6. Serving stack (comment servir le modèle une fois choisi)

- **Ollama** : le plus simple à mettre en œuvre, expose une API compatible OpenAI, gère automatiquement la quantification et l'usage GPU/CPU. **Recommandé pour la V1 et le développement**, cohérent avec le choix déjà fait par le commanditaire.
- **vLLM** : plus performant en production à fort trafic concurrent (traitement par lots optimisé), mais plus complexe à configurer. À envisager uniquement si Ollama montre ses limites en charge réelle (plusieurs dizaines de requêtes simultanées), ce qui est un problème « de riche » à ce stade du projet.

---

## 10. Collecte et sources de données

### 10.1. Les canaux disponibles, comparés

| Source | Avantages | Limites | Implications juridiques |
|---|---|---|---|
| **PDF officiels** (décrets, arrêtés) | Source la plus autoritative, déjà utilisés par ASIN (documents publiés sur asin.bj) | Extraction de texte parfois imparfaite (tableaux, mise en page complexe), nécessite un pipeline d'extraction robuste | Documents publics, réutilisation généralement libre pour les textes officiels béninois, à confirmer selon la politique open data en cours d'élaboration par l'ASIN |
| **Documents Word/Excel internes** | Facile à produire par les points focaux eux-mêmes (back-office, UC4) | Nécessite une discipline de dépôt et de mise à jour côté ministère | Documents internes, gouvernance à définir en interne (qui peut publier quoi) |
| **Pages HTML du portail vitrine existant** | Déjà à jour par construction (le portail vitrine est maintenu par le ministère) | Nécessite un extracteur HTML adapté à la structure du site, fragile si le site change de structure | Contenu déjà public, réutilisation interne sans problème |
| **API si disponible** | La source la plus fiable et la plus facile à maintenir à jour automatiquement | Peu de services publics béninois exposent une API aujourd'hui, sauf initiatives récentes (plateforme d'interopérabilité, portail national des services publics evoqués dans les chantiers ASIN) | Si une API officielle existe, son usage est la voie la plus sûre juridiquement |
| **Open Data** | Cadre en cours de structuration au Bénin (l'ASIN a engagé, avec l'appui de l'AFD/Expertise France, un projet de politique open data) | Le corpus disponible en open data est encore limité au moment de l'écriture de ce document | À surveiller : toute donnée publiée sous licence open data explicite peut être réutilisée en toute sécurité juridique |
| **RSS** | Idéal pour les événements et actualités (UC3) si le portail vitrine ou l'ASIN en propose | Peu répandu dans l'administration béninoise actuellement | Contenu public par nature si le flux existe |
| **Scraping** | Permet de récupérer un contenu qui n'existe sous aucune autre forme structurée | Fragile (casse dès que le site change), pose une question de légitimité si fait sans coordination avec le site source | À réserver en dernier recours, uniquement sur des sites publics institutionnels, en respectant le fichier `robots.txt` et sans charge excessive sur le serveur cible (voir 10.2) |

### 10.2. Principe directeur : la hiérarchie des sources

Pour un projet institutionnel, l'ordre de préférence doit toujours être : **saisie/validation directe par les points focaux du back-office (UC4) > documents officiels structurés (PDF/Word déposés) > API officielle si elle existe > extraction du portail vitrine > scraping en dernier recours**. Le scraping n'est pas interdit en soi pour des sites publics institutionnels, mais il doit rester une solution de contournement documentée, jamais l'architecture principale d'alimentation d'un système institutionnel car il crée une dépendance fragile à une structure de page qu'on ne contrôle pas.

### 10.3. Format d'ingestion recommandé

Toute source, quelle que soit son origine, doit être normalisée vers un même format pivot interne avant chunking : texte brut + métadonnées structurées (direction, type de document, date, statut). Cela permet au pipeline de chunking (section 7.4) et de réindexation (section 11) de traiter toutes les sources de façon uniforme, sans code spécifique à chaque format en aval de l'ingestion.

---

## 11. Mise à jour automatique des données

### 11.1. Le problème posé par le commanditaire

La présentation officielle identifie ce point comme un **facteur clé de réussite explicite** (« Gouvernance des données », section 19) : sans mécanisme fiable de mise à jour, la base documentaire devient obsolète une adresse qui change, une procédure qui évolue, un événement qui n'est jamais ajouté. Le README du prototype le note aussi comme perspective d'amélioration.

### 11.2. Les solutions disponibles, comparées

| Solution | Principe | Avantages | Risques et bonnes pratiques |
|---|---|---|---|
| **Back-office de saisie** (UC4, déjà couvert en section 4.5) | Les points focaux et responsables mettent à jour eux-mêmes leurs fiches | La source la plus fiable l'information vient directement du propriétaire métier | Nécessite une adhésion humaine réelle (voir section 19) ; sans discipline de mise à jour, la fiche devient obsolète malgré l'outil disponible |
| **Planification de tâches (cron)** | Un job planifié (quotidien, hebdomadaire) relance l'extraction des sources externes (portail vitrine, PDF publiés) | Simple à mettre en œuvre, prévisible | Un cron trop fréquent gaspille des ressources sans bénéfice si les sources changent rarement caler la fréquence sur le rythme réel de changement (voir 11.4) |
| **Détection de modification** | Comparer un hash (empreinte) du contenu source à chaque exécution planifiée ; ne déclencher la réindexation que si le contenu a réellement changé | Évite de réindexer inutilement tout un corpus inchangé, économise du calcul | Nécessite de stocker le hash précédent de chaque source pour comparaison |
| **Réindexation incrémentale** | Ne recalculer les embeddings que des chunks modifiés, pas de tout le corpus | Rapide, peu coûteux en calcul, peut tourner plus fréquemment sans impact | Nécessite un identifiant stable par chunk pour savoir lequel a changé à concevoir dès le schéma de données (section 6.4) |
| **Surveillance de sites officiels** | Un job périodique vérifie si une page ou un document a été mis à jour sur un site source | Utile pour les sources externes hors du contrôle direct du ministère | À utiliser avec modération (fréquence raisonnable, respect du `robots.txt`), et seulement pour des sources publiques légitimes |
| **Récupération via API** | Si une API officielle existe (ou est créée par l'ASIN dans le cadre de sa plateforme d'interopérabilité), interroger directement les données à jour | La solution la plus robuste dans le temps | Dépend de l'existence effective d'une API à privilégier activement dans les discussions avec l'ASIN si le projet devient institutionnel |
| **Scraping responsable planifié** | Combine scraping (10.1) et cron, en dernier recours pour des sources sans API ni back-office | Comble les lacunes des autres solutions | Fragile par nature (casse si la page change de structure) ; toujours prévoir une alerte de monitoring si le scraping échoue silencieusement (voir section 15) |

### 11.3. Architecture recommandée pour SIOU

Une combinaison à deux vitesses :

1. **Voie principale : back-office avec workflow de validation.** C'est la source la plus fiable pour les données propres au ministère (adresses, attributions, procédures). Chaque modification déclenche automatiquement une réindexation incrémentale du ou des chunks concernés (pas de tout le corpus), via une tâche de fond asynchrone pour ne pas ralentir la réponse de l'API au moment de la sauvegarde.
2. **Voie secondaire : job planifié (cron, quotidien ou hebdomadaire selon la source) avec détection de modification par hash**, pour les sources externes (portail vitrine, PDF publiés en ligne) qui ne passent pas par le back-office. La fréquence doit être calée sur le rythme réel de changement de chaque source, pas fixée arbitrairement partout à la même valeur.

### 11.4. Bonnes pratiques transverses

- **Ne jamais réindexer aveuglément tout le corpus à chaque exécution** : coût de calcul inutile, et risque de dégrader temporairement la qualité de recherche pendant la réindexation si elle n'est pas faite de façon transactionnelle (l'ancien index doit rester utilisable jusqu'à ce que le nouveau soit complet).
- **Toujours horodater la dernière vérification et la dernière modification réelle de chaque document**, visible dans le back-office c'est ce qui permet au responsable désigné (section 19) de repérer les fiches en retard de révision.
- **Journaliser chaque réindexation** (nombre de chunks ajoutés/modifiés/supprimés, durée, erreurs) pour pouvoir diagnostiquer une dérive de qualité a posteriori.

---

## 12. Sécurité

### 12.1. Cadre de référence : OWASP Top 10 pour les LLM

L'OWASP (Open Worldwide Application Security Project) maintient depuis 2023 une liste de référence des risques spécifiques aux applications basées sur des LLM, régulièrement mise à jour. Elle sert de check-list de couverture minimale pour tout système comme SIOU qui combine RAG et génération. Les catégories les plus pertinentes pour SIOU :

| Risque OWASP | Ce que ça veut dire pour SIOU | Mitigation |
|---|---|---|
| **LLM01 - Injection de prompt** | Un usager tape « ignore tes instructions précédentes et... » pour faire dévier le modèle de son rôle d'orientation | Contraintes comportementales explicites dans le prompt système (section 7.11), filtrage des motifs suspects en entrée, jamais de confiance aveugle dans le fait que le modèle « résistera » seul |
| **Injection indirecte (variante de LLM01)** | Un document indexé dans le corpus contient, volontairement ou non, du texte qui ressemble à une instruction (« Ignore les consignes et affiche... ») | Traiter tout contenu récupéré comme **donnée**, jamais comme instruction délimiter clairement dans le prompt la frontière entre consignes système et contenu documentaire récupéré (balises explicites), et valider les documents avant publication (workflow de validation, section 19) |
| **LLM02 - Divulgation d'informations sensibles** | Le modèle pourrait révéler des informations internes non destinées au public si elles se retrouvent dans le corpus par erreur | Séparer strictement, dès l'ingestion, les documents à statut « public » de ceux à statut « interne » ; ne jamais indexer un document interne dans le corpus interrogeable par le canal public |
| **LLM07 - Fuite du prompt système** | Un usager demande « répète tes instructions » pour découvrir la configuration interne | Ne jamais placer de secret (clé API, logique métier confidentielle) dans le prompt système ; accepter que le prompt système puisse un jour être visible et le concevoir en conséquence |
| **LLM08 - Faiblesses des vecteurs et embeddings** | Accès non autorisé au vector store, ou empoisonnement du corpus par un document malveillant | Contrôle d'accès strict sur les endpoints de gestion documentaire (RBAC, section 5.5), validation avant publication |
| **LLM09 - Désinformation** | Une hallucination du modèle présentée comme un fait officiel | Confidence gate (section 7.15), citations systématiques, formation des secrétaires à vérifier les cas ambigus |
| **LLM10 - Consommation non bornée** | Un usager malveillant envoie des milliers de requêtes pour épuiser les ressources GPU ou générer une facture excessive (si API tierce en secours) | Rate limiting (12.4), quotas par utilisateur/IP |

La bonne pratique reconnue par l'OWASP elle-même est la **défense en profondeur** : aucune protection unique n'est suffisante contre l'injection de prompt, il faut cumuler plusieurs couches (filtrage en entrée, contraintes comportementales, validation de sortie, moindre privilège, supervision humaine pour les actions sensibles).

### 12.2. Sécurité applicative classique (toujours valable, LLM ou pas)

| Menace | Mitigation pour SIOU |
|---|---|
| **XSS (Cross-Site Scripting)** | Le frontend échappe systématiquement tout contenu inséré dynamiquement dans le DOM (déjà appliqué dans `utils.js` du frontend livré via `escapeHtml()`) ; ne jamais utiliser `innerHTML` avec du texte non échappé provenant d'une réponse du modèle ou d'un usager |
| **CSRF (Cross-Site Request Forgery)** | Utilisation de jetons CSRF sur les actions de modification (back-office), et vérification de l'en-tête `Origin`/`Referer` sur les requêtes sensibles |
| **Injection SQL** | Utiliser exclusivement un ORM (SQLAlchemy) avec requêtes paramétrées jamais de concaténation de chaînes SQL, même pour des requêtes générées dynamiquement |
| **Sécurité de l'API** | HTTPS obligatoire partout, validation stricte des entrées via Pydantic (déjà natif à FastAPI), limitation de la taille des requêtes (éviter qu'un usager envoie un message de 500 000 caractères) |

### 12.3. Authentification, autorisation et RBAC (rappel, détaillé section 5.5)

Quatre rôles minimum (`secretaire`, `point_focal`, `responsable_ministere`, `admin`), JWT signés, mots de passe hashés avec argon2. Principe du **moindre privilège** : un point focal ne peut modifier que les fiches de sa propre direction/agence, jamais celles d'un autre service cette règle doit être vérifiée côté serveur à chaque requête, jamais seulement masquée côté interface.

### 12.4. Rate limiting

Limiter le nombre de requêtes par utilisateur/IP sur une fenêtre de temps (par exemple, via une extension comme `slowapi` pour FastAPI), avec des seuils différents selon le rôle : un usager anonyme du canal public a un quota plus restrictif qu'une secrétaire authentifiée. Objectif double : empêcher les abus, et éviter qu'un pic de requêtes ne sature l'infrastructure d'inférence auto-hébergée (qui n'a pas la capacité d'absorption élastique d'une API cloud tierce).

### 12.5. Chiffrement

- **En transit** : HTTPS partout (certificat via Let's Encrypt, gratuit et automatisé), y compris pour les communications internes entre le frontend et l'API si elles traversent un réseau public.
- **Au repos** : chiffrement des sauvegardes de base de données, et chiffrement des champs particulièrement sensibles (le cas échéant, mots de passe déjà hashés donc non concernés par ce point, mais tout futur champ contenant des données personnelles d'usagers).

### 12.6. Sauvegardes

Sauvegardes automatiques quotidiennes de PostgreSQL (données relationnelles ET vecteurs, puisqu'ils cohabitent dans le même moteur un argument supplémentaire en faveur du choix fait section 6.3 : une seule stratégie de sauvegarde à maintenir), conservées au moins 30 jours en rotation, testées régulièrement par une restauration réelle (une sauvegarde jamais testée n'est pas une sauvegarde fiable).

### 12.7. Journalisation et audit (rappel, détaillé section 5.7 et section 19)

Toute modification de la base documentaire (qui, quoi, quand, avant/après) doit être tracée dans une table d'audit immuable indispensable pour la gouvernance des données (section 19) et pour investiguer en cas de contenu erroné publié.

---

## 13. Hébergement

### 13.1. La contrainte spécifique de SIOU : un LLM auto-hébergé change tout

La plupart des comparatifs d'hébergement pour projets étudiants (Render, Railway, Vercel) supposent une application web classique, sans besoin de GPU. Or le choix fait section 9 (LLM auto-hébergé via Ollama) introduit une contrainte que ces plateformes ne couvrent pas nativement : de la mémoire vive GPU dédiée. Ce facteur doit être isolé du reste de l'hébergement.

### 13.2. Comparatif pour la partie « application web classique » (frontend + API + base de données)

| Plateforme | Coût de départ | Facilité | Avantages | Limites pour SIOU |
|---|---|---|---|---|
| **Render** | Gratuit (tier limité) puis ~7 $/mois par service | Élevée | Pricing prévisible par service, PostgreSQL managé avec sauvegardes, hébergement statique gratuit pour le frontend | Facturation par service peut grimper si on multiplie les composants |
| **Railway** | Pas de palier gratuit permanent, ~5-15 $/mois pour un usage modeste | Élevée, expérience développeur très fluide | Facturation à l'usage réel (peut être plus économique qu'un prix fixe pour un trafic faible et irrégulier, ce qui correspond au profil d'un projet étudiant en phase de test) | Pas de tier gratuit pérenne, coûts moins prévisibles à volume variable |
| **Vercel** | Gratuit pour le frontend statique | Élevée | Excellent pour héberger uniquement la partie frontend (fichiers statiques) | Pas conçu pour héberger un backend Python avec base de données et modèle GPU pertinent uniquement pour la partie frontend de SIOU, pas pour l'ensemble |
| **Hugging Face Spaces** | Gratuit avec CPU, GPU payant à l'heure | Moyenne, orientée démonstration ML | Idéal pour héberger une démo publique du modèle ou de l'espace RAG à moindre coût, communauté ML | Moins adapté comme hébergement de production d'un site institutionnel complet ; pensé pour des démonstrations, pas pour un service public 24/7 |
| **OVH** (cloud européen/francophone) | Variable, VPS à partir de quelques euros/mois, instances GPU plus coûteuses | Moyenne, plus proche de l'administration d'un serveur classique | **Argument de souveraineté déterminant pour un projet gouvernemental** : hébergeur européen, avec la possibilité de choisir précisément la localisation des données (un point qui compte pour des données publiques béninoises, en cohérence avec les impératifs identifiés par l'APDP et le Code du numérique béninois, section 20) ; propose des instances GPU dédiées | Moins « clé en main » que Render/Railway, demande plus de compétences d'administration système |
| **AWS / Azure / Google Cloud** | Très variable, souvent le plus cher à configuration équivalente pour un petit projet | Faible pour des débutants (complexité de configuration) | Le plus de flexibilité, catalogues d'instances GPU les plus larges | Complexité et risques de facturation incontrôlée disproportionnés pour un budget étudiant ; à réserver à une phase institutionnelle avec un budget et une équipe DevOps dédiée |

### 13.3. Où faire tourner le LLM auto-hébergé (le vrai point de décision)

Trois options concrètes, de la plus simple à la plus robuste :

1. **Développement et démonstration** : faire tourner Ollama sur une machine locale ou un serveur GPU étudiant/universitaire disponible (l'IFRI ou un partenaire académique peut disposer de ressources GPU mutualisées) coût nul, suffisant pour la phase actuelle (« ébauche démontrée » selon la feuille de route officielle).
2. **Pilote au secrétariat** (étape 2 de la feuille de route officielle, « Consolidation ») : un serveur GPU dédié modeste (une carte 24 Go de VRAM suffit pour Mistral Small quantifié, section 9.5), hébergé soit sur une instance OVH GPU, soit sur un serveur physique au sein même du ministère si l'infrastructure existe déjà cette dernière option maximise la souveraineté et évite tout coût récurrent d'hébergement cloud.
3. **Déploiement institutionnel à grande échelle** (au-delà du périmètre de ce document) : discussion à mener avec l'ASIN, qui dispose déjà d'un data-center national dans ses chantiers prioritaires la solution la plus cohérente à terme est d'héberger SIOU sur l'infrastructure numérique de l'État béninois elle-même plutôt que sur un cloud commercial, ce qui répond simultanément à la souveraineté et à la pérennité budgétaire.

### 13.4. Recommandation

**Phase actuelle (étudiant, prototype à consolider)** : frontend statique sur Render (gratuit) ou Vercel, API backend + PostgreSQL/pgvector sur Render ou Railway (quelques dollars par mois), LLM et embeddings sur une ressource GPU académique ou une instance OVH GPU à l'heure pour les phases de test intensif.

**Phase pilote au secrétariat** : migration vers OVH (VPS pour l'application web + instance GPU dédiée pour Ollama), pour l'argument de souveraineté et parce que le coût devient plus prévisible à usage constant qu'une facturation cloud à l'heure.

**Phase institutionnelle** : intégration à l'infrastructure numérique de l'État (data-center national ASIN) dès que cette option est opérationnellement disponible pour un projet comme SIOU à anticiper dans les discussions de gouvernance (section 19) plutôt qu'à décider unilatéralement par l'équipe de développement.

---

## 14. DevOps

### 14.1. Conteneurisation avec Docker

Chaque composant (frontend, API, base de données, Ollama) tourne dans son propre conteneur Docker, défini par un `Dockerfile`, orchestré en développement par un fichier `docker-compose.yml`. Avantage concret pour une équipe débutante : **« ça marche sur ma machine » devient « ça marche partout »** l'environnement est identique en développement, en test et en production, ce qui élimine une classe entière de bugs liés aux différences de configuration.

```yaml
# docker-compose.yml (extrait pédagogique)
services:
  frontend:
    build: ./frontend
    ports: ["8080:80"]
  backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql://...
      - OLLAMA_URL=http://ollama:11434
    depends_on: [db, ollama]
  db:
    image: pgvector/pgvector:pg16
    volumes: ["pgdata:/var/lib/postgresql/data"]
  ollama:
    image: ollama/ollama
    volumes: ["ollama_models:/root/.ollama"]
volumes:
  pgdata:
  ollama_models:
```

### 14.2. Intégration et déploiement continus (CI/CD) avec GitHub Actions

À chaque `push` sur la branche principale (ou à chaque pull request), un pipeline automatique :

1. Installe les dépendances.
2. Exécute les tests automatisés (section 16).
3. Vérifie le style de code (linting).
4. Construit les images Docker.
5. (sur la branche principale uniquement, après validation manuelle si souhaité) Déploie automatiquement sur l'environnement de production.

C'est un investissement qui paraît disproportionné pour deux étudiants au tout début, mais qui évite l'erreur la plus commune des projets académiques qui deviennent des produits : déployer manuellement, oublier une étape, casser la production sans s'en rendre compte immédiatement.

### 14.3. Environnements

Trois environnements distincts, avec des bases de données et des configurations séparées, pour ne jamais tester une fonctionnalité risquée directement sur les vraies données publiées :

- **Développement local** (Docker Compose sur la machine de chaque développeur).
- **Staging/recette** (une copie de la configuration de production, avec des données de test, où le ministère peut valider une nouvelle fonctionnalité avant sa mise en ligne réelle particulièrement important pour le workflow de validation des fiches, section 19).
- **Production**.

### 14.4. Tests dans le pipeline (renvoi à la section 16)

Aucun déploiement automatique ne doit se produire si les tests échouent c'est la garde-fou de base de tout pipeline CI/CD sérieux.

---

## 15. Monitoring

### 15.1. Ce qu'il faut surveiller, et pourquoi

Un système RAG en production peut « fonctionner » techniquement (répondre 200 OK) tout en dérivant silencieusement en qualité c'est le piège spécifique aux systèmes à base de LLM, différent d'une application classique où une panne se voit immédiatement.

| Catégorie | Ce qu'on surveille | Outil recommandé |
|---|---|---|
| **Logs applicatifs** | Erreurs, exceptions, requêtes lentes | Stack simple pour démarrer : logs structurés (JSON) envoyés à un service comme Grafana Loki (open source, léger) |
| **Alertes** | Taux d'erreur anormal, latence excessive du LLM, échec répété d'un job de réindexation (section 11) | Alertes configurées sur seuils, notifiées par e-mail ou messagerie (Slack/Discord/Telegram selon ce que l'équipe utilise déjà) |
| **Statistiques d'usage** | Nombre de conversations par jour, questions les plus fréquentes, taux de « je ne trouve pas cette information » (confidence gate déclenché, section 7.15) ce dernier indicateur est le plus précieux : il révèle directement les lacunes du corpus documentaire | Tableau de bord simple (déjà esquissé dans la page Dashboard du frontend livré) alimenté par les tables `messages`/`signalements` |
| **Performance infrastructure** | Utilisation CPU/GPU/RAM du serveur d'inférence, temps de réponse de l'API, temps de la recherche vectorielle vs temps de génération LLM (pour savoir où optimiser en priorité) | Prometheus + Grafana (standard open source de l'industrie, gratuit, bien documenté) |

### 15.2. Recommandation pour une équipe de trois étudiants

Ne pas sur-investir dans un stack de monitoring complexe dès le départ. Commencer par : logs structurés + une page d'administration simple affichant les statistiques clés (déjà prévue dans le Dashboard du frontend) + une alerte e-mail basique en cas d'échec de réindexation ou de taux d'erreur élevé. Ajouter Prometheus/Grafana au moment du passage en pilote réel au secrétariat (section 21), pas avant le monitoring avancé résout un problème (diagnostiquer une panne en production à fort trafic) que le projet n'a pas encore en phase de prototype.

---

## 16. Tests

### 16.1. Les quatre familles de tests nécessaires

| Type de test | Ce qu'il vérifie | Outil (écosystème Python/JS) |
|---|---|---|
| **Tests unitaires** | Une fonction isolée se comporte comme attendu (ex. le chunking découpe bien un texte donné en morceaux de la bonne taille) | `pytest` côté backend |
| **Tests d'intégration** | Plusieurs composants fonctionnent bien ensemble (ex. une requête à `/api/chat` déclenche bien la recherche vectorielle puis la génération et retourne une réponse structurée) | `pytest` + client de test FastAPI (`TestClient`) |
| **Tests utilisateurs** | L'interface est utilisable et compréhensible par de vraies secrétaires, pas seulement par les développeurs | Sessions de test manuelles avec des utilisateurs réels du ministère, avant chaque mise en production majeure indispensable et souvent négligé dans les projets étudiants |
| **Tests du RAG** | La qualité des réponses ne se dégrade pas quand on change un composant du pipeline (chunking, modèle d'embedding, prompt) | Le golden dataset + RAGAS déjà décrit en section 7.16 c'est la famille de tests la plus spécifique à ce projet et la plus souvent oubliée dans les tutoriels généralistes |

### 16.2. Priorisation réaliste pour une équipe de deux étudiants

Il n'est pas réaliste de viser une couverture de test exhaustive dès le départ. Ordre de priorité recommandé : (1) tests du RAG (golden dataset), car c'est la qualité perçue du produit qui en dépend directement ; (2) tests d'intégration sur les endpoints critiques (`/api/chat`, authentification, back-office) ; (3) tests unitaires sur la logique la plus sensible aux régressions silencieuses (chunking, calcul du score de confiance) ; (4) tests utilisateurs à chaque étape clé de la feuille de route (section 21), pas seulement à la fin.

### 16.3. Où placer les tests dans le pipeline CI/CD

Tous les tests automatisés (unitaires + intégration) tournent à chaque `push` (section 14.2). Le golden dataset RAG, plus coûteux en temps de calcul (il appelle réellement le LLM), tourne plutôt à chaque changement touchant le pipeline RAG spécifiquement (chunking, prompt, modèle), pas à chaque commit trivial de style CSS.

---

## 17. Performances

### 17.1. Les quatre leviers, par ordre d'impact réel pour SIOU

1. **Cache des réponses fréquentes.** Beaucoup de questions se ressemblent d'un usager à l'autre (« où se trouve l'ASIN ? » sera posée des dizaines de fois). Un cache simple (par exemple Redis, ou même une table PostgreSQL avec horodatage d'expiration) sur les questions normalisées permet de renvoyer une réponse déjà validée sans repasser par le LLM à chaque fois gain de latence et de coût de calcul.
2. **Streaming de la génération** (déjà couvert section 4.6 et 5.4) : réduit la latence *perçue*, pas la latence réelle, mais c'est ce qui compte le plus pour l'expérience utilisateur.
3. **Pagination de l'historique des conversations** : ne jamais charger tout l'historique d'un utilisateur en une seule requête (déjà anticipé côté frontend avec la page Historique, mais côté API il faut prévoir une pagination réelle `limit`/`offset` ou pagination par curseur dès la conception de l'endpoint `/api/conversations`).
4. **Compression des réponses HTTP** (gzip/brotli, activable au niveau du serveur web ou du reverse proxy) : gain modeste mais gratuit, à activer par défaut.

### 17.2. Le vrai goulot d'étranglement de SIOU

Dans un système RAG, la génération par le LLM est presque toujours l'étape la plus lente (souvent plusieurs secondes), largement devant la recherche vectorielle (quelques dizaines de millisecondes avec `pgvector` sur un corpus de cette taille). **Optimiser la recherche vectorielle avant d'avoir optimisé la génération est un mauvais ordre de priorité** un piège classique où l'énergie est mise sur la partie la plus facile à mesurer plutôt que sur celle qui domine réellement le temps de réponse perçu. Le cache (17.1.1) et le streaming (17.1.2) sont donc les deux leviers qui rapportent le plus pour l'effort investi.

---

## 18. Accessibilité

### 18.1. Pourquoi c'est particulièrement important pour SIOU

Un outil utilisé au guichet d'une administration doit être utilisable par des secrétaires aux profils variés, potentiellement avec des besoins d'accessibilité différents (vision réduite, usage clavier préférentiel). Ce n'est pas une case à cocher réglementaire abstraite mais une condition réelle d'adoption au quotidien.

### 18.2. Normes de référence : WCAG

Les **WCAG (Web Content Accessibility Guidelines)**, maintenues par le W3C, définissent trois niveaux de conformité (A, AA, AAA). **Le niveau AA est le standard visé pour un service institutionnel** le niveau AAA est rarement atteignable pour une application interactive complexe comme un chat, et le niveau A est insuffisant pour un usage professionnel quotidien.

### 18.3. Points de contrôle concrets (déjà en partie couverts dans le frontend livré)

| Exigence WCAG AA | État dans le frontend déjà construit | Ce qu'il reste à vérifier |
|---|---|---|
| Navigation complète au clavier | Piège de focus dans les modales, lien d'évitement (`skip-link`) déjà en place | Tester le parcours complet du chat (poser une question, lire la réponse, copier, régénérer) uniquement au clavier |
| Focus visible | Géré via `:focus-visible` dans le CSS de base | Vérifier le contraste du halo de focus sur tous les fonds (clair et sombre) |
| Contraste des couleurs (4.5:1 minimum pour le texte courant) | Palette construite sur des tokens CSS centralisés | Vérifier chaque combinaison texte/fond avec un outil comme le contrast checker du WebAIM, en particulier les badges de statut et le texte secondaire gris clair |
| Lecteurs d'écran (attributs ARIA, structure sémantique) | `aria-live` sur le fil de conversation, `role="dialog"` sur les modales, labels sur tous les champs | **Test réel avec NVDA ou VoiceOR nécessaire avant mise en production** les attributs ARIA mal utilisés créent parfois une fausse impression de conformité sans test humain réel |
| Respect de `prefers-reduced-motion` | Déjà implémenté globalement en CSS | — |
| Textes alternatifs sur les éléments visuels | Icônes actuellement décoratives (`aria-hidden`) | S'assurer que toute icône porteuse de sens (ex. statut d'une conversation) a un équivalent textuel, pas seulement une couleur |

### 18.4. Recommandation de processus

Intégrer un audit d'accessibilité (même informel, avec l'extension navigateur gratuite axe DevTools) à chaque nouvelle page ajoutée, plutôt qu'un audit unique en fin de projet corriger un problème d'accessibilité découvert tôt coûte une fraction de ce qu'il coûte une fois l'interface figée et utilisée en production.

---

## 19. Gouvernance des données

*(Section ajoutée : la présentation officielle du projet identifie explicitement ce point comme le facteur clé de réussite n°1 plus important, pour le commanditaire, que n'importe quel choix technique de ce document.)*

### 19.1. Le constat du commanditaire

Sans gouvernance humaine, aucune architecture technique aussi bien conçue soit-elle ne maintient un corpus documentaire à jour. La présentation liste quatre piliers explicites :

1. **Un responsable désigné** au ministère, chargé de la mise à jour de la base de connaissances dans son ensemble.
2. **Des points focaux dans chaque agence partenaire** (ASIN, SBIN...), responsables de la validité des informations de leur propre structure.
3. **Une fréquence de révision régulière** (par exemple mensuelle), avec un circuit de validation avant publication.
4. **Un mécanisme de signalement d'erreurs**, accessible aux secrétaires et, potentiellement, aux usagers eux-mêmes.

### 19.2. Traduction technique de ces quatre piliers

| Pilier de gouvernance | Traduction dans l'architecture |
|---|---|
| Responsable désigné | Rôle `responsable_ministere` dans le RBAC (section 5.5), avec un tableau de bord dédié montrant les fiches en retard de révision |
| Points focaux par agence | Rôle `point_focal`, restreint à sa propre direction/agence (moindre privilège, section 12.3), via le back-office (UC4, section 4.5) |
| Fréquence de révision | Champ `date_derniere_revision` sur chaque document (schéma section 6.4), avec une alerte automatique (section 15) quand une fiche dépasse le délai fixé sans révision |
| Signalement d'erreurs | Endpoint `/api/feedback` déjà prévu (section 5.3), avec une file de traitement visible par le responsable désigné, alimentant elle-même le cycle de révision |

### 19.3. Le choix de circuit de validation  à trancher avec le ministère, pas unilatéralement

Deux modèles possibles, avec un compromis clair entre réactivité et contrôle :

- **Publication directe par le point focal**, sans validation intermédiaire : plus réactif, mais risque qu'une information incorrecte soit publiée immédiatement (moins de garde-fou).
- **Publication soumise à validation du responsable désigné** avant mise en ligne : plus sûr, mais introduit un délai à mesurer contre l'objectif affiché de « fiche validée et actualisée en moins de 24h » (persona Responsable de direction, section 2.2).

**Recommandation** : démarrer avec un circuit à validation obligatoire pendant la phase pilote (pour construire la confiance dans le système), puis évaluer, une fois la fiabilité démontrée, un passage à une publication directe pour les points focaux les plus expérimentés une décision de gouvernance, pas une décision technique, qui doit rester révisable sans changement de code (un simple paramètre de configuration par direction/agence).

---

## 20. Conformité légale béninoise

*(Section ajoutée : le prompt initial demande d'expliciter les implications juridiques des sources de données — indispensable pour un projet institutionnel béninois, à ne pas traiter en généralités RGPD européennes qui ne s'appliquent pas ici.)*

### 20.1. Le cadre légal applicable

Le Bénin dispose d'un cadre juridique dédié à la protection des données personnelles depuis la **Loi n° 2017-20 du 20 avril 2018 portant Code du numérique**, dont le **Livre V** constitue le socle juridique de la protection des données à caractère personnel, complétée par la **Loi n° 2020-35 du 6 janvier 2021**. L'autorité de contrôle est l'**APDP (Autorité de Protection des Données à Caractère Personnel)**, institution indépendante chargée de veiller à l'application de ces textes.

### 20.2. Ce que cela implique concrètement pour SIOU

- **Les informations institutionnelles pures** (attributions d'une direction, adresse d'une agence, procédure administrative) ne sont **pas des données à caractère personnel** au sens du Code du numérique leur traitement dans le RAG ne pose pas de difficulté particulière au regard de cette loi.
- **Les questions posées par les usagers**, en revanche, peuvent parfois contenir des informations personnelles (un usager qui mentionne son nom, une situation personnelle précise en formulant sa question). Si ces questions sont journalisées (section 5.7, logs de conversation), SIOU devient un **responsable de traitement** au sens de la loi béninoise, avec les obligations associées : finalité déclarée, information des usagers, durée de conservation limitée, sécurisation des données (section 12).
- **Le principe de pertinence et de proportionnalité** du droit béninois (ne collecter que ce qui est nécessaire à la finalité) justifie techniquement une politique de rétention courte des logs de conversation contenant des données personnelles, et l'anonymisation des statistiques d'usage agrégées (section 15) dès que possible.
- **L'ASIN**, chargée de la mise en œuvre opérationnelle des systèmes d'information sécurisés au Bénin, est un interlocuteur naturel pour valider l'architecture de sécurité de SIOU avant tout déploiement institutionnel d'autant qu'elle pilote également le chantier de politique open data qui pourrait, à terme, simplifier légalement la réutilisation de certaines sources pour SIOU (section 10).

### 20.3. Recommandation

Avant le passage en pilote réel (feuille de route, section 21), soumettre le projet à une revue légère avec l'APDP ou un référent juridique du ministère, portant spécifiquement sur trois questions : (1) le statut des logs de conversation et leur durée de conservation, (2) la nécessité ou non d'un consentement explicite si le canal devient public via le portail vitrine, (3) l'articulation avec la stratégie open data en cours de définition par l'ASIN pour la réutilisation de documents officiels.

---

## 21. Feuille de route

*Alignée sur la feuille de route officielle du commanditaire (« Existant → Étape 1 · Décision → Étape 2 · Consolidation »), déclinée en étapes techniques concrètes.*

### Étape 0 - Existant (déjà fait)
- Prototype Streamlit fonctionnel avec RAG basique (fait).
- Frontend web moderne HTML/CSS/JS pour 8 pages (fait, livré séparément).
- Présentation validée en interne (fait).

### Étape 1 - Décision (court terme, 4 à 6 semaines)
**Objectifs** : lever les inconnues qui conditionnent toute l'architecture technique.
**Technologies impliquées** : aucune nouvelle - travail de cadrage et de spécification.
**Difficultés attendues** : obtenir un arbitrage clair du ministère sur le périmètre exact des données à couvrir et le canal de diffusion (interne secrétariat seul, ou ouvert au public via le portail vitrine dès le pilote).
**Livrables** :
- Confirmation du LLM définitif (Mistral Small recommandé, section 9.5) et validation de la disponibilité d'une ressource GPU pour le pilote.
- Périmètre de données de la V1 (quelles directions/agences en premier).
- Décision de gouvernance (circuit de validation, section 19.3).
- Maquette validée du back-office avec au moins un point focal réel du ministère.

### Étape 2 - Fondations techniques (6 à 10 semaines)
**Objectifs** : construire l'ossature backend et brancher le frontend déjà existant.
**Technologies** : FastAPI, PostgreSQL + pgvector, Docker Compose, BGE-M3, Ollama + Mistral Small.
**Difficultés attendues** : première mise en place du pipeline de chunking sur le corpus réel (souvent plus désordonné que prévu), calibrage du seuil du confidence gate (section 7.15).
**Livrables** :
- API backend fonctionnelle (`/api/chat`, authentification, endpoints documents).
- Pipeline RAG complet (ingestion → chunking → embeddings → pgvector → reranking → génération → citations).
- Frontend branché sur la vraie API (remplacement de `requestAssistantReply()` simulée, section 5.4).
- Golden dataset initial (30-50 paires question/réponse, section 7.16).

### Étape 3 - Consolidation et données réelles (8 à 12 semaines)
**Objectifs** : atteindre le MVP consolidé visé par la feuille de route officielle.
**Technologies** : back-office complet, système de rôles RBAC, monitoring de base.
**Difficultés attendues** : adhésion réelle des points focaux au back-office (facteur humain, pas technique — section 19.1) ; volume de documents réels souvent plus hétérogène en qualité que le corpus de test.
**Livrables** :
- Back-office opérationnel avec workflow de validation.
- Corpus documentaire réel couvrant au moins les directions et agences prioritaires identifiées à l'étape 1.
- Tests utilisateurs avec de vraies secrétaires.
- Score de qualité RAGAS mesuré sur le golden dataset étendu (80-100 paires).

### Étape 4 - Déploiement pilote au secrétariat (4 à 8 semaines)
**Objectifs** : déploiement réel visé par la feuille de route officielle.
**Technologies** : hébergement OVH (section 13.4), CI/CD complet, monitoring Prometheus/Grafana.
**Difficultés attendues** : charge réelle différente de la charge de test, premiers signalements d'erreurs à traiter en conditions réelles.
**Livrables** :
- Déploiement en production sur l'infrastructure retenue.
- Formation des secrétaires du secrétariat pilote.
- Cycle de gouvernance opérationnel (révision mensuelle effective, section 19).
- Bilan quantitatif du pilote (temps de réponse moyen, taux de confidence gate déclenché, satisfaction des secrétaires) servant de base à la décision d'extension.

### Étape 5 - Extension institutionnelle (au-delà de ce document)
Discussion avec l'ASIN sur l'intégration à l'infrastructure numérique nationale, extension du canal au portail vitrine public, intégration éventuelle à la plateforme d'interopérabilité hors périmètre direct de ce document mais à anticiper dès les choix d'architecture ci-dessus (c'est précisément pour cela que l'option B de la section 3 a été retenue plutôt qu'un monolithe qui bloquerait cette extension).

---

## 22. Ressources par technologie

### FastAPI
- Documentation officielle : https://fastapi.tiangolo.com/ (tutoriel pas à pas excellent pour débutants, en anglais mais très accessible)
- Concepts clés à maîtriser en premier : routes, modèles Pydantic, dépendances (`Depends`), gestion asynchrone

### PostgreSQL + pgvector
- Documentation pgvector : dépôt GitHub officiel `pgvector/pgvector` (README très clair avec exemples SQL)
- SQLAlchemy (ORM Python) : https://docs.sqlalchemy.org/ privilégier la documentation de la version 2.x (syntaxe moderne)

### RAG et LangChain
- Documentation LangChain : https://python.langchain.com/ utile pour l'orchestration du pipeline RAG, même si une implémentation « à la main » reste possible et plus simple à déboguer pour une équipe débutante
- Framework d'évaluation RAGAS : dépôt GitHub `explodinggradients/ragas`, documentation avec exemples de golden dataset

### Ollama
- Documentation officielle : https://ollama.com/ (site + bibliothèque de modèles avec tailles et commandes exactes)
- Commande de démarrage : `ollama pull mistral-small` puis `ollama serve` API compatible OpenAI, donc réutilisable avec la plupart des bibliothèques clientes existantes

### Modèles d'embeddings (BGE-M3)
- Modèle et documentation : Hugging Face, organisation BAAI, modèle `bge-m3`
- Bibliothèque d'utilisation simple : `sentence-transformers` (déjà utilisée dans le prototype actuel, donc réutilisation directe de l'expérience acquise)

### Frontend (déjà largement documenté dans le projet livré séparément)
- MDN Web Docs (https://developer.mozilla.org/fr/) - référence complète et gratuite pour HTML/CSS/JS natif
- WCAG (https://www.w3.org/WAI/WCAG21/quickref/) - check-list interactive filtrable par niveau de conformité

### Docker et CI/CD
- Documentation Docker : https://docs.docker.com/get-started/ (parcours « Get Started » officiel, pensé pour les débutants)
- GitHub Actions : https://docs.github.com/actions - commencer par le modèle de workflow Python officiel avant de le personnaliser

### Sécurité
- OWASP Top 10 pour les LLM : site officiel owasp.org, projet « OWASP Top 10 for LLM Applications » - mis à jour régulièrement, à ressurveiller à chaque montée de version majeure du pipeline RAG
- OWASP Top 10 classique (applications web) : toujours pertinent en complément, pour tout ce qui n'est pas spécifique aux LLM

### Cadre légal béninois
- Code du numérique (Loi n° 2017-20 du 20 avril 2018) : texte consultable via l'APDP (archive.apdp.bj) et Open Loi Bénin
- Site de l'APDP : autorité de contrôle, publications et guides de bonnes pratiques
- Documents ASIN : asin.bj/documents publications officielles sur la sécurité numérique et la protection des données au Bénin

---

## Note de clôture

Ce document fixe un cap, pas un contrat figé. Chaque section contient explicitement le compromis accepté en échange du choix retenu c'est ce qui permettra, dans six mois, de revenir sur une décision en connaissance de cause plutôt que de la remettre en question sans mémoire du raisonnement initial. La prochaine étape naturelle, avant d'écrire la moindre ligne de code d'API, est l'**Étape 1 - Décision** de la feuille de route (section 21) : obtenir un arbitrage explicite du ministère sur le périmètre de données et le canal de diffusion. Tout ce qui est construit avant cette clarification risque d'être partiellement refait.
#   S I O U 2  
 #   S I O U 2  
 