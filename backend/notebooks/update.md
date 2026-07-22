# Autre méthode a essayer pour améliorer les embeddings

## Réalisations:

En supposant que dans le notebook les methodes les plus usuelles ont déjà été testés qui sont entre autre

* le choix de la méthode de chunk qui sont entre autre fixed chunking (mauvais) MakdownSplitter (Tres bon vu qu'on vas transformer en markdown d'abord) Recursive Spliter (Tres bon aussi pour garder le maximum de contexte: On va le combiner avec du markdown splitter pour maximiser les perfs)

* le choix du model open source pour la transformation en embeddings:
BAAI/bge-large (On restera sur celui ci qui a l'air le plus pertinent)
jina-embeddings
e5-large
OpenAI
Voyage AI

## A tester : La recherche hybride

En gros au lieu de faire juste de la recherche vectorielle faire aussi de la recherche textuelle ppur maximiser les perfs
Technologie classique : BM25 ou TF-IDF (utilisée par des outils comme Elasticsearch)
Ultra-précise pour les codes, les identifiants, les noms propres, les sigles administratifs ou le jargon technique exact notamment pour notre contexte juridique
            ┌──> Recherche Lexicale (BM25) ───> Liste A (Scores exacts)                     
Requête     │    
            └──> Recherche Sémantique ────────> Liste B (Scores sémantiques)┘

            (Combinaison)   ├──> RRF / Fusion ──> Top K Final

## Tester aussi la Query Expansion

Envoyer les questions a un autre LLM qui a etendre la question et ensuite on va transformer ses differentes question en embeddings, qu'on enverra ensuite a notre sentence transformers , qu'on va encoder et trouver des passages similaires maintenant

Qui signe les arrêtés ? -->  Qui est responsable de signer les arrêtés ? ; Qui valide les arrêtés ? ; Autorité compétente pour signer...

## Le Reranker
Le Reranker utilise une architecture différente appelée Cross-Encoder (souvent basée sur des modèles de type BERT ou spécialisés comme Cohere Rerank ou BGE-Reranker).

Au lieu de comparer des vecteurs pré-calculés, le Reranker prend la question ET le texte du chunk ensemble, et il les analyse mot à mot en calculant toutes les interactions possibles entre la question et le document.