/**
 * chat.js
 * Gestion de l'interface de conversation et des interactions utilisateur.
 */

import { initVoiceRecorder } from './voice-recorder.js';
import { streamQuestion } from './chat-service.js';
import { reportAnswer } from './feedback-service.js';
import {
    listConversations,
    getConversationMessages,
    updateConversation,
    deleteConversation,
} from './conversation-service.js';
import { messageFromError } from './api.js';
import { showToast } from './toast.js';
import { getSettings } from './settings.js';
import { formatRelativeDate, escapeHtml } from './utils.js';

// État du chat
let isStreaming = false;
let currentConversationId = null;
let selectedAttachments = [];

// Initialisation du composant de chat
export function initChat() {
    const composerForm = document.querySelector('[data-composer-form]');
    const composerInput = document.querySelector('[data-composer-input]');
    const composerSend = document.querySelector('[data-composer-send]');
    const chatThread = document.querySelector('.chat-thread__inner');

    if (!composerForm || !composerInput || !composerSend || !chatThread) {
        console.warn('[chat] Composants de chat introuvables - abandon');
        return;
    }

    // Gestion de l'état du bouton d'envoi
    composerInput.addEventListener('input', () => {
        composerSend.disabled = composerInput.value.trim() === '';
    });

    // Gestion de la soumission du formulaire
    composerForm.addEventListener('submit', handleFormSubmit);

    // Raccourci clavier
    composerInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!composerSend.disabled) {
                composerForm.dispatchEvent(new Event('submit'));
            }
        }
    });

    // Gestion des suggestions
    document.querySelectorAll('[data-suggestion]').forEach(suggestion => {
        suggestion.addEventListener('click', () => {
            const question = suggestion.getAttribute('data-suggestion');
            composerInput.value = question;
            composerInput.focus();
            composerInput.dispatchEvent(new Event('input', { bubbles: true }));
        });
    });

    // Saisie vocale (bouton micro) - insère le texte transcrit dans composerInput,
    // n'envoie jamais le message automatiquement.
    initVoiceRecorder(composerInput);
    initAttachmentPicker(composerInput, composerSend);

    // Historique des conversations (panneau de gauche) + « Nouvelle conversation »
    initHistorySidebar();

    console.log('[chat] Module initialisé');
}

// SVG des trois points (bouton d'options d'une conversation).
const MORE_ICON =
    '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/></svg>';

// Panneau d'historique : alimente la liste depuis GET /api/conversations et
// câble le bouton « Nouvelle conversation ».
async function initHistorySidebar() {
    const list = document.querySelector('.chat-history__list');

    const newChatBtn = document.getElementById('new-chat-btn');
    if (newChatBtn) newChatBtn.addEventListener('click', resetConversation);

    if (!list) return;

    // Délégation (attachée une seule fois, vaut pour les éléments rendus
    // dynamiquement) : le bouton « options » ouvre le menu (renommer / supprimer) ;
    // un clic sur la ligne elle-même ouvre la conversation (rejeu du fil).
    list.addEventListener('click', (event) => {
        const moreBtn = event.target.closest('.history-item__more');
        if (moreBtn) {
            event.stopPropagation();
            const item = moreBtn.closest('.history-item');
            if (item) openConversationMenu(moreBtn, item);
            return;
        }
        // Ignorer les clics pendant un renommage / une confirmation de suppression.
        if (event.target.closest('.history-item__rename, .history-item__confirm')) return;
        const item = event.target.closest('.history-item');
        if (item && !item.classList.contains('history-item--confirming')) {
            loadConversation(item.dataset.conversationId, item);
        }
    });

    list.innerHTML = '<p class="chat-history__hint">Chargement…</p>';
    try {
        const conversations = (await listConversations()) || [];
        renderHistorySidebar(list, conversations);
    } catch (error) {
        list.innerHTML = `<p class="chat-history__hint">${escapeHtml(
            messageFromError(error, 'Historique indisponible.'),
        )}</p>`;
    }
}

// Rendu de la liste d'historique, regroupée par date relative.
function renderHistorySidebar(list, conversations) {
    if (!conversations.length) {
        list.innerHTML = '<p class="chat-history__hint">Aucune conversation pour le moment.</p>';
        return;
    }

    const groups = new Map();
    conversations.forEach((conversation) => {
        const label = conversation.created_at ? formatRelativeDate(conversation.created_at) : 'Récent';
        if (!groups.has(label)) groups.set(label, []);
        groups.get(label).push(conversation);
    });

    list.innerHTML = '';
    groups.forEach((items, label) => {
        const heading = document.createElement('p');
        heading.className = 'chat-history__date-group';
        heading.dataset.dateGroup = '';
        heading.textContent = label;
        list.appendChild(heading);

        items.forEach((conversation) => {
            list.appendChild(createHistoryItem(conversation));
        });
    });
}

// Construit une ligne d'historique avec son bouton d'options.
function createHistoryItem(conversation) {
    const item = document.createElement('div');
    item.className = 'history-item';
    item.dataset.conversationId = conversation.id;

    const title = document.createElement('span');
    title.className = 'history-item__title';
    title.textContent = conversation.title || 'Conversation';

    const more = document.createElement('button');
    more.type = 'button';
    more.className = 'history-item__more';
    more.setAttribute('aria-label', 'Options de la conversation');
    more.setAttribute('aria-haspopup', 'true');
    more.innerHTML = MORE_ICON;

    item.append(title, more);
    return item;
}

/* ------------------------------------------------------------------ */
/*  Menu d'options d'une conversation (renommer / supprimer)           */
/* ------------------------------------------------------------------ */

let openConvMenu = null;

function closeConvMenu() {
    if (!openConvMenu) return;
    openConvMenu.remove();
    openConvMenu = null;
}

// Positionne le menu sous le déclencheur, en le recalant si le bord droit
// de la fenêtre est trop proche (reprend la logique de context-menu.js).
function positionConvMenu(menu, trigger) {
    const rect = trigger.getBoundingClientRect();
    const menuWidth = menu.offsetWidth || 190;
    const spaceRight = window.innerWidth - rect.right;
    menu.style.top = `${rect.bottom + window.scrollY + 4}px`;
    menu.style.left =
        spaceRight < menuWidth
            ? `${rect.right + window.scrollX - menuWidth}px`
            : `${rect.left + window.scrollX}px`;
}

function openConversationMenu(trigger, item) {
    const alreadyOpen = openConvMenu && openConvMenu.dataset.forId === item.dataset.conversationId;
    closeConvMenu();
    if (alreadyOpen) return; // second clic sur le même déclencheur → ferme

    const menu = document.createElement('div');
    menu.className = 'context-menu is-open';
    menu.setAttribute('role', 'menu');
    menu.dataset.forId = item.dataset.conversationId;
    menu.innerHTML = `
        <button class="context-menu__item" data-conv-action="rename" role="menuitem" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>Renommer
        </button>
        <div class="context-menu__divider"></div>
        <button class="context-menu__item context-menu__item--danger" data-conv-action="delete" role="menuitem" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6"/></svg>Supprimer
        </button>
    `;
    document.body.appendChild(menu);
    positionConvMenu(menu, trigger);
    openConvMenu = menu;

    menu.addEventListener('click', (event) => {
        const btn = event.target.closest('[data-conv-action]');
        if (!btn) return;
        event.stopPropagation();
        const action = btn.dataset.convAction;
        closeConvMenu();
        if (action === 'rename') startRename(item);
        else if (action === 'delete') confirmDelete(item);
    });
}

// Fermeture globale du menu (clic extérieur / Échap / redimensionnement).
document.addEventListener('click', closeConvMenu);
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeConvMenu();
});
window.addEventListener('resize', closeConvMenu);

// Renommage en place : le titre devient un champ éditable ; Entrée valide,
// Échap annule, la perte de focus enregistre.
function startRename(item) {
    const titleSpan = item.querySelector('.history-item__title');
    if (!titleSpan) return;
    const id = item.dataset.conversationId;
    const current = titleSpan.textContent;

    const input = document.createElement('input');
    input.className = 'history-item__rename';
    input.value = current;
    input.setAttribute('aria-label', 'Nouveau nom de la conversation');
    titleSpan.replaceWith(input);
    input.focus();
    input.select();

    let done = false;
    const finish = async (save) => {
        if (done) return;
        done = true;
        const newTitle = input.value.trim();
        const span = document.createElement('span');
        span.className = 'history-item__title';

        if (save && newTitle && newTitle !== current) {
            try {
                const updated = await updateConversation(id, { title: newTitle });
                span.textContent = updated.title || newTitle;
                input.replaceWith(span);
                showToast({ title: 'Conversation renommée', type: 'success' });
            } catch (error) {
                span.textContent = current;
                input.replaceWith(span);
                showToast({ title: 'Renommage impossible', text: messageFromError(error), type: 'danger' });
            }
        } else {
            span.textContent = current;
            input.replaceWith(span);
        }
    };

    input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            finish(true);
        } else if (event.key === 'Escape') {
            event.preventDefault();
            finish(false);
        }
    });
    input.addEventListener('blur', () => finish(true));
}

// Suppression avec confirmation en deux temps, directement dans la ligne.
function confirmDelete(item) {
    const id = item.dataset.conversationId;
    const original = item.innerHTML;

    item.classList.add('history-item--confirming');
    item.innerHTML = `
        <span class="history-item__title">Supprimer&nbsp;?</span>
        <span class="history-item__confirm">
            <button class="btn btn--danger btn--sm" data-conv-del-confirm type="button">Oui</button>
            <button class="btn btn--ghost btn--sm" data-conv-del-cancel type="button">Non</button>
        </span>
    `;

    item.querySelector('[data-conv-del-cancel]').addEventListener('click', (event) => {
        event.stopPropagation();
        item.classList.remove('history-item--confirming');
        item.innerHTML = original;
    });

    item.querySelector('[data-conv-del-confirm]').addEventListener('click', async (event) => {
        event.stopPropagation();
        event.currentTarget.disabled = true;
        try {
            await deleteConversation(id);
            // Si la conversation supprimée est celle affichée, on repart à zéro.
            if (currentConversationId === id) resetConversation();
            const list = item.parentElement;
            item.remove();
            pruneEmptyGroups(list);
            showToast({ title: 'Conversation supprimée', type: 'success' });
        } catch (error) {
            item.classList.remove('history-item--confirming');
            item.innerHTML = original;
            showToast({ title: 'Suppression impossible', text: messageFromError(error), type: 'danger' });
        }
    });
}

// Retire les en-têtes de date qui n'ont plus de conversation, et affiche
// l'état vide si toutes les conversations ont été supprimées.
function pruneEmptyGroups(list) {
    if (!list) return;
    list.querySelectorAll('[data-date-group]').forEach((heading) => {
        const next = heading.nextElementSibling;
        if (!next || !next.classList.contains('history-item')) heading.remove();
    });
    if (!list.querySelector('.history-item')) {
        list.innerHTML = '<p class="chat-history__hint">Aucune conversation pour le moment.</p>';
    }
}

// « Nouvelle conversation » : réinitialise le fil courant sans quitter la page.
function initAttachmentPicker(composerInput, composerSend) {
    const attachButton = document.querySelector('[data-composer-attach]');
    const fileInput = document.querySelector('[data-composer-file]');
    const attachmentList = document.querySelector('[data-composer-attachments]');

    if (!attachButton || !fileInput || !attachmentList) return;

    attachButton.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
        const files = Array.from(fileInput.files || []);
        if (!files.length) return;

        const existingKeys = new Set(selectedAttachments.map(fileKey));
        for (const file of files) {
            if (selectedAttachments.length >= 5) {
                showToast({
                    title: 'Limite atteinte',
                    text: 'Vous pouvez joindre au maximum 5 fichiers par message.',
                    type: 'warning',
                });
                break;
            }
            if (!existingKeys.has(fileKey(file))) {
                selectedAttachments.push(file);
                existingKeys.add(fileKey(file));
            }
        }

        fileInput.value = '';
        renderAttachments(attachmentList, composerInput, composerSend);
        showToast({
            title: 'Fichier joint',
            text: 'Le fichier est ajouté au message. Écrivez votre question pour l’envoyer à SIOU.',
            type: 'success',
        });
    });
}

function fileKey(file) {
    return `${file.name}:${file.size}:${file.lastModified}`;
}

function formatFileSize(bytes) {
    if (bytes < 1024) return `${bytes} o`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} Ko`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}

function renderAttachments(container, composerInput, composerSend) {
    container.innerHTML = '';
    selectedAttachments.forEach((file, index) => {
        const chip = document.createElement('div');
        chip.className = 'attachment-chip';
        chip.innerHTML = `
            <span class="attachment-chip__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <path d="M14 2v6h6"/>
                </svg>
            </span>
            <span class="attachment-chip__name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</span>
            <span class="attachment-chip__size">${formatFileSize(file.size)}</span>
            <button class="attachment-chip__remove" type="button" aria-label="Retirer ${escapeHtml(file.name)}">x</button>
        `;
        chip.querySelector('.attachment-chip__remove')?.addEventListener('click', () => {
            selectedAttachments.splice(index, 1);
            renderAttachments(container, composerInput, composerSend);
            composerInput?.focus();
        });
        container.appendChild(chip);
    });

    if (composerSend && composerInput) {
        composerSend.disabled = composerInput.value.trim() === '';
    }
}

function clearAttachments() {
    selectedAttachments = [];
    const attachmentList = document.querySelector('[data-composer-attachments]');
    if (attachmentList) attachmentList.innerHTML = '';
}

function resetConversation() {
    currentConversationId = null;
    clearAttachments();
    const chatThread = document.querySelector('.chat-thread__inner');
    if (chatThread) {
        chatThread.querySelectorAll('.message, .thinking-indicator').forEach((el) => el.remove());
    }
    document
        .querySelectorAll('.history-item.is-active')
        .forEach((el) => el.classList.remove('is-active'));
    const composerInput = document.querySelector('[data-composer-input]');
    if (composerInput) {
        composerInput.value = '';
        composerInput.focus();
    }
}

// Rejeu d'une conversation : charge ses messages et les réaffiche dans le fil.
async function loadConversation(id, item) {
    if (!id || id === currentConversationId || isStreaming) return;

    const chatThread = document.querySelector('.chat-thread__inner');
    if (!chatThread) return;

    // État actif dans la sidebar.
    document
        .querySelectorAll('.history-item.is-active')
        .forEach((el) => el.classList.remove('is-active'));
    if (item) item.classList.add('is-active');

    // Vider le fil courant (on garde l'écran d'accueil, comme ailleurs).
    chatThread.querySelectorAll('.message, .thinking-indicator').forEach((el) => el.remove());

    try {
        const messages = (await getConversationMessages(id)) || [];
        currentConversationId = id;
        messages.forEach((message) => {
            const sender = message.sender_type === 'human' ? 'user' : 'assistant';
            // Les sources ne sont pas reconstituées pour l'historique (v1).
            const element = createMessageElement(message.content || '', sender, [], {
                model: message.model_used,
            });
            chatThread.appendChild(element);
        });
        scrollToBottom(false);
    } catch (error) {
        showToast({
            title: 'Impossible de charger la conversation',
            text: messageFromError(error),
            type: 'danger',
        });
    }
}

// Gestion de la soumission du formulaire
function handleFormSubmit(e) {
    e.preventDefault();

    const composerInput = document.querySelector('[data-composer-input]');
    const composerSend = document.querySelector('[data-composer-send]');

    if (!composerInput || isStreaming || composerInput.value.trim() === '') {
        return;
    }

    const question = composerInput.value.trim();
    const attachmentNames = selectedAttachments.map((file) => `${file.name} (${formatFileSize(file.size)})`);
    const questionWithAttachments = attachmentNames.length
        ? `${question}\n\nFichiers joints : ${attachmentNames.join(', ')}`
        : question;

    // Ajouter le message de l'utilisateur
    addUserMessage(questionWithAttachments);

    // Réinitialiser le champ de saisie
    composerInput.value = '';
    clearAttachments();
    if (composerSend) composerSend.disabled = true;

    // Envoyer la question au backend
    requestAssistantResponse(questionWithAttachments);
}

// Ajouter un message utilisateur au fil de conversation
function addUserMessage(text) {
    const chatThread = document.querySelector('.chat-thread__inner');
    if (!chatThread) return;

    const messageElement = createMessageElement(text, 'user');
    chatThread.appendChild(messageElement);

    // L'utilisateur vient d'envoyer : on l'amène toujours en bas (défilement doux).
    scrollToBottom(true);
}

// Ajouter un message de l'assistant au fil de conversation
function addAssistantMessage(text, sources = [], meta = {}) {
    const chatThread = document.querySelector('.chat-thread__inner');
    if (!chatThread) return;

    const messageElement = createMessageElement(text, 'assistant', sources, meta);
    chatThread.appendChild(messageElement);

    scrollToBottom(true);
}

/* ------------------------------------------------------------------ */
/*  Rendu Markdown léger (réponses de l'assistant)                     */
/*                                                                     */
/*  Le LLM répond en Markdown (gras, listes, titres). On le convertit  */
/*  en HTML sûr : le texte est d'abord échappé (escapeHtml), puis les  */
/*  seules balises injectées sont celles que l'on génère — pas de XSS. */
/* ------------------------------------------------------------------ */

// Mise en forme « en ligne » : gras, italique, code. Appliquée sur du texte
// DÉJÀ échappé (donc `<`, `>`, `&` sont neutralisés).
function renderInlineMarkdown(escaped) {
    return escaped
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/__([^_]+)__/g, '<strong>$1</strong>')
        .replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
}

// Convertit un texte Markdown en HTML (paragraphes, listes ordonnées/à puces,
// titres). Regroupe les lignes en blocs séparés par des lignes vides.
function renderMarkdown(raw) {
    const lines = escapeHtml(String(raw || '')).split('\n');
    const html = [];
    let paragraph = [];
    let listItems = [];
    let listTag = null; // 'ol' | 'ul'

    const flushParagraph = () => {
        if (paragraph.length) {
            html.push(`<p>${renderInlineMarkdown(paragraph.join(' '))}</p>`);
            paragraph = [];
        }
    };
    const flushList = () => {
        if (listItems.length) {
            const items = listItems.map((it) => `<li>${renderInlineMarkdown(it)}</li>`).join('');
            html.push(`<${listTag}>${items}</${listTag}>`);
            listItems = [];
            listTag = null;
        }
    };

    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) {
            flushParagraph();
            flushList();
            continue;
        }

        const heading = trimmed.match(/^(#{1,6})\s+(.*)$/);
        const ordered = trimmed.match(/^\d+[.)]\s+(.*)$/);
        const bullet = trimmed.match(/^[-*+]\s+(.*)$/);

        if (heading) {
            flushParagraph();
            flushList();
            const level = Math.min(6, heading[1].length + 2); // # → h3, ## → h4…
            html.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
        } else if (ordered) {
            flushParagraph();
            if (listTag !== 'ol') flushList();
            listTag = 'ol';
            listItems.push(ordered[1]);
        } else if (bullet) {
            flushParagraph();
            if (listTag !== 'ul') flushList();
            listTag = 'ul';
            listItems.push(bullet[1]);
        } else {
            flushList();
            paragraph.push(trimmed);
        }
    }
    flushParagraph();
    flushList();
    return html.join('');
}

// Créer un élément de message
function createMessageElement(text, sender, sources = [], meta = {}) {
    const settings = getSettings();

    const messageDiv = document.createElement('div');
    messageDiv.className = `message message--${sender}`;

    // Score de confiance conservé sur l'élément (utile pour le débogage/CSS).
    if (typeof meta.confidence === 'number') {
        messageDiv.dataset.confidence = String(meta.confidence);
    }

    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message__avatar';
    avatarDiv.textContent = sender === 'user' ? 'U' : 'S';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message__content';

    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'message__bubble';

    // Réponses de l'assistant : rendu Markdown (gras, listes, titres). Messages
    // utilisateur : texte verbatim en paragraphes (pas d'interprétation Markdown).
    if (sender === 'assistant') {
        bubbleDiv.innerHTML = renderMarkdown(text);
    } else {
        text.split('\n').filter((p) => p.trim() !== '').forEach((paragraph) => {
            const p = document.createElement('p');
            p.textContent = paragraph;
            bubbleDiv.appendChild(p);
        });
    }

    contentDiv.appendChild(bubbleDiv);

    // Score de confiance : affiché seulement si l'utilisateur l'a activé
    // (préférence « Afficher le score de confiance » de la page Paramètres).
    if (sender === 'assistant' && settings.showConfidence && typeof meta.confidence === 'number') {
        contentDiv.appendChild(createConfidenceBadge(meta.confidence));
    }

    // Sources : affichées si disponibles et si la préférence « Citer les
    // sources » est active (page Paramètres).
    if (sources.length > 0 && settings.citeSources) {
        const sourcesElement = createSourcesElement(sources);
        contentDiv.appendChild(sourcesElement);
    }

    // Action de signalement sur les réponses de l'assistant (hors messages d'erreur).
    if (sender === 'assistant' && !meta.isError) {
        contentDiv.appendChild(createAssistantActions());
    }

    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);

    return messageDiv;
}

// Barre d'actions d'un message assistant (signalement d'une réponse incorrecte)
function createAssistantActions() {
    const actions = document.createElement('div');
    actions.className = 'message__actions';

    const reportBtn = document.createElement('button');
    reportBtn.type = 'button';
    reportBtn.className = 'message__action';
    reportBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>
        <span>Signaler</span>
    `;
    reportBtn.addEventListener('click', () => openReportPanel(actions, reportBtn));

    actions.appendChild(reportBtn);
    return actions;
}

// Envoi d'un signalement au backend
function openReportPanel(actions, button) {
    if (actions.querySelector('[data-report-panel]')) return;
    button.hidden = true;

    const panel = document.createElement('form');
    panel.className = 'message__report-panel';
    panel.dataset.reportPanel = '';
    panel.innerHTML = `
        <div class="message__report-title">Noter cette réponse</div>
        <div class="message__rating" role="radiogroup" aria-label="Note du signalement">
            ${[1, 2, 3, 4, 5].map((rating) => `
                <label class="message__rating-option">
                    <input type="radio" name="rating" value="${rating}" ${rating === 1 ? 'checked' : ''}>
                    <span>${'★'.repeat(rating)}</span>
                </label>
            `).join('')}
        </div>
        <textarea class="textarea message__report-comment" name="comment" rows="2" placeholder="Ajouter un commentaire optionnel..."></textarea>
        <div class="message__report-actions">
            <button class="btn btn--ghost btn--sm" type="button" data-report-cancel>Annuler</button>
            <button class="btn btn--primary btn--sm" type="submit" data-report-submit>Envoyer</button>
        </div>
    `;

    panel.querySelector('[data-report-cancel]')?.addEventListener('click', () => {
        panel.remove();
        button.hidden = false;
    });

    panel.addEventListener('submit', (event) => {
        event.preventDefault();
        handleReportSubmit(panel, button);
    });

    actions.appendChild(panel);
}

async function handleReportSubmit(panel, button) {
    const submit = panel.querySelector('[data-report-submit]');
    const rating = Number(new FormData(panel).get('rating')) || 1;
    const comment = panel.querySelector('[name="comment"]')?.value.trim() || null;
    if (submit) submit.disabled = true;
    try {
        await reportAnswer({ conversationId: currentConversationId, rating, comment });
        const label = button.querySelector('span');
        if (label) label.textContent = 'Signalé';
        button.hidden = false;
        button.disabled = true;
        panel.remove();
        showToast({
            title: 'Merci',
            text: 'Votre note a été enregistrée pour révision.',
            type: 'success',
        });
    } catch (error) {
        if (submit) submit.disabled = false;
        showToast({
            title: 'Signalement impossible',
            text: messageFromError(error),
            type: 'danger',
        });
    }
}

// Badge de score de confiance d'une réponse (0..1 ou 0..100 normalisés en %).
function createConfidenceBadge(confidence) {
    const pct = Math.round(confidence <= 1 ? confidence * 100 : confidence);
    const clamped = Math.max(0, Math.min(100, pct));
    const level = clamped >= 75 ? 'high' : clamped >= 50 ? 'medium' : 'low';

    const badge = document.createElement('p');
    badge.className = `message__confidence message__confidence--${level}`;
    badge.textContent = `Confiance estimée : ${clamped} %`;
    return badge;
}

// Créer un élément de sources
function createSourcesElement(sources) {
    const sourcesDiv = document.createElement('div');
    sourcesDiv.className = 'sources';

    const label = document.createElement('p');
    label.className = 'sources__label';
    label.textContent = 'Sources';
    sourcesDiv.appendChild(label);

    sources.forEach((source, index) => {
        const sourceChip = document.createElement('div');
        sourceChip.className = 'source-chip';

        const indexSpan = document.createElement('span');
        indexSpan.className = 'source-chip__index';
        indexSpan.textContent = index + 1;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'source-chip__content';

        const title = document.createElement('p');
        title.className = 'source-chip__title';
        title.textContent = source.title;

        const meta = document.createElement('p');
        meta.className = 'source-chip__meta';
        meta.textContent = source.meta;

        contentDiv.appendChild(title);
        contentDiv.appendChild(meta);

        sourceChip.appendChild(indexSpan);
        sourceChip.appendChild(contentDiv);

        sourcesDiv.appendChild(sourceChip);
    });

    return sourcesDiv;
}

// Prépare une bulle d'assistant vide qui recevra le texte au fil du flux SSE.
// Le contenu est re-rendu en Markdown à chaque token (le curseur clignotant est
// replacé à la fin), puis la bulle est finalisée (confiance, sources, actions).
function createStreamingAssistantMessage(chatThread) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message--assistant';

    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'message__avatar';
    avatarDiv.textContent = 'S';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message__content';

    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'message__bubble';
    contentDiv.appendChild(bubbleDiv);

    messageDiv.appendChild(avatarDiv);
    messageDiv.appendChild(contentDiv);
    chatThread.appendChild(messageDiv);

    let buffer = '';

    // Re-rend le Markdown accumulé et repositionne le curseur à la fin (dans le
    // dernier bloc s'il existe, pour un rendu « en ligne » naturel).
    const render = (withCursor) => {
        bubbleDiv.innerHTML = renderMarkdown(buffer);
        if (withCursor) {
            const cursor = document.createElement('span');
            cursor.className = 'stream-cursor';
            const last = bubbleDiv.lastElementChild;
            (last && /^(P|LI|H\d)$/.test(last.tagName) ? last : bubbleDiv).appendChild(cursor);
        }
    };
    render(true);

    return {
        push(delta) {
            buffer += delta;
            render(true);
        },
        finalize({ text, sources = [], confidence, isError = false }) {
            const settings = getSettings();
            if (typeof text === 'string' && text.length) buffer = text;
            render(false); // rendu final, sans curseur

            if (typeof confidence === 'number') messageDiv.dataset.confidence = String(confidence);

            if (!isError && settings.showConfidence && typeof confidence === 'number') {
                contentDiv.appendChild(createConfidenceBadge(confidence));
            }
            if (!isError && sources.length > 0 && settings.citeSources) {
                contentDiv.appendChild(createSourcesElement(sources));
            }
            if (!isError) {
                contentDiv.appendChild(createAssistantActions());
            }
        },
    };
}

// Envoi de la question au backend et rendu de la réponse (streaming SSE).
async function requestAssistantResponse(question) {
    isStreaming = true;

    const chatThread = document.querySelector('.chat-thread__inner');
    const thinkingIndicator = createThinkingIndicator();
    chatThread.appendChild(thinkingIndicator);
    scrollToBottom(true);

    let bubble = null; // créée au 1er token (l'indicateur reste visible jusque-là)
    let buffer = '';

    // Crée la bulle si besoin, en retirant l'indicateur « réfléchit… ».
    const ensureBubble = () => {
        if (!bubble) {
            thinkingIndicator.remove();
            bubble = createStreamingAssistantMessage(chatThread);
        }
        return bubble;
    };

    // Auto-scroll « collant » piloté par un flag : on suit le flux tant que
    // l'utilisateur ne remonte pas. Un écouteur de scroll met à jour `stick`
    // uniquement sur les défilements manuels (les scrolls programmés atterrissent
    // en bas → `isNearBottom()` reste vrai). Robuste face au scroll smooth animé.
    const scroller = getScroller();
    let stick = true;
    const handleScroll = () => { stick = isNearBottom(); };
    scroller?.addEventListener('scroll', handleScroll, { passive: true });

    const followStream = (mutate) => {
        mutate();
        if (stick) scrollToBottom(false);
    };

    try {
        await streamQuestion({
            question,
            conversationId: currentConversationId,
            onMeta: (meta) => {
                // Mémoriser le fil courant pour rattacher les échanges suivants.
                if (meta.conversation_id) currentConversationId = meta.conversation_id;
            },
            onToken: (delta) => {
                buffer += delta;
                followStream(() => ensureBubble().push(delta));
            },
            onDone: ({ sources, confidence }) => {
                followStream(() =>
                    ensureBubble().finalize({ text: buffer, sources: sources || [], confidence }),
                );
            },
        });
    } catch (error) {
        const message = messageFromError(
            error,
            'Le service est momentanément indisponible. Veuillez réessayer.',
        );
        if (bubble) {
            // Une bulle partielle existe déjà : la clôturer proprement en erreur.
            bubble.finalize({ text: buffer || message, isError: true });
        } else {
            thinkingIndicator.remove();
            addAssistantMessage(message, [], { isError: true });
        }
        showToast({ title: 'Échec de la requête', text: message, type: 'danger' });
    } finally {
        scroller?.removeEventListener('scroll', handleScroll);
        thinkingIndicator.remove(); // no-op si déjà retiré
        isStreaming = false;
    }
}

// Indicateur « L'assistant réfléchit… »
function createThinkingIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'thinking-indicator';
    indicator.innerHTML = `
        <div class="thinking-dots">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <span>L'assistant réfléchit...</span>
    `;
    return indicator;
}

// Conteneur réellement scrollable (overflow-y:auto) — c'est `.chat-thread`,
// pas `.chat-thread__inner` (simple wrapper de mise en page).
function getScroller() {
    return document.querySelector('.chat-thread');
}

// Vrai si l'utilisateur est (quasi) en bas du fil — sert à ne PAS le forcer vers
// le bas s'il a remonté volontairement pour relire un message.
function isNearBottom(threshold = 120) {
    const scroller = getScroller();
    if (!scroller) return true;
    return scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight <= threshold;
}

// Défile vers le dernier message. `smooth` pour les actions ponctuelles (envoi
// d'un message) ; défilement instantané pendant le streaming pour suivre le flux
// sans à-coups.
function scrollToBottom(smooth = false) {
    const scroller = getScroller();
    if (!scroller) return;
    scroller.scrollTo({ top: scroller.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
}

// Initialisation automatique si le module est chargé
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initChat);
} else {
    initChat();
}
