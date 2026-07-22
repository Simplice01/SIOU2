/**
 * voice-recorder.js
 * Saisie vocale : enregistrement micro, envoi au backend Speech-to-Text
 * (Whisper ou équivalent), puis insertion du texte transcrit dans le champ
 * de saisie du chat. Le message n'est jamais envoyé automatiquement.
 */

import { qs, uid } from './utils.js';
import { showToast } from './toast.js';
import { API_BASE } from './api.js';

// Adapter cette URL à l'endpoint réel exposé par le backend SIOU.
const TRANSCRIBE_ENDPOINT = `${API_BASE}/speech-to-text`;

let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

/**
 * Initialise le bouton de saisie vocale.
 * @param {HTMLTextAreaElement} composerInput - le textarea déjà utilisé par le composer du chat.
 */
export function initVoiceRecorder(composerInput) {
    const micButton = qs('[data-composer-mic]');
    if (!micButton || !composerInput) {
        console.warn('[voice-recorder] Bouton micro ou champ de saisie introuvable - abandon');
        return;
    }

    if (!isVoiceRecordingSupported()) {
        // Dégradation silencieuse : le chat reste utilisable normalement au clavier.
        micButton.remove();
        console.warn('[voice-recorder] Enregistrement audio non supporté par ce navigateur');
        return;
    }

    micButton.addEventListener('click', () => handleMicClick(micButton, composerInput));
}

function isVoiceRecordingSupported() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
}

async function handleMicClick(micButton, composerInput) {
    if (isRecording) {
        stopRecording(micButton);
        return;
    }
    await startRecording(micButton, composerInput);
}

async function startRecording(micButton, composerInput) {
    let stream;
    try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
        showToast({
            title: 'Micro non accessible',
            text: "L'accès au microphone est nécessaire uniquement pour la saisie vocale. Vous pouvez toujours écrire votre question.",
            type: 'warning',
        });
        return;
    }

    const mimeType = getSupportedMimeType();
    mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.addEventListener('dataavailable', (event) => {
        if (event.data.size > 0) audioChunks.push(event.data);
    });

    mediaRecorder.addEventListener('stop', () => {
        stream.getTracks().forEach((track) => track.stop());
        const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
        transcribeAudio(audioBlob, micButton, composerInput);
    });

    mediaRecorder.start();
    isRecording = true;
    setMicState(micButton, { recording: true });
}

function stopRecording(micButton) {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }
    isRecording = false;
    setMicState(micButton, { recording: false, transcribing: true });
}

/**
 * Sélectionne le meilleur format audio supporté par le navigateur.
 * webm/opus est privilégié (léger, bien supporté par Whisper).
 * Safari (desktop/iOS) ne supporte pas webm : on retombe sur mp4/aac.
 */
function getSupportedMimeType() {
    const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'];
    return candidates.find((type) => MediaRecorder.isTypeSupported(type)) || '';
}

async function transcribeAudio(audioBlob, micButton, composerInput) {
    micButton.disabled = true;

    try {
        const extension = getFileExtension(audioBlob.type);
        const formData = new FormData();
        formData.append('audio', audioBlob, `saisie-vocale-${uid('voice')}.${extension}`);
        // Indication de langue pour améliorer la précision du moteur STT (SIOU est en français).
        formData.append('language', 'fr');

        const response = await fetch(TRANSCRIBE_ENDPOINT, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            let detail = '';
            try {
                const payload = await response.json();
                detail = payload?.detail ? ` : ${payload.detail}` : '';
            } catch {
                detail = '';
            }
            throw new Error(`Réponse serveur invalide (${response.status})${detail}`);
        }

        const data = await response.json();
        const transcript = (data.text || '').trim();

        if (transcript) {
            insertTranscript(composerInput, transcript);
        } else {
            showToast({
                title: 'Aucun texte détecté',
                text: 'Réessayez en parlant clairement près du microphone.',
                type: 'info',
            });
        }
    } catch (err) {
        console.error('[voice-recorder] Échec de la transcription :', err);
        showToast({
            title: 'Transcription impossible',
            text: err?.message || 'Une erreur est survenue. Vous pouvez réessayer ou écrire votre question directement.',
            type: 'danger',
        });
    } finally {
        micButton.disabled = false;
        setMicState(micButton, { recording: false, transcribing: false });
    }
}

function getFileExtension(mimeType) {
    if (mimeType.includes('mp4')) return 'm4a';
    if (mimeType.includes('ogg')) return 'ogg';
    return 'webm';
}

/**
 * Insère le texte transcrit dans le champ de saisie sans jamais envoyer le message.
 * Si l'utilisateur avait déjà commencé à écrire, le texte transcrit est ajouté
 * à la suite plutôt que d'écraser sa saisie.
 */
function insertTranscript(composerInput, transcript) {
    const existing = composerInput.value.trim();
    composerInput.value = existing ? `${existing} ${transcript}` : transcript;
    composerInput.focus();
    composerInput.dispatchEvent(new Event('input', { bubbles: true }));
}

/**
 * Met à jour l'état visuel et accessible du bouton micro.
 */
function setMicState(micButton, { recording, transcribing = false }) {
    micButton.classList.toggle('is-recording', recording);
    micButton.classList.toggle('is-transcribing', transcribing);
    micButton.setAttribute('aria-pressed', String(recording));
    micButton.setAttribute(
        'aria-label',
        recording ? "Arrêter l'enregistrement vocal" : 'Saisie vocale'
    );
}
