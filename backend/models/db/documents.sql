-- Activation de l'extension pour générer les UUID automatiquement
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Table des documents d'origine (Corpus RAG global)
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    file_path VARCHAR(512) NOT NULL, -- Chemin de stockage (Supabase Storage, S3, local)
    file_type VARCHAR(50) NOT NULL,  -- 'pdf', 'docx', 'txt'
    status VARCHAR(50) NOT NULL DEFAULT 'processing', -- 'processing', 'active', 'failed'
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL, -- Qui a ajouté le fichier
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Table des fragments de documents (Chunks associés aux vecteurs)
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE, -- Supprime les chunks si le document est supprimé
    content TEXT NOT NULL, -- Texte brut du fragment
    page_number INT, -- Pour afficher la page source à la secrétaire
    embedding VECTOR(384) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);