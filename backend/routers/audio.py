"""Route HTTP pour la transcription audio.

Toute la logique de traitement (validation de format, lecture avec
limite de taille, transcription) vit dans backend/AI/AUDIO/ — ce fichier
ne fait que parser la requête et traduire les résultats/exceptions du
module audio en réponse HTTP.

URL (/api/speech-to-text), nom de champ ("audio") et forme de la réponse
({"text": ...}) alignés sur frontend/assets/js/modules/voice-recorder.js
(déjà écrit et fusionné), pour ne pas avoir à le modifier.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from backend.AI.AUDIO.audio_jobs import read_audio_with_size_limit, transcribe_synchronously, validate_upload_format
from backend.AI.AUDIO.audio_llm import AudioProcessingError, AudioTooLargeError, UnsupportedAudioFormatError
from backend.models.schemas import SpeechToTextResponse

router = APIRouter(prefix="/api", tags=["Audio"])


@router.post("/speech-to-text", response_model=SpeechToTextResponse)
async def speech_to_text(audio: UploadFile = File(...), language: str | None = Form(None)):
    """Reçoit un fichier audio et renvoie directement le texte transcrit."""
    try:
        validate_upload_format(audio.filename)
    except UnsupportedAudioFormatError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    try:
        audio_bytes = await read_audio_with_size_limit(audio)
    except AudioTooLargeError as e:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(e))

    try:
        text = await transcribe_synchronously(audio_bytes, audio.filename, language)
    except AudioProcessingError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return SpeechToTextResponse(text=text)
