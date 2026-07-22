from pydantic import BaseModel


class SpeechToTextResponse(BaseModel):
    """Réponse de POST /api/speech-to-text."""

    text: str
