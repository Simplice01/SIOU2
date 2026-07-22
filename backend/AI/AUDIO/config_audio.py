from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings_Audio(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Taille du modèle Whisper local (tiny, base, small, medium, large-v3) :
    # plus gros = plus précis mais plus lent/gourmand en mémoire. "small" est
    # un bon compromis pour du français sur CPU.
    whisper_model_size: str = "small"
    whisper_device: str = "cpu"
    # int8 = quantification légère, adaptée au CPU (rapide, peu de mémoire).
    whisper_compute_type: str = "int8"
    whisper_language: str = "fr"
    # Limite de taille pour un enregistrement de question orale (pas conçu
    # pour transcrire de longs fichiers) — au-delà, la requête est rejetée
    # avant même d'être entièrement chargée en mémoire.
    max_audio_size_mb: int = 10


settings_audio = Settings_Audio()  # type: ignore
