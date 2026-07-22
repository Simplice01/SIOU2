# Deploiement SIOU2

## Backend Render

Le depot contient `render.yaml`. Il cree uniquement le service web backend, sans base PostgreSQL Render automatique.

Variables d'environnement a renseigner dans Render :

```dotenv
DATABASE_URL=postgresql://...
JWT_SECRET_KEY=...
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=...
LLM_MODEL=gpt-4.1-mini
LLM_TEMPERATURE=0.2
RAG_TOP_K=5
RAG_MIN_SCORE=0.35
```

Commande de build :

```bash
pip install -e .
```

Commande de demarrage :

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Test rapide apres deploiement :

```text
https://<backend-render>/health
```

La reponse attendue est :

```json
{"status":"ok","service":"SIOU"}
```

## Frontend Vercel

Le frontend est statique. Dans Vercel :

- Root Directory : `frontend`
- Framework Preset : `Other`
- Build Command : laisser vide
- Output Directory : `.`

Le fichier `frontend/vercel.json` gere les routes `/`, `/login` et `/dashboard`.

Par defaut, si le site est sur `*.vercel.app`, le frontend appelle :

```text
https://siou2.onrender.com/api
```

Si le nom du service Render change, modifier `frontend/assets/js/modules/api.js`.

## Base PostgreSQL

SIOU2 utilise la base PostgreSQL existante via `DATABASE_URL`.
Les fichiers locaux de base de donnees (`*.db`, `*.sqlite`, `siou_dev.db`) sont ignores par Git et ne doivent pas etre pousses.

Au demarrage, le backend applique seulement des creations idempotentes et micro-migrations compatibles avec la base existante.
