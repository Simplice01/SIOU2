# Plan d'attaque - Pipeline RAG / LLM de SIOU

**Objectif :** remplacer le stub `generate_demo_answer` par un vrai pipeline
*Retrieval-Augmented Generation* qui répond aux questions des usagers **à partir
des documents officiels indexés**, avec citations et refus si la confiance est
insuffisante.

> Ce document est un plan de mise en œuvre découpé en phases **livrables et
> vérifiables**. Chaque phase peut être développée, testée et fusionnée
> indépendamment. Voir [RAPPORT_AVANCEMENT.md](RAPPORT_AVANCEMENT.md) §3.3.

---

## ✅ Avancement au 2026-07-20

Le pipeline RAG est **branché de bout en bout** et couvert par la suite de tests
(93 tests verts, dégradation gracieuse quand torch/LLM/pgvector sont absents).

| Bloc | État | Détail |
|---|---|---|
| Nettoyage code mort/cassé | ✅ | 7 fichiers supprimés (`util.py`, `utils.py`, `AI/LLM/llm.py`, `AI/LLM/config_llm.py`, `AI/RAG/rag_min.py`, `AI/RAG/config_rag.py`, `test.py`) |
| Ingestion async | ✅ | `text_to_chunks.py` réécrit 100 % async : embeddings **en batch**, modèle **chargé paresseusement**, transaction unique tout-ou-rien |
| Métadonnées + index + migration | ✅ | colonne `chunk_metadata` (JSONB), index **HNSW** + **GIN** full-text FR, micro-migration idempotente au démarrage (`core/schema_upgrades.py`) |
| Recherche hybride | ✅ | `retrieve_hybrid_chunks` async corrigée (`text()`), **dense (pgvector) + sparse (full-text) + RRF**, **filtre `status = 'active'`** |
| Chat branché | ✅ | `retrieve_context` → LLM **Groq** (httpx async, format OpenAI) → réponse **sourcée** + `message_sources` alimentés ; **refus si aucune source** |
| Ingestion en tâche de fond | ✅ | `POST /api/documents/ingest` (202) + `BackgroundTasks` + wrapper `services/ingestion.py` |
| Ré-indexation idempotente | ✅ | purge des anciens chunks (`DELETE`) dans la transaction de réinsertion — plus de doublons |
| Transcription audio | ✅ | `POST /api/speech-to-text` (faster-whisper, `backend/AI/AUDIO/`) — hors périmètre RAG initial mais livré |
| Extraction binaire (PDF/DOCX) | ⛔ à faire | l'ingestion accepte du **texte** (md/txt) ; pas encore d'upload binaire ni d'extraction — voir **Phase 1** |
| Confidence gate **par seuil** | ✅ | refus si aucune source **ou** similarité cosinus < `rag_min_score` (0.35) ; `confidence` = similarité cosinus. Reste : **calibrer** le seuil — voir **Phase 4** |
| Streaming | ✅ | SSE `POST /api/chat/stream` (`meta`/`token`/`done`/`error`), branché au front (`streamQuestion` + rendu **Markdown** live + **auto-scroll collant**) — voir **Phase 5** |
| Évaluation (RAGAS) | ⛔ à faire | voir **Phase 6** |

**Reste pour un run réel** : `uv sync` (installe `langchain-huggingface`/torch), une
**clé API LLM** (`LLM_API_KEY`, Groq par défaut — ou un Ollama local), et une base
**Neon+pgvector** peuplée. Sans eux, l'app démarre et répond quand même (contexte
vide, ou 503 si le LLM est requis).

> ⚠️ **Bascule fournisseur LLM** : la génération n'utilise plus **Ollama/Mistral
> auto-hébergé** mais une **API hostée compatible OpenAI** (**Groq**,
> `llama-3.3-70b-versatile`) — voir §0 et Phase 4. Interchangeable via `.env`.

---

## 0. Principe directeur

> **« Aucune réponse sans document source. »**

- **Souveraineté** : *objectif initial* = modèles auto-hébergés (Ollama / Mistral),
  pas d'API externe pour les données publiques béninoises.
  > ⚠️ **État actuel** : la génération passe par **Groq** (API hostée compatible
  > OpenAI) pour la **vitesse** — la souveraineté stricte est temporairement
  > assouplie. Le client (`services/llm.py`) parle le format OpenAI, donc le repli
  > vers un **Ollama auto-hébergé** ne coûte que 3 lignes de `.env`. Décision à
  > réévaluer selon les exigences de confidentialité des données.
- **Traçabilité** : chaque réponse cite les chunks utilisés (`message_sources`).
- **Confidence gate** : sous un seuil de similarité/score, l'assistant **refuse
  de répondre** plutôt que d'inventer. *(Aujourd'hui : refus si aucune source ;
  le seuil calibré `rag_min_score` reste à brancher — Phase 4.)*

---

## 1. État des lieux (ce qui existe déjà)

| Élément | État | Emplacement |
|---|---|---|
| Table `document_chunks` + colonne `embedding Vector(384)` | ✅ créée | `backend/models/document_models.py:80` |
| Table `message_sources` (citations) | ✅ créée | `backend/models/conversation_models.py` |
| `pgvector` | ✅ activé sur Neon | — |
| Stub de génération `generate_demo_answer` | ✅ remplacé | `backend/services/llm.py` (`generate_answer`, **Groq**/format OpenAI) |
| Endpoint chat | ✅ vrai retrieval hybride + génération | `backend/routers/chat.py` |
| Réglages `rag_top_k=5`, `rag_rrf_k=60`, `llm_timeout` | ✅ | `backend/core/config.py` |
| Pipeline RAG (chunking/recherche) | ✅ branché | `backend/AI/RAG/` (`text_to_chunks.py`, `semantic_search.py`) |
| Affichage progressif + Markdown | ✅ rendu Markdown live + auto-scroll collant | `frontend/assets/js/modules/chat.js` (`renderMarkdown`) ; `streaming.js` factice supprimé |

### ✅ Incohérences résolues
1. **Dimension d'embedding** : alignée sur **384** partout (modèle local
   `paraphrase-multilingual-MiniLM-L12-v2`). Les configs OpenAI/1536 contradictoires
   (`config_rag.py`) ont été supprimées.
2. **Duplication** : doublons supprimés (`AI/LLM/llm.py`, `AI/LLM/config_llm.py`) ;
   source de vérité unique dans `core/config.py`.
3. Le scaffolding OpenAI/FAISS (`AI/RAG/rag_min.py`) a été **supprimé** au profit de
   la stack unique HuggingFace + pgvector.

---

## 2. Architecture cible

```
        ┌─────────────── INGESTION (offline / admin) ───────────────┐
Upload  │  fichier → extraction texte → nettoyage → chunking →       │
(PDF..) │  embeddings (384d) → INSERT document_chunks(embedding)     │
        └────────────────────────────────────────────────────────────┘

        ┌─────────────── REQUÊTE (online / usager) ─────────────────┐
Question│  embed(question) → recherche pgvector top-k (<=> distance) │
        │  → [reranking?] → construction du contexte →               │
        │  LLM (Ollama) + prompt système → réponse + score →         │
        │  confidence gate → persistance message + message_sources   │
        └────────────────────────────────────────────────────────────┘
```

---

## 3. Phases

### Phase 0 : Socle & décisions (fondations) — ✅ **faite**
**But :** trancher les choix techniques et préparer le terrain.
- [x] Modèle d'embedding local **384 dims** : `paraphrase-multilingual-MiniLM-L12-v2`
      (chargé paresseusement, chemin résolu via `__file__`, fallback HF).
- [x] **LLM** : client HTTP async au **format OpenAI** (`services/llm.py`, httpx).
      Fournisseur par défaut **Groq** (`llama-3.3-70b-versatile`) ; Ollama/Mistral
      local reste possible via `.env` (voir §0 sur l'assouplissement de la souveraineté).
- [x] Doublons supprimés → une seule config dans `core/config.py`.
- [~] Dépendances déjà **déclarées** (`pyproject.toml` : `langchain-huggingface`,
      `sentence-transformers`, `httpx`) mais **pas encore installées** dans le venv
      (`uv sync` requis pour torch avant un run réel).
- [x] Index vectoriel pgvector : index **HNSW** (`vector_cosine_ops`) + **GIN**
      full-text créés par la micro-migration de démarrage (`core/schema_upgrades.py`).

---

### Phase 1 - Ingestion : extraction & nettoyage — ⛔ **à faire**
**But :** transformer un fichier uploadé en texte propre.
> Aujourd'hui l'ingestion accepte du **texte** (`POST /api/documents/ingest`,
> md/txt via `content`). L'upload binaire et l'extraction restent à faire.
- [ ] Endpoint **upload binaire réel** (`multipart/form-data`). Stocker le fichier
      (disque/objet) et son chemin.
- [ ] **Extraction de texte** selon le type : PDF (pypdf/pdfminer), DOCX (python-docx),
      TXT. Gérer les échecs → statut `failed`.
- [ ] **Nettoyage** : espaces, en-têtes/pieds répétés, césures, normalisation Unicode.
- [ ] Brancher l'extraction en amont de `run_document_ingestion` (qui attend déjà du texte).

**Livrable vérifiable :** uploader un PDF réel → texte extrait consultable ; test
unitaire sur un petit fichier fixture.

---

### Phase 2 - Chunking + embeddings → `document_chunks` — ✅ **faite**
**But :** peupler la table de chunks vectorisés.
- [x] **Chunking hybride** : MarkdownHeaderTextSplitter (structure) puis
      RecursiveCharacterTextSplitter (séparateurs adaptés aux « Article … »), avec
      propagation des métadonnées structurelles (`chunk_metadata` + fil d'Ariane).
- [x] **Embeddings 384d** par chunk **en batch** (`embed_documents`).
- [x] **INSERT** dans `document_chunks` (transaction unique tout-ou-rien).
- [x] Indexation déclenchée en **tâche de fond** (`POST /ingest` → `BackgroundTasks`),
      statut `processing` → `active`/`failed`.
- [x] **Ré-indexation idempotente** : purge des anciens chunks (`DELETE ... WHERE
      document_id = …`) dans la **même transaction** que la réinsertion (`text_to_chunks.py`)
      → ré-ingérer un document ne duplique plus les chunks.

**Livrable vérifiable :** vérifié via `verif_ingestion_bg` (document `processing` →
`active`, chunks rattachés) et 6 cas fonctionnels de `text_to_chunks`.

---

### Phase 3 - Recherche vectorielle (retrieval) — ✅ **faite** (hybride)
**But :** retrouver les chunks pertinents pour une question.
- [x] `embed(question)` puis recherche **hybride** dans Postgres : **dense** pgvector
      (`<=>` cosinus) + **sparse** full-text FR (`ts_rank_cd`), fusionnées par **RRF**
      (`retrieve_hybrid_chunks`, `services/rag.py`).
- [x] Renvoie chunks + score + document d'origine (titre/méta) pour les citations.
- [x] **Filtre `status = 'active'`** appliqué dans la requête SQL (sur la branche
      **dense ET sparse**, `semantic_search.py`) : les chunks de documents non
      validés ne remontent plus.
- [ ] (Option, non fait) **reranking** cross-encoder si la qualité l'exige.

**Livrable vérifiable :** câblage async validé (stub `text()`/params) ; la pertinence
réelle demande une base Neon+pgvector peuplée (run live).

---

### Phase 4 - Génération + confidence gate + citations — 🟡 **en grande partie faite**
**But :** produire la réponse ancrée dans le contexte, ou refuser.
- [x] **Prompt système** cadré (déjà dans `settings.system_prompt`, injecté par
      `build_chat_messages`).
- [x] Appel **LLM (Groq, format OpenAI)** avec question + contexte (`generate_answer`,
      httpx async, erreurs → `LLMError` → 503).
- [x] Persister le message IA **et** les **`message_sources`** (liens chunks + score).
- [x] `generate_demo_answer` remplacé dans `chat.py`.
- [x] **Confidence gate** : `chat.py` refuse (`REFUSAL_TEXT`, **sans appel LLM ni
      citation**) si **aucune** source **ou** si la meilleure **similarité cosinus
      < `rag_min_score`** (0.35). La recherche hybride expose désormais la similarité
      cosinus `[0,1]` (`semantic_search.py`) en plus du RRF (classement) ; le
      `confidence` renvoyé = cette similarité (calibrée). Couvert par `test_chat.py`.
- [ ] **Calibrage du seuil** `rag_min_score` sur des cas réels béninois (le seuil
      cosinus 0.35 est une valeur de départ).

**Livrable vérifiable :** logique de gate validée (mock LLM + tests, refus sous seuil) ;
le **calibrage fin** du seuil demande un run sur corpus réel.

---

### Phase 5 - Streaming de la réponse — ✅ **faite**
**But :** afficher la réponse au fil de l'eau.
- [x] Endpoint **SSE** `POST /api/chat/stream` (`StreamingResponse`) streamant les tokens
      du LLM : `stream_answer` (`services/llm.py`, httpx `stream:true`, parse SSE OpenAI)
      → évènements `meta` / `token` / `done` / `error` (`routers/chat.py`).
- [x] Front branché sur le flux réel : `streamQuestion` (`chat-service.js`,
      `fetch`+`ReadableStream`, en-tête `Authorization`) → rendu dans `chat.js`
      (**Markdown live** via `renderMarkdown`, puis confiance + sources + actions).
- [x] **Rendu Markdown** sûr (gras/listes/titres/code) + CSS de bulle soigné
      (`04-chat.css`) ; **auto-scroll collant** pendant la génération (cible corrigée :
      `.chat-thread`). Module factice `streaming.js` supprimé.
- [x] Message IA + citations **persistés en fin de flux** (transaction unique via la
      session injectée) ; rollback si la génération échoue en cours de route.

**Livrable vérifiable :** ✅ vérifié end-to-end (Groq live : réponses ASIN/SBIN streamées
en Markdown — listes, gras —, badge de confiance, 5 sources, fil qui suit le flux
automatiquement, message enregistré) + `test_chat.py` (SSE mocké).

---

### Phase 6 - Qualité & évaluation — ⛔ **à faire**
**But :** mesurer et fiabiliser.
- [ ] **RAGAS** (faithfulness, answer/context relevancy) sur un jeu de questions/réponses de référence.
- [ ] Tests d'intégration du pipeline **sur vraie base Postgres+pgvector** (ingestion →
      retrieval → génération) avec un mini-corpus fixture — le SQL hybride n'est pas
      testable sur le SQLite des tests unitaires actuels.
- [x] Tests unitaires ajoutés : `test_llm_service.py` (client LLM mocké),
      `test_chat.py` (génération + confidence gate + streaming SSE mockés),
      `test_documents.py` (ingestion planifiée).

**Livrable vérifiable :** rapport RAGAS reproductible ; suite de tests verte.

---

## 4. Ordre recommandé (MVP → complet)

1. ✅ **Phase 0** (socle) + **Phases 2 → 3 → 4** (retrieval hybride, gate, génération)
   + **Phase 5** (streaming) : **faites**.
2. ⛔ **Phase 1** (ingestion binaire PDF/DOCX) : le principal reste pour alimenter le corpus.
3. **Phase 6** (RAGAS/tests d'intégration pgvector) : en continu.

**Jalon MVP =** atteint (réponse sourcée streamée ou refus argumenté). Reste surtout
l'**ingestion de vrais documents** (Phase 1) pour élargir le corpus au-delà du texte md/txt.

---

## 5. Points de vigilance

- **Performance d'indexation** : ✅ traitée en **tâche de fond** (`BackgroundTasks`) ;
  pour un très gros volume, envisager une vraie file (worker dédié) plutôt que
  `BackgroundTasks` in-process.
- **Fichiers volumineux** : l'ingestion charge encore tout le texte en mémoire
  (`f.read()`) — le streaming reste à faire pour de très gros documents.
- **Coût mémoire** : seul le **modèle d'embedding** (~440 Mo, torch/HF) tourne
  désormais localement — le **LLM est déporté sur Groq** (plus de poids Mistral à
  héberger). En contrepartie : **clé API** requise (`LLM_API_KEY`, `.env`) et
  **données envoyées à un tiers** (à arbitrer côté confidentialité, voir §0).
- **Base partagée Neon** : indexer sur un schéma/quota maîtrisé, ne pas polluer.
- **Migrations** : solution actuelle = **micro-migration idempotente au démarrage**
  (`core/schema_upgrades.py`, `IF NOT EXISTS`, gardée au dialecte Postgres). À
  **remplacer par Alembic** dès que le schéma se versionne (rollback, historique).
- **pgvector ≥ 0.5.0** requis côté serveur pour l'index **HNSW** ; sinon repli `ivfflat`.
- **Sécurité** : valider les fichiers uploadés (type, taille, contenu) ; l'upload
  reste réservé aux rôles d'écriture documentaire.
- **Qualité multilingue** : corpus FR + expressions locales → le modèle multilingue
  384d est un bon choix ; vérifier sur des cas réels béninois.
