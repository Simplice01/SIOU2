/**
 * documents.js
 * Contrôleur de la page « Base documentaire » (documents.html).
 *
 * - charge la liste réelle via `GET /api/documents` et rend les cartes ;
 * - modale d'ajout / d'édition → `POST` / `PUT /api/documents/{id}` ;
 * - actions par carte : valider (`POST …/validate`) et supprimer (`DELETE`) ;
 * - active la recherche et les filtres sur les cartes rendues.
 *
 * La page est déjà réservée aux rôles habilités (RBAC déclaratif sur <body>),
 * donc les actions d'écriture y sont visibles pour tous les visiteurs.
 *
 * Limites backend assumées : pas d'upload de fichier binaire (l'endpoint
 * n'accepte que des métadonnées) et pas de champ « catégorie » (on s'appuie
 * sur `file_type` / `status`).
 */

import {
  listDocuments,
  getDocument,
  createDocument,
  ingestDocument,
  updateDocument,
  deleteDocument,
  validateDocument,
  rejectDocument,
} from './document-service.js';
import { messageFromError } from './api.js';
import { getUser } from './auth.js';
import { openModal, closeModal } from './modal.js';
import { initFilters } from './filters.js';
import { initInstantSearch } from './search.js';
import { showToast } from './toast.js';
import { escapeHtml, formatRelativeDate } from './utils.js';

const DOC_ICON =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>';

let editingId = null;

/* ------------------------------------------------------------------ */
/*  Présentation du statut                                             */
/* ------------------------------------------------------------------ */

function statusBadge(status) {
  const map = {
    active: { label: 'Actif', cls: 'badge--success' },
    validated: { label: 'Validé', cls: 'badge--success' },
    processing: { label: 'En traitement', cls: 'badge--warning' },
    // Le backend utilise le statut « failed » pour un document refusé.
    failed: { label: 'Refusé', cls: 'badge--danger' },
    rejected: { label: 'Refusé', cls: 'badge--danger' },
  };
  const entry = map[status] || { label: status || 'Inconnu', cls: 'badge--info' };
  return `<span class="badge ${entry.cls}">${escapeHtml(entry.label)}</span>`;
}

function metaLine(doc) {
  const parts = [];
  if (doc.created_at) parts.push(`Indexé ${formatRelativeDate(doc.created_at)}`);
  if (doc.file_type) parts.push(String(doc.file_type).toUpperCase());
  return escapeHtml(parts.join(' · '));
}

/* ------------------------------------------------------------------ */
/*  Rendu des cartes                                                   */
/* ------------------------------------------------------------------ */

function createCard(doc) {
  const card = document.createElement('div');
  card.className = 'card card--hover';
  card.dataset.docCard = '';
  card.dataset.docId = doc.id;
  // Pas de catégorie côté backend : on retombe sur file_type pour la recherche/filtre.
  card.dataset.filterCategory = doc.file_type || 'all';
  card.dataset.searchText = `${doc.title || ''} ${doc.file_path || ''}`.toLowerCase();

  card.innerHTML = `
    <div class="card__header">
      <span class="card__icon-wrap">${DOC_ICON}</span>
      ${statusBadge(doc.status)}
    </div>
    <h3 class="doc-card__title"></h3>
    <p class="doc-card__desc"></p>
    <p class="doc-card__meta">${metaLine(doc)}</p>
    <div class="doc-card__actions">
      <button class="btn btn--ghost btn--sm" data-doc-validate type="button">Valider</button>
      <button class="btn btn--ghost btn--sm" data-doc-reject type="button">Refuser</button>
      <button class="btn btn--ghost btn--sm" data-doc-edit type="button">Modifier</button>
      <button class="btn btn--ghost btn--sm" data-doc-delete type="button">Supprimer</button>
    </div>
  `;

  // Texte inséré via textContent (jamais innerHTML) pour éviter toute injection.
  card.querySelector('.doc-card__title').textContent = doc.title || 'Document';
  card.querySelector('.doc-card__desc').textContent = doc.file_path || '';
  return card;
}

function renderDocuments(list, docs) {
  list.innerHTML = '';
  docs.forEach((doc) => list.appendChild(createCard(doc)));
}

function updateCount(count) {
  const desc = document.querySelector('.page__header .page__desc');
  if (desc) {
    desc.textContent = `${count} document${count > 1 ? 's' : ''} indexé${count > 1 ? 's' : ''} et utilisé${count > 1 ? 's' : ''} par le moteur RAG.`;
  }
  // Barre de pagination statique : on la neutralise tant qu'elle n'est pas branchée.
  const pagination = document.querySelector('.pagination-bar span');
  if (pagination) pagination.textContent = `Affichage de ${count} document${count > 1 ? 's' : ''}`;
}

/* ------------------------------------------------------------------ */
/*  Chargement                                                         */
/* ------------------------------------------------------------------ */

async function loadDocuments(list) {
  list.setAttribute('aria-busy', 'true');
  try {
    const docs = (await listDocuments()) || [];
    renderDocuments(list, docs);
    updateCount(docs.length);
  } catch (error) {
    showToast({
      title: 'Chargement impossible',
      text: messageFromError(error, 'Impossible de charger les documents.'),
      type: 'danger',
    });
  } finally {
    list.removeAttribute('aria-busy');
  }
}

/* ------------------------------------------------------------------ */
/*  Modale d'ajout / d'édition                                         */
/* ------------------------------------------------------------------ */

function modalRefs() {
  return {
    overlay: document.getElementById('upload-modal'),
    title: document.getElementById('upload-modal-title'),
    titleInput: document.getElementById('doc-title'),
    fileInput: document.getElementById('doc-file'),
    submit: document.querySelector('#upload-modal [data-doc-submit]'),
  };
}

function openAddModal() {
  editingId = null;
  const { overlay, title, titleInput, submit } = modalRefs();
  if (!overlay) return;
  if (title) title.textContent = 'Ajouter un document';
  if (submit) submit.textContent = 'Indexer le document';
  if (titleInput) titleInput.value = '';
  openModal(overlay);
}

function openEditModal(doc) {
  editingId = doc.id;
  const { overlay, title, titleInput, submit } = modalRefs();
  if (!overlay) return;
  if (title) title.textContent = 'Modifier le document';
  if (submit) submit.textContent = 'Enregistrer';
  if (titleInput) titleInput.value = doc.title || '';
  openModal(overlay);
}

function fileExtension(name) {
  const match = /\.([a-z0-9]+)$/i.exec(name || '');
  return match ? match[1].toLowerCase() : null;
}

async function handleModalSubmit(list) {
  const { overlay, titleInput, fileInput, submit } = modalRefs();
  const title = titleInput?.value.trim();

  if (!title) {
    showToast({ title: 'Titre requis', text: 'Veuillez renseigner un titre.', type: 'warning' });
    titleInput?.focus();
    return;
  }

  if (submit) submit.disabled = true;
  let ingestedId = null;
  try {
    if (editingId) {
      await updateDocument(editingId, { title });
      showToast({ title: 'Document mis à jour', type: 'success' });
    } else {
      const file = fileInput?.files?.[0];
      const ext = file ? fileExtension(file.name) : null;
      const isText = ext === 'md' || ext === 'markdown' || ext === 'txt';

      if (file && isText) {
        // Fichier texte : on lit le contenu et on lance l'ingestion RAG réelle
        // (découpage + embeddings + chunks en tâche de fond).
        const content = await file.text();
        const created = await ingestDocument({ title, content, fileType: ext === 'markdown' ? 'md' : ext });
        ingestedId = created?.id;
        showToast({
          title: 'Indexation lancée',
          text: 'Découpage et vectorisation en cours… le statut passera à « actif ».',
          type: 'success',
        });
      } else {
        // Pas de contenu texte exploitable (PDF/DOCX : extraction pas encore
        // disponible) → on enregistre seulement les métadonnées.
        await createDocument({
          title,
          file_path: file ? file.name : title,
          file_type: ext || 'pdf',
          status: 'processing',
          uploaded_by: getUser()?.id ?? null,
        });
        showToast({
          title: 'Document ajouté',
          text: file
            ? "Métadonnées enregistrées (indexation du contenu PDF/DOCX pas encore disponible — utilisez .md ou .txt)."
            : 'Métadonnées enregistrées.',
          type: file ? 'warning' : 'success',
        });
      }
    }
    if (overlay) closeModal(overlay);
    if (fileInput) fileInput.value = '';
    await loadDocuments(list); // recharge pour refléter l'état serveur
    // Ingestion asynchrone : on suit le statut en fond et on met à jour la carte
    // quand l'indexation se termine (plus besoin de rafraîchir à la main).
    if (ingestedId) pollDocumentStatus(ingestedId, list);
  } catch (error) {
    showToast({ title: 'Enregistrement impossible', text: messageFromError(error), type: 'danger' });
  } finally {
    if (submit) submit.disabled = false;
  }
}

// Sonde le statut d'un document fraîchement ingéré jusqu'à ce qu'il quitte
// « processing » (→ actif / échec), puis met à jour le badge de sa carte sans
// rechargement. S'arrête après un délai raisonnable (l'utilisateur peut toujours
// rafraîchir la page si besoin).
async function pollDocumentStatus(docId, list, { attempts = 20, delayMs = 2000 } = {}) {
  for (let i = 0; i < attempts; i += 1) {
    await new Promise((resolve) => setTimeout(resolve, delayMs));

    let doc;
    try {
      doc = await getDocument(docId);
    } catch {
      return; // erreur réseau / doc supprimé : on arrête sans bruit
    }

    if (doc?.status && doc.status !== 'processing') {
      const card = list?.querySelector(`[data-doc-id="${docId}"]`);
      const badge = card?.querySelector('.card__header .badge');
      if (badge) badge.outerHTML = statusBadge(doc.status);

      if (doc.status === 'active') {
        showToast({ title: 'Document indexé', text: 'Il est prêt à être interrogé.', type: 'success' });
      } else if (doc.status === 'failed') {
        showToast({
          title: "Échec de l'indexation",
          text: "Le document n'a pas pu être traité.",
          type: 'danger',
        });
      }
      return;
    }
  }
}

/* ------------------------------------------------------------------ */
/*  Actions par carte (délégation)                                     */
/* ------------------------------------------------------------------ */

async function handleValidate(card, button) {
  const id = card.dataset.docId;
  button.disabled = true;
  try {
    await validateDocument(id);
    const header = card.querySelector('.card__header');
    const badge = header?.querySelector('.badge');
    if (badge) badge.outerHTML = statusBadge('active');
    showToast({ title: 'Document validé', type: 'success' });
  } catch (error) {
    button.disabled = false;
    showToast({ title: 'Validation impossible', text: messageFromError(error), type: 'danger' });
  }
}

async function handleReject(card, button) {
  const id = card.dataset.docId;
  button.disabled = true;
  try {
    await rejectDocument(id);
    const header = card.querySelector('.card__header');
    const badge = header?.querySelector('.badge');
    if (badge) badge.outerHTML = statusBadge('failed');
    showToast({ title: 'Document refusé', type: 'success' });
  } catch (error) {
    button.disabled = false;
    showToast({ title: 'Refus impossible', text: messageFromError(error), type: 'danger' });
  }
}

// Confirmation en deux temps, sans boîte de dialogue native.
function handleDelete(card, button, list) {
  const actions = button.closest('.doc-card__actions');
  if (!actions) return;
  const original = actions.innerHTML;

  actions.innerHTML = `
    <span class="doc-card__confirm">Supprimer ?</span>
    <button class="btn btn--danger btn--sm" data-doc-delete-confirm type="button">Confirmer</button>
    <button class="btn btn--ghost btn--sm" data-doc-delete-cancel type="button">Annuler</button>
  `;

  actions.querySelector('[data-doc-delete-cancel]').addEventListener('click', () => {
    actions.innerHTML = original;
  });

  actions.querySelector('[data-doc-delete-confirm]').addEventListener('click', async (event) => {
    const confirmBtn = event.currentTarget;
    confirmBtn.disabled = true;
    try {
      await deleteDocument(card.dataset.docId);
      card.remove();
      updateCount(list.querySelectorAll('[data-doc-card]').length);
      showToast({ title: 'Document supprimé', type: 'success' });
    } catch (error) {
      actions.innerHTML = original;
      showToast({ title: 'Suppression impossible', text: messageFromError(error), type: 'danger' });
    }
  });
}

function findDoc(card) {
  return {
    id: card.dataset.docId,
    title: card.querySelector('.doc-card__title')?.textContent || '',
  };
}

/* ------------------------------------------------------------------ */
/*  Initialisation                                                     */
/* ------------------------------------------------------------------ */

async function initDocuments() {
  const list = document.querySelector('[data-doc-list]');
  if (!list) return;

  await loadDocuments(list);

  // Recherche + filtres (ces initialiseurs ne sont câblés nulle part ailleurs).
  initInstantSearch();
  initFilters();

  // Modale : ajout, fermeture, soumission.
  document.querySelectorAll('[data-modal-open="upload-modal"]').forEach((btn) => {
    btn.addEventListener('click', openAddModal);
  });
  const overlay = document.getElementById('upload-modal');
  if (overlay) {
    overlay.querySelectorAll('[data-modal-close]').forEach((btn) => {
      btn.addEventListener('click', () => closeModal(overlay));
    });
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) closeModal(overlay);
    });
    const form = overlay.querySelector('[data-doc-form]');
    if (form) {
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        handleModalSubmit(list);
      });
    }
  }

  // Actions par carte, en délégation (fonctionne avec les cartes rendues à la volée).
  list.addEventListener('click', (event) => {
    const card = event.target.closest('[data-doc-card]');
    if (!card) return;
    if (event.target.closest('[data-doc-validate]')) {
      handleValidate(card, event.target.closest('[data-doc-validate]'));
    } else if (event.target.closest('[data-doc-reject]')) {
      handleReject(card, event.target.closest('[data-doc-reject]'));
    } else if (event.target.closest('[data-doc-edit]')) {
      openEditModal(findDoc(card));
    } else if (event.target.closest('[data-doc-delete]')) {
      handleDelete(card, event.target.closest('[data-doc-delete]'), list);
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initDocuments);
} else {
  initDocuments();
}
