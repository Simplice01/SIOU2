"""
Traitement des requêtes de transcription audio : validation de format,
lecture avec limite de taille, et appel à la transcription elle-même.

Séparé de audio_llm.py (qui ne s'occupe que de la transcription via
faster-whisper) pour garder une responsabilité par fichier. Les routes
HTTP (backend/routers/audio.py) ne font qu'appeler ces fonctions et
traduire leurs résultats/exceptions en réponses HTTP.
"""

from pathlib import Path

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from backend.AI.AUDIO.audio_llm import (
    AudioTooLargeError,
    SUPPORTED_FORMATS,
    UnsupportedAudioFormatError,
    process_audio_file,
)
from backend.AI.AUDIO.config_audio import settings_audio

_READ_CHUNK_SIZE = 1024 * 1024  # 1 Mo par lecture


def validate_upload_format(file_name: str | None) -> None:
    """Vérifie que le nom de fichier a une extension audio supportée."""
    file_ext = Path(file_name).suffix.lower() if file_name else ""
    if file_ext not in SUPPORTED_FORMATS:
        raise UnsupportedAudioFormatError(
            f"Format audio non supporté : {file_ext}. "
            f"Formats supportés : {', '.join(SUPPORTED_FORMATS)}"
        )


async def read_audio_with_size_limit(file: UploadFile, max_size_mb: int | None = None) -> bytes:
    """
    Lit le fichier par blocs et rejette (AudioTooLargeError) dès que la
    limite est dépassée, plutôt que de charger un fichier arbitrairement
    gros en mémoire avant de s'apercevoir qu'il est trop volumineux.
    """
    limit_mb = max_size_mb if max_size_mb is not None else settings_audio.max_audio_size_mb
    max_bytes = limit_mb * 1024 * 1024

    chunks = bytearray()
    while True:
        chunk = await file.read(_READ_CHUNK_SIZE)
        if not chunk:
            break
        chunks.extend(chunk)
        if len(chunks) > max_bytes:
            raise AudioTooLargeError(f"Fichier audio trop volumineux (max {limit_mb} Mo).")
    return bytes(chunks)


async def transcribe_synchronously(audio_bytes: bytes, file_name: str, language: str | None = None) -> str:
    """
    Transcrit l'audio et renvoie le texte directement (pas de job_id).

    Exécutée dans un thread à part (via run_in_threadpool) : process_audio_file
    est bloquante (calcul CPU), elle ne doit jamais tourner directement dans
    la boucle d'événements async.
    """
    return await run_in_threadpool(process_audio_file, audio_bytes, file_name, language)
