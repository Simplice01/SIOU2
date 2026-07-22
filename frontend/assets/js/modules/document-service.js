/**
 * document-service.js
 * Accès à l'API de la base documentaire. Enveloppe mince au-dessus de `api.js`.
 *
 * Contrat serveur (backend/routers/documents.py) :
 *   GET    /api/documents               → [{ id, title, file_path, file_type, status, uploaded_by, created_at, updated_at }]
 *   POST   /api/documents               { title, file_path, file_type, status?, uploaded_by? } → document
 *   PUT    /api/documents/{id}          { title?, file_path?, file_type?, status?, uploaded_by? } → document
 *   DELETE /api/documents/{id}          → { detail }
 *   POST   /api/documents/{id}/validate → document (statut → actif)
 *   POST   /api/documents/{id}/reject   → document (statut → refusé)
 */

import { apiFetch } from './api.js';

/** Liste les documents indexés. @returns {Promise<Array>} */
export function listDocuments() {
  return apiFetch('/documents');
}

/** Récupère un document par son identifiant. @returns {Promise<Object>} */
export function getDocument(id) {
  return apiFetch(`/documents/${id}`);
}

/** Enregistre un nouveau document (métadonnées seules). @returns {Promise<Object>} */
export function createDocument(document) {
  return apiFetch('/documents', { method: 'POST', body: document });
}

/**
 * Ingère un document texte : crée le document puis, en tâche de fond, le
 * découpe, calcule les embeddings et stocke les chunks (pipeline RAG).
 * Répond 202 avec le document en statut `processing`.
 * @param {{title:string, content:string, fileType?:string}} params
 * @returns {Promise<Object>}
 */
export function ingestDocument({ title, content, fileType = 'md' }) {
  return apiFetch('/documents/ingest', {
    method: 'POST',
    body: { title, content, file_type: fileType },
  });
}

/** Met à jour un document existant. @returns {Promise<Object>} */
export function updateDocument(id, patch) {
  return apiFetch(`/documents/${id}`, { method: 'PUT', body: patch });
}

/** Supprime un document. @returns {Promise<Object>} */
export function deleteDocument(id) {
  return apiFetch(`/documents/${id}`, { method: 'DELETE' });
}

/** Valide un document avant publication (statut → actif). @returns {Promise<Object>} */
export function validateDocument(id) {
  return apiFetch(`/documents/${id}/validate`, { method: 'POST' });
}

/** Refuse un document (statut → refusé). @returns {Promise<Object>} */
export function rejectDocument(id) {
  return apiFetch(`/documents/${id}/reject`, { method: 'POST' });
}
