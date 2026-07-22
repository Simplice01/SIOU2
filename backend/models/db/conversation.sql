
-- Table qui contient juste une id de conversation entre l'ia et l'humain
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- L'user qui a ouvert cette discussion
    user_id UUID REFERENCES users(id) ON DELETE SET NULL, 
    
    -- Un titre généré par l'IA ou saisi par la secrétaire (ex: "Procédure d'inscription des étudiants")
    title VARCHAR(255) DEFAULT 'Nouvelle recherche',
    
    -- Permet à la secrétaire de classer la discussion
    --status VARCHAR(50) DEFAULT 'en_cours', -- 'en_cours', 'clôturée', 'archivée'
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- Table qui garde le contenu d'une discussion entre l'ia et l'humain! Chaque ligne represente une question et une reponse de la secretaire et est liée a une seule conversation
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    
    -- Qui parle dans ce message ?
    sender_type VARCHAR(50) NOT NULL, -- '(l'humain) ou 'ia' (l'assistant)
    
    -- Le message textuel
    content TEXT NOT NULL,
    
    -- --------------------------------------------------------
    -- Section LLMOps : Remplie uniquement quand sender_type = 'ia'
    -- --------------------------------------------------------
    model_used VARCHAR(100),       -- ex: 'mistral-7b-instruct'
    prompt_tokens INT,             -- Tokens de la question du user + le contexte système
    completion_tokens INT,         -- Tokens de la réponse de l'IA
    latency_ms INT,                -- Temps de génération en millisecondes
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);



-- Table qui permet d'indexer les documents ayant servi à la reponse de la question

CREATE TABLE message_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- La réponse de l'IA concernée
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    
    -- Le morceau de document d'origine utilisé
    chunk_id UUID REFERENCES document_chunks(id) ON DELETE SET NULL,
    
    -- Score de similarité vectorielle (ex: 0.85) calculé lors de la recherche FAISS/Qdrant
    similarity_score FLOAT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);