# Démarrer l'application SIOU (backend + RAG)

Guide opérationnel pour lancer l'API **avec le pipeline RAG réel** (embeddings +
recherche pgvector + génération LLM). Pour le détail des pages frontend, voir
`README.md` §0.

---

## 1. Prérequis (à faire une fois)

### a. Dépendances Python
```bash
uv sync
```
Installe tout, **y compris** `langchain-huggingface` / `sentence-transformers` /
`torch` (plusieurs Go) nécessaires aux embeddings.

### b. Fichier `.env` (non commité)
Pour un nouveau poste, partir du modèle fourni puis remplir les vraies valeurs :
```bash
cp .env.example .env
```
`.env` doit contenir au minimum :
```
DATABASE_URL=postgresql+asyncpg://...neon...   # base Neon + pgvector
JWT_SECRET_KEY=...
USERNAME_ADMIN=...        # compte admin initial
PASSWORD_ADMIN=...

# LLM (génération) — API compatible OpenAI. Défaut : Groq.
LLM_API_KEY=gsk_...       # ⬅️ OBLIGATOIRE : ta clé Groq (voir c.), JAMAIS commitée
```
Réglages LLM optionnels (valeurs par défaut dans `backend/core/config.py`) :
```
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
LLM_MAX_TOKENS=512
LLM_TIMEOUT=60
```

### c. Fournisseur LLM (Groq — API hostée, gratuite)
La génération passe par une **API HTTPS compatible OpenAI** : rien à installer,
pas de serveur ni de machine allumée en permanence.
1. Créer un compte sur **console.groq.com** → générer une **clé API** (gratuit).
2. La mettre dans `.env` : `LLM_API_KEY=gsk_...`.
3. C'est tout — le backend appelle Groq en HTTPS.

> **Changer de fournisseur = 3 lignes .env.** Le client parle le format OpenAI,
> donc compatible aussi **Mistral** (`https://api.mistral.ai/v1`), **Gemini**, ou
> **Ollama en local** (`LLM_BASE_URL=http://localhost:11434/v1`, `LLM_API_KEY` vide).
>
> ⚠️ Le nom exact du modèle peut évoluer côté Groq — vérifier le catalogue sur
> console.groq.com si `LLM_MODEL` renvoie une erreur (ex. `llama-3.1-8b-instant`
> pour plus de débit gratuit).

### d. Modèle d'embedding (optionnel)
- Soit placer les poids locaux sous `backend/pretrained/paraphrase-local`,
- soit ne rien faire : au **premier** appel RAG, le modèle
  `paraphrase-multilingual-MiniLM-L12-v2` (~440 Mo) est téléchargé et **mis en
  cache** automatiquement (accès HuggingFace requis cette fois-là).

---

## 2. Lancer l'application

```bash
uv run uvicorn main:app --reload --port 8055
```
(ou, venv activé : `uvicorn main:app --reload --port 8055`)

Au démarrage, le `lifespan` :
1. crée les tables manquantes (`create_all`) ;
2. applique la **micro-migration** Postgres (colonne `chunk_metadata`, index
   HNSW + GIN) idempotente, ne s'exécute que sur PostgreSQL.

Puis :
- API : http://localhost:8055
- Frontend servi sur la même origine : http://localhost:8055/login.html
- Santé : http://localhost:8055/health

> **pgvector ≥ 0.5.0** requis côté serveur Neon pour l'index HNSW. Si le
> `CREATE INDEX` échoue au démarrage, demander le repli `ivfflat`.

---

## 3. Tester le pipeline RAG de bout en bout

Une fois l'API lancée et authentifié (rôle `admin` / `responsable_ministere` /
`point_focal`) :

| Étape | Requête |
|---|---|
| 1. Se connecter | `POST /api/auth/login` → récupérer `access_token` |
| 2. Ingérer un document | `POST /api/documents/ingest` `{ "title": "...", "content": "# Titre\n..." }` → **202** |
| 3. Suivre l'indexation | `GET /api/documents/{id}` → attendre `status: "active"` |
| 4. Poser une question | `POST /api/chat` `{ "question": "..." }` → réponse **sourcée** |

Notes :
- L'étape 2 (ou la modale « Ajouter un document » du frontend) accepte du **texte**
  (Markdown/txt via `content`) ; l'upload binaire PDF/DOCX n'est pas encore implémenté.
- Le **tout premier** appel touchant les embeddings charge le modèle local
  (~440 Mo, une fois ; préchargé au démarrage). La **génération**, elle, passe par
  Groq (HTTPS) → réponse en quelques secondes.

---

## 4. Lancer les tests

```bash
uv run pytest backend/tests/ -q
```
Les tests tournent sur une base **SQLite isolée** (jamais Neon) et **mockent** le
LLM ; ils ne nécessitent donc ni Ollama ni GPU. Le SQL hybride pgvector n'est,
lui, testable que sur une vraie base Postgres (voir Phase 6 de `PLAN_RAG.md`).
