# Rapport d'avancement - SIOU

**Système Intelligent d'Orientation des Usagers** - MTDI, République du Bénin
**Date :** 19 juillet 2026 · **Branche :** `androu_branch`

> Ce rapport fait l'état des lieux de l'intégration frontend ↔ backend, de la
> mise en service de la vraie base de données, et du **branchement du pipeline
> RAG/LLM**. Il distingue ce qui est **fait et vérifié**, ce qui **reste à
> faire**, et les **points de vigilance**.
>
> 🚀 **Pour lancer l'application** (dépendances, Ollama, migration) : voir
> [DEMARRAGE.md](DEMARRAGE.md). Plan détaillé du RAG : [PLAN_RAG.md](PLAN_RAG.md).

---

## 1. Architecture actuelle (rappel)

| Tiers | Techno | État |
|---|---|---|
| Frontend | HTML/CSS/JS natif (sans build) | Fonctionnel, branché sur l'API |
| Backend | FastAPI + SQLAlchemy async + JWT | Branché sur la vraie base |
| Base de données | PostgreSQL **Neon** (cloud) + `pgvector` | Provisionnée, tables + index HNSW/GIN |
| Génération IA | **Pipeline RAG réel** (embeddings 384d + pgvector + LLM via API compatible OpenAI) | ✅ branché et testé end-to-end |
| Fournisseur LLM | **Groq** (`llama-3.3-70b-versatile`), client format OpenAI | ✅ hébergé, rapide ; interchangeable (Mistral/OpenAI/Ollama) via `.env` |
| Transcription audio | **faster-whisper** (`POST /api/speech-to-text`) | ✅ branché (dictée vocale du chat) |

Le backend peut servir le frontend sur la **même origine** (montage `StaticFiles`) :
lancer le backend puis ouvrir `http://localhost:8055/login.html` suffit
(voir [DEMARRAGE.md](DEMARRAGE.md)).

---

## 2. Ce qui est FAIT (et vérifié)

### 2.1. Authentification & sécurité d'accès
- [x] Page de connexion `login.html` (design institutionnel, responsive, dark mode).
- [x] Couche HTTP centralisée `api.js` : base URL configurable, `Authorization: Bearer`
      automatique, **timeout**, erreurs normalisées (`ApiError`, `messageFromError`).
- [x] **Rafraîchissement JWT transparent** sur `401` (mutualisé), déconnexion propre si échec.
- [x] Service `auth.js` : `login` / `logout` / `refresh` / rôles.
- [x] Stockage session `localStorage` **ou** `sessionStorage` selon « Rester connecté ».
- [x] Protection des routes `route-guard.js` : `requireAuth`, `requireGuest`.
- [x] **RBAC déclaratif** par page (`<body data-require-role="…">`) + masquage des liens de nav interdits.
- [x] Déconnexion (topbar) + avatar personnalisé selon l'utilisateur connecté.

### 2.2. Intégration frontend → API (services dédiés)
- [x] `chat-service.js` → **`POST /api/chat`** (réponse + sources + score de confiance conservé).
- [x] `feedback-service.js` → **`POST /api/feedbacks`** (bouton « Signaler »).
- [x] `conversation-service.js` → **`GET /api/conversations`** (sidebar du chat + page Historique).
- [x] `document-service.js` → **`GET / POST / PUT / DELETE`** + **`validate`**.
- [x] Chat branché (fin de la simulation), historique dynamique, base documentaire dynamique
      (liste, ajout via modale, modifier/valider/supprimer avec confirmation).
- [x] **Page Profil** (`profil.html`) branchée : chargement via **`GET /api/auth/me`**
      (`fetchCurrentUser` enfin utilisé) et enregistrement prénom/nom via le nouvel
      endpoint self-service **`PATCH /api/auth/me`** (`updateCurrentUser`). Contrôleur
      dédié `profile.js` ; l'avatar/nom de la topbar se met à jour sans rechargement.
- [x] **Renommer / supprimer une conversation** branché sur **`PATCH`** et **`DELETE
      /api/conversations/{id}`** : menu d'options de la sidebar du chat (`chat.js`, menus
      créés dynamiquement plus de `menu-1..5` statiques) **et** actions par ligne de la
      page Historique (`historique.js`). Renommage en place, suppression à double
      confirmation, toasts, mise à jour du DOM sans rechargement. « Dupliquer » retiré
      (aucun endpoint de copie côté backend).
- [x] **Page Paramètres** (`parametres.html`) rendue fonctionnelle (`settings.js`) :
      préférences (langue, affichage du score de confiance, citation des sources)
      **persistées** en local et **restaurées** au chargement ; le chat respecte
      désormais ces préférences (badge de confiance affichable, masquage des sources).
      **« Effacer tout l'historique »** supprime réellement toutes les conversations de
      l'utilisateur (boucle `DELETE`). Le thème sombre était déjà géré par `theme.js`.
- [x] **Cache du serveur de dev corrigé** : `NoCacheStaticFiles` (main.py) ajoute
      `Cache-Control: no-cache` sur les fichiers statiques → le navigateur revalide via
      l'ETag et prend en compte les modifs JS/CSS **sans Ctrl+Shift+R**.
- [x] **Refuser un document** branché sur **`POST /api/documents/{id}/reject`** :
      bouton « Refuser » sur les cartes (symétrique de « Valider »), badge → « Refusé »
      (statut backend `failed`), toast. CRUD documentaire complété. La validation reflète
      désormais le vrai statut `active`.
- [x] **Gestion des utilisateurs (admin)** : nouvelle page `utilisateurs.html` +
      `users-admin.js` + `user-service.js`, branchée sur **`GET / POST / PATCH / DELETE
      /api/admin/users`**. Tableau des comptes, modale ajout (avec mot de passe) / édition
      (identité, rôle, activation), suppression à confirmation. Lien de nav réservé `admin`
      (section « Administration »). **Garde-fous** : un admin ne peut ni se supprimer ni se
      rétrograder/désactiver lui-même (badge « Vous », actions verrouillées).
- [x] **Signalements (admin)** : nouvelle page `feedbacks.html` + `feedbacks-admin.js`,
      branchée sur **`GET`** et **`DELETE /api/admin/feedbacks`** (fonctions ajoutées à
      `feedback-service.js`). Tableau : note (étoiles + couleur), commentaire, réf. de
      conversation, date ; suppression à confirmation ; recherche. Lien de nav réservé `admin`.
- [x] **Tableau de bord / Statistiques** branché sur de **vraies** données : nouvel endpoint
      **`GET /api/stats`** (router `stats.py`, auth requise) agrégeant conversations (mois
      courant vs précédent → %) et documents (total, récents 7 j, répartition par statut).
      Frontend : `stats-service.js` + `dashboard.js` (le `fetch()` brut sans jeton a été
      remplacé par un service passant par `api.js`), accueil personnalisé. La carte
      « Démarches les plus consultées » (catégories de conversations **inexistantes** dans le
      schéma) a été remplacée par une **répartition réelle des documents par statut**.
      Testé (`test_stats.py`, 4 tests).
- [x] Gestion d'erreurs unifiée : réseau / timeout / serveur / 401 / 403 → messages intégrés
      (toasts, bulles), **jamais d'`alert()`**.

### 2.3. Backend branché sur la vraie base + JWT
- [x] **Bugs bloquants corrigés** : `DocumentChunk` défini en double, réglages LLM/RAG absents de `config.py`.
- [x] Modèle ORM `Feedback` + `lifespan` `create_all` (a créé `message_sources` et `feedbacks` sur Neon).
- [x] Routers réécrits (mock → DB + JWT) : `documents`, `conversation`, `chat`, `feedbacks`, `users`.
- [x] **RBAC serveur** : écritures documents réservées à `admin / responsable_ministere / point_focal`.
- [x] Chat : persiste conversation + messages ; sources tirées des documents réels.
- [x] Montage `StaticFiles` (déploiement mono-origine).
- [x] **Robustesse connexion Neon** : `pool_pre_ping=True` + `pool_recycle=300` sur l'engine
      (`database.py`) → fini les 500 « connection is closed » après une période d'inactivité
      (Neon serverless ferme les connexions oisives).

### 2.4. Vérifications
- [x] **Test full-stack** contre Neon (login admin réel → chat → feedback → historique → documents) : OK.
- [x] Login `401` sans token ; RBAC ; CRUD documents ; persistance chat/conversations vérifiés.

### 2.5. Documentation & nettoyage
- [x] `README.md` §0 (guide de démarrage + test de toutes les pages) et `FRONTEND.md` mis à jour.
- [x] Origines CORS `:8080` ajoutées.
- [x] Code mort supprimé : `mock_store.py`, `logo_SIOUsvg.svg`, `requirements.txt` (vide).

### 2.6. Pipeline RAG / LLM branché (19 juillet 2026)

Le **stub `generate_demo_answer` a été remplacé** par un vrai pipeline RAG,
entièrement asynchrone, et **validé de bout en bout contre Neon + LLM**.

> ⚠️ **Évolution d'architecture (LLM) :** la génération ne passe plus par
> **Ollama/Mistral auto-hébergé** mais par une **API hostée compatible OpenAI**,
> **Groq** par défaut (`llama-3.3-70b-versatile`). Le client `services/llm.py`
> parle le format OpenAI (`POST /chat/completions`), donc le fournisseur se change
> en 3 lignes de `.env` (`llm_base_url`, `llm_api_key`, `llm_model`) — Groq,
> Mistral, Gemini, OpenAI, ou Ollama en local (`/v1`). **Conséquence :** le point
> de vigilance « inférence CPU lente (~7 s/token) » **ne s'applique plus** (Groq
> répond en quelques secondes). Ce choix **assouplit le principe de souveraineté**
> initial (voir [PLAN_RAG.md](PLAN_RAG.md) §0) au profit de la vitesse : à
> réévaluer si l'auto-hébergement redevient une exigence.

- [x] **Nettoyage** : suppression de 7 fichiers morts/cassés (doublons LLM
      `AI/LLM/`, stack OpenAI/FAISS `rag_min.py`/`config_rag.py`, fichiers Streamlit
      à syntaxe invalide). Stack unique retenue : **HuggingFace + pgvector**.
- [x] **Ingestion async** (`AI/RAG/text_to_chunks.py`) : découpage hybride
      (Markdown → récursif « Article … »), embeddings **384d en batch**, modèle
      **chargé paresseusement**, transaction unique tout-ou-rien
      (`processing` → `active`/`failed`).
- [x] **Métadonnées + index + migration** : colonne `chunk_metadata` (JSONB),
      index **HNSW** (vectoriel) + **GIN** (full-text FR), via une **micro-migration
      idempotente au démarrage** (`core/schema_upgrades.py`) — contourne le fait
      que `create_all` n'altère pas les tables Neon existantes.
- [x] **Recherche hybride** (`AI/RAG/semantic_search.py`) : **dense (pgvector `<=>`)
      + sparse (full-text) + fusion RRF**, requête corrigée (`text()`) et async.
      **Filtre `status = 'active'`** appliqué (dense ET sparse) : seuls les documents
      validés remontent.
- [x] **Chat rebranché** (`routers/chat.py` + `services/rag.py` + `services/llm.py`) :
      récupération → génération **LLM (Groq, httpx async, format OpenAI)** → réponse
      **sourcée**, avec persistance des **`message_sources`** (enfin alimentés).
      **Refus** (`REFUSAL_TEXT`, sans appel LLM) quand **aucune** source n'est
      trouvée. Dégradation gracieuse (contexte vide) ou **503** si le LLM est indisponible.
- [x] **Ingestion en tâche de fond** : `POST /api/documents/ingest` (202) +
      `BackgroundTasks` (wrapper `services/ingestion.py`, import paresseux de torch).
- [x] **Ré-indexation idempotente** (`text_to_chunks.py`) : purge des anciens chunks
      du document (`DELETE`) dans la **même transaction** que la réinsertion, avant
      ré-ingestion → pas de doublons.
- [x] **Config unifiée** dans `core/config.py` (`rag_top_k`, `rag_rrf_k`, `llm_timeout`,
      `llm_provider`, `llm_base_url`, `llm_model`, `rag_min_score`…).
- [x] **Tests** : suite complète verte (**93 tests**), dont `test_llm_service.py`
      (client LLM mocké), l'ingestion planifiée (`test_documents.py`), `test_audio.py`
      et le **streaming SSE** + confidence gate (`test_chat.py`).
- [x] **Validation end-to-end réelle** (19/07) : migration Neon appliquée →
      ingestion → recherche hybride (le bon chunk remonte) → génération LLM
      qui **s'appuie sur le contexte** ; données de test nettoyées après coup.

**Reste à faire dans le RAG** : voir §3.3 (upload binaire/extraction, confidence
gate **calibrage** de `rag_min_score`).

### 2.7. Transcription audio (dictée vocale)

- [x] **Endpoint `POST /api/speech-to-text`** (`routers/audio.py`) : reçoit un
      fichier audio (`multipart/form-data`, champ `audio`) et renvoie le texte
      transcrit (`{"text": …}`), aligné sur le front `voice-recorder.js` (déjà fusionné).
- [x] **Module `backend/AI/AUDIO/`** : validation du format, **lecture par blocs
      avec limite de taille** (rejet `413` au-delà), transcription **faster-whisper**
      déportée hors boucle asyncio (`run_in_threadpool`). Erreurs typées
      (`UnsupportedAudioFormatError` → 400, `AudioTooLargeError` → 413,
      `AudioProcessingError` → 500).
- [x] **Tests** : `test_audio.py` (5 tests).

---

## 3. Ce qu'il RESTE à faire

### 3.1. Endpoints backend existants mais NON branchés au frontend
- [x] ~~**Gestion des utilisateurs (router admin)** : lister / créer / modifier des comptes → aucune UI.~~ **fait** : page `utilisateurs.html` complète (voir §2.2).
- [x] ~~**Conversations** : `DELETE` (supprimer) et `PATCH` (renommer)~~ **fait** : menu du chat et page Historique branchés (« Dupliquer » retiré, sans endpoint).
- [x] ~~**Documents** : `POST /{id}/reject` (refuser) — pas de bouton~~ **fait** : bouton « Refuser » branché (voir §2.2). CRUD documentaire complet.
- [x] ~~**Feedbacks** : `GET` (liste), `DELETE`~~ **fait** : page « Signalements » admin branchée sur `GET`/`DELETE /api/admin/feedbacks` (voir §2.2). Reste non branché (facultatif) : `PATCH` et `GET /{id}` du router utilisateur.
- [x] ~~**Auth** : `GET /me`~~ désormais appelé par la page Profil (`fetchCurrentUser`).

### 3.2. Écrans frontend sans backend
- [x] ~~**Profil** (`profil.html`)~~  **fait** : relié à `GET /api/auth/me` + `PATCH /api/auth/me`
      (self-service prénom/nom). Les champs sans support backend (e-mail, téléphone, service,
      photo, mot de passe) ont été retirés ; identifiant et rôle sont en lecture seule.
- [x] ~~**Paramètres** (`parametres.html`) statique.~~ **fait** : préférences persistées
      + effacement réel de l'historique (voir §2.2). Réglage sans effet backend (langue)
      simplement mémorisé côté client.
- [x] ~~**Statistiques / Dashboard** (`dashboard.html`) chiffres en dur, aucun endpoint d'agrégation.~~
      **fait** : endpoint `GET /api/stats` + `dashboard.js` (voir §2.2). ⚠️ La répartition affichée
      porte sur les **documents** (par statut), faute de catégories de conversations dans le schéma.
- [ ] **Panneau de notifications** (topbar)  statique, pas d'endpoint.
- [ ] Initialisation non câblée globalement : `notifications.js`, `context-menu.js`, `skeleton.js`
      (leurs `init…()` ne sont appelés que ponctuellement).

### 3.3. Cœur métier : RAG / LLM
- [x] ~~Remplacer le **stub** `generate_demo_answer`~~ **fait** (voir §2.6) :
  - [x] ~~**Chunking + embeddings** (384 dims) + insertion dans `document_chunks`~~ **fait** (ingestion async + endpoint `/ingest`).
  - [x] ~~**Recherche vectorielle** `pgvector`~~ **fait** — recherche **hybride** (dense + sparse + RRF).
  - [x] ~~**Génération** via LLM (Ollama/Mistral)~~ **fait** (`services/llm.py`, httpx async).
  - [x] ~~Persistance des **`message_sources`**~~ **fait**.
- [ ] **Ingestion — upload binaire réel** (multipart) + **extraction de texte** PDF/DOCX + nettoyage
      (aujourd'hui l'ingestion accepte du **texte** Markdown/txt via `content`). NB : le
      module audio, lui, gère déjà l'upload `multipart` (voir §2.7) — patron réutilisable.
- [x] ~~**Confidence gate**~~ **fait** : refus (`REFUSAL_TEXT`, sans appel LLM ni
      citation) quand **aucune** source **ou** quand la meilleure **similarité cosinus
      < `rag_min_score`** (0.35). La recherche renvoie désormais la similarité cosinus
      `[0,1]` en plus du RRF (`semantic_search.py`) ; le `confidence` retourné = cette
      similarité (calibrée, plus l'ancienne heuristique). Couvert par `test_chat.py`.
      Reste à **calibrer le seuil** sur des cas réels béninois.
- [x] ~~**Filtre `status = 'active'`** dans la recherche~~ **fait** (`semantic_search.py`, dense + sparse).
- [x] ~~**Ré-indexation idempotente**~~ **fait** (`text_to_chunks.py` : `DELETE` des anciens chunks dans la transaction de réinsertion).
- [ ] (Option) **reranking** cross-encoder si la qualité l'exige.
- [x] ~~**Streaming** réel de la réponse~~ **fait** : endpoint **SSE** `POST /api/chat/stream`
      (`stream_answer` httpx `stream:true` → évènements `meta`/`token`/`done`/`error`),
      consommé côté front via `fetch`+`ReadableStream` (`streamQuestion` dans
      `chat-service.js`, rendu progressif dans `chat.js`). Persistance du message IA +
      citations en fin de flux. Vérifié end-to-end (Groq live) + `test_chat.py`.
- [x] **Rendu Markdown** des réponses (gras, listes, titres, code) via un petit
      convertisseur sûr (`renderMarkdown`, échappement puis balisage) — fini les `**`
      et `1.` affichés en texte brut ; CSS de la bulle assistant soigné (`04-chat.css`).
- [x] **Auto-scroll « collant »** pendant la génération : le fil suit le flux tant que
      l'utilisateur ne remonte pas (flag piloté par un écouteur de scroll). Corrige au
      passage la cible de défilement (`.chat-thread`, le vrai conteneur `overflow`, et
      non `.chat-thread__inner`). Le module factice `streaming.js` a été supprimé.
- [x] ~~**Rejeu d'une conversation**~~ **fait** : `GET /api/conversations/{id}/messages` (`conversation.py`, ordre chronologique, contrôle d'appartenance).
- [x] ~~**Performance CPU** (mistral lent)~~ **caduc** : la génération passe désormais par
      **Groq** (API hostée, réponse en quelques secondes). Le curseur vitesse/souveraineté
      est à réévaluer si l'auto-hébergement redevient une exigence.

### 3.4. Sécurité & production
- [ ] Stockage des tokens : `localStorage` est sensible au XSS → envisager cookies `httpOnly` (impact backend).
- [ ] **Rate limiting** (surtout si le chat devient public via le portail vitrine).
- [ ] CORS de production (origines réelles) ; HTTPS ; en-têtes de sécurité (CSP…).
- [ ] **Migrations de schéma** : passer de `create_all` à **Alembic** pour faire évoluer la base proprement.
- [ ] Champ **« catégorie »** de document côté backend (le filtre front retombe sur `file_type`).
- [ ] Corriger le fichier `backend/models/db/users.sql` (virgule finale invalide) — informatif, la table réelle existe déjà.

### 3.5. Qualité
- [x] ~~Tests obsolètes `mock_store` à réécrire~~ **fait** : toute la suite est verte
      (**93 tests**), sur base SQLite isolée + fixtures `admin_token`/`user_token`, LLM mocké.
- [ ] **Test d'intégration RAG sur vraie base Postgres+pgvector** : le SQL hybride
      (`<=>`, `to_tsvector`, RRF) **n'est pas exerçable sur le SQLite** des tests unitaires
      → prévoir un mini-corpus fixture sur une base Postgres de test.
- [ ] **RAGAS** (faithfulness, context/answer relevancy) sur un jeu de questions de référence.
- [ ] CI/CD : vérifier `.github/workflows` (build/lint/tests).

---

## 4. Points de vigilance / dette technique

- **Secrets** : `.env` (identifiants Neon + `JWT_SECRET_KEY`) est **correctement gitignoré** (non commité) ✅. Le garder ainsi ; prévoir une rotation du secret JWT avant la mise en production.
- **Base partagée** : la base Neon est réelle et partagée éviter d'y écrire des données de test non nettoyées. (Les tests unitaires tournent sur SQLite ; les essais RAG manuels doivent nettoyer leurs documents de test.)
- **Migrations** : solution actuelle = **micro-migration idempotente au démarrage** (`core/schema_upgrades.py`, `IF NOT EXISTS`, gardée au dialecte Postgres). À **remplacer par Alembic** quand le schéma devra être versionné/rollbackable. **pgvector ≥ 0.5.0** requis pour l'index HNSW (sinon repli `ivfflat`).
- **Fournisseur LLM = Groq (API hostée)** : la génération passe par une API externe
  compatible OpenAI (`services/llm.py`), plus par Ollama local. Avantage : réponses
  rapides (l'ancien souci « mistral ≈ 7 s/token sur CPU » ne s'applique plus).
  **Contreparties** : dépendance réseau + **clé API** (`LLM_API_KEY` dans `.env`,
  jamais commitée) + **données envoyées à un tiers** — à arbitrer face au principe de
  souveraineté ([PLAN_RAG.md](PLAN_RAG.md) §0). Repli auto-hébergé possible en 3 lignes de `.env`.
- **Cache serveur de dev** : résolu côté FastAPI (`NoCacheStaticFiles`, `Cache-Control: no-cache`)
  quand le frontend est servi par le backend (`:8055`). Ne s'applique **pas** si on sert le
  frontend séparément via `python -m http.server` (`:8080`/`:8202`), qui n'envoie toujours pas
  d'en-têtes de cache → dans ce cas, rechargement forcé (Ctrl+Shift+R) après une modif JS/CSS.
- **Scaffolding** : `backend/AI/LLM/` et les prototypes RAG OpenAI/FAISS ont été
  **supprimés** (voir §2.6) ; la stack unique est HuggingFace + pgvector. Le prototype
  `version_1/DTDI_MANAGEMENT` reste conservé comme référence historique.

---

## 5. Prochaine étape recommandée

Le pipeline RAG est fonctionnel end-to-end (filtre `active`, ré-indexation idempotente,
refus sans source et génération Groq déjà en place). Priorités restantes pour le
**rendre fiable en usage réel** :

1. **Ingestion de vrais documents** : upload binaire + extraction **PDF/DOCX**
   (aujourd'hui seul le texte Markdown/txt est ingéré) — c'est le principal frein à
   l'alimentation du corpus. Le module audio (§2.7) fournit déjà un patron d'upload `multipart`.
2. **Fiabilité des réponses** : brancher le **confidence gate par seuil calibré**
   (`rag_min_score`, aujourd'hui défini mais inutilisé) et calibrer le `confidence` renvoyé.
3. Fiabilisation : **RAGAS** + test d'intégration sur Postgres+pgvector.
4. **Calibrer** le seuil `rag_min_score` sur des cas réels béninois.
