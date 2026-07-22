"""Tests pour backend/routers/audio.py (POST /api/speech-to-text).

URL, nom de champ ("audio") et forme de la réponse ({"text": ...})
alignés sur frontend/assets/js/modules/voice-recorder.js (déjà écrit et
fusionné), pour éviter d'avoir à le modifier.

La vraie transcription (faster-whisper) est remplacée par un mock ici :
exécuter un vrai modèle Whisper à chaque test serait lent et
téléchargerait des poids depuis internet au premier lancement. Le
fonctionnement réel du modèle (téléchargement, chargement, inférence) a
été vérifié manuellement en dehors de cette suite automatisée.
"""

import backend.AI.AUDIO.audio_jobs as audio_jobs
from backend.AI.AUDIO.audio_llm import AudioProcessingError


async def test_speech_to_text_returns_transcribed_text(client, monkeypatch):
    monkeypatch.setattr(
        audio_jobs,
        "process_audio_file",
        lambda audio_file, file_name, language=None: "Bonjour, ceci est un test.",
    )

    response = await client.post(
        "/api/speech-to-text",
        data={"language": "fr"},
        files={"audio": ("test.wav", b"fake-audio-bytes", "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "Bonjour, ceci est un test."}


async def test_speech_to_text_without_language_field(client, monkeypatch):
    monkeypatch.setattr(
        audio_jobs,
        "process_audio_file",
        lambda audio_file, file_name, language=None: "Sans langue précisée.",
    )

    response = await client.post(
        "/api/speech-to-text",
        files={"audio": ("test.wav", b"fake-audio-bytes", "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "Sans langue précisée."}


async def test_speech_to_text_transcription_failure_returns_500(client, monkeypatch):
    def _raise(audio_file, file_name, language=None):
        raise AudioProcessingError("échec simulé")

    monkeypatch.setattr(audio_jobs, "process_audio_file", _raise)

    response = await client.post(
        "/api/speech-to-text",
        files={"audio": ("test.wav", b"fake-audio-bytes", "audio/wav")},
    )

    assert response.status_code == 500


async def test_speech_to_text_unsupported_format_is_rejected(client):
    response = await client.post(
        "/api/speech-to-text",
        files={"audio": ("document.txt", b"pas de l'audio", "text/plain")},
    )

    assert response.status_code == 400


async def test_speech_to_text_oversized_audio_is_rejected(client, monkeypatch):
    monkeypatch.setattr(audio_jobs.settings_audio, "max_audio_size_mb", 1)
    oversized_payload = b"x" * (2 * 1024 * 1024)  # 2 Mo, au-delà de la limite fixée ci-dessus

    response = await client.post(
        "/api/speech-to-text",
        files={"audio": ("test.wav", oversized_payload, "audio/wav")},
    )

    assert response.status_code == 413
