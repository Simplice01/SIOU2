"""
Module de transcription audio, via faster-whisper (réimplémentation open
source et locale du modèle Whisper d'OpenAI). Tourne entièrement sur la
machine du serveur : gratuit, sans clé API, aucune donnée audio envoyée
à un tiers — cohérent avec le choix d'auto-hébergement déjà fait pour le
LLM (Ollama).
"""

import os
import tempfile
from pathlib import Path
from typing import Optional

try:
    from faster_whisper import WhisperModel
except ModuleNotFoundError:
    WhisperModel = None

from .config_audio import settings_audio

SUPPORTED_FORMATS = [".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg"]


class AudioProcessingError(Exception):
    """Exception de base levée en cas d'erreur de traitement audio."""


class UnsupportedAudioFormatError(AudioProcessingError):
    """Format de fichier audio non supporté."""


class AudioTooLargeError(AudioProcessingError):
    """Fichier audio dépassant la taille maximale autorisée."""


_model = None


def get_model():
    """
    Charge le modèle Whisper une seule fois (singleton paresseux) puis le
    réutilise à chaque appel — le chargement du modèle est l'étape la plus
    coûteuse, on ne veut pas la refaire à chaque transcription.
    """
    global _model
    if WhisperModel is None:
        raise AudioProcessingError("Transcription audio indisponible : faster-whisper n'est pas installe.")
    if _model is None:
        _model = WhisperModel(
            settings_audio.whisper_model_size,
            device=settings_audio.whisper_device,
            compute_type=settings_audio.whisper_compute_type,
        )
    return _model


def validate_audio_file(audio_path: str) -> None:
    """
    Vérifie que le fichier audio existe et a un format supporté.

    Raises:
        AudioProcessingError: si le fichier n'existe pas ou le format n'est pas supporté
    """
    if not os.path.exists(audio_path):
        raise AudioProcessingError(f"Fichier audio introuvable : {audio_path}")

    file_ext = Path(audio_path).suffix.lower()
    if file_ext not in SUPPORTED_FORMATS:
        raise UnsupportedAudioFormatError(
            f"Format audio non supporté : {file_ext}. "
            f"Formats supportés : {', '.join(SUPPORTED_FORMATS)}"
        )


def transcribe_audio_file(audio_path: str, language: Optional[str] = None) -> str:
    """
    Transcrit un fichier audio en texte avec le modèle Whisper local.

    Args:
        audio_path: chemin vers le fichier audio
        language: code langue (ex. "fr") ; par défaut settings_audio.whisper_language

    Returns:
        Le texte transcrit

    Raises:
        AudioProcessingError: si la transcription échoue
    """
    validate_audio_file(audio_path)

    try:
        model = get_model()
        segments, _info = model.transcribe(
            audio_path,
            language=language or settings_audio.whisper_language,
        )
        text = " ".join(segment.text.strip() for segment in segments)
        return text.strip()
    except AudioProcessingError:
        raise
    except Exception as e:
        raise AudioProcessingError(f"Échec de la transcription audio : {e}")


def process_audio_file(
    audio_file: bytes,
    file_name: str,
    language: Optional[str] = None,
) -> str:
    """
    Fonction principale : reçoit le contenu binaire d'un fichier audio,
    l'écrit dans un fichier temporaire, le transcrit, puis nettoie le
    fichier temporaire.

    Fonction volontairement synchrone (le modèle Whisper local est du
    calcul CPU bloquant) : à appeler depuis une tâche de fond
    (BackgroundTasks), jamais directement dans une route async, pour ne
    pas bloquer la boucle d'événements pendant la transcription.

    Args:
        audio_file: contenu binaire du fichier audio
        file_name: nom du fichier (utilisé pour déduire le format)
        language: code langue (optionnel, défaut : settings_audio.whisper_language)

    Returns:
        Le texte transcrit

    Raises:
        AudioProcessingError: si le traitement échoue
    """
    file_ext = Path(file_name).suffix.lower()
    if file_ext not in SUPPORTED_FORMATS:
        raise UnsupportedAudioFormatError(
            f"Format audio non supporté : {file_ext}. "
            f"Formats supportés : {', '.join(SUPPORTED_FORMATS)}"
        )

    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as temp_file:
        temp_file.write(audio_file)
        temp_path = temp_file.name

    try:
        return transcribe_audio_file(temp_path, language=language)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
