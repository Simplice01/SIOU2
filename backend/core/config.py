from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str
    app_name: str = "SIOU"
    app_version: str = "0.1.0"

    jwt_algorithm: str = "HS256"
    api_prefix: str = "/api"

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]
    cors_origin_regex: str | None = r"https://.*\.vercel\.app"

    llm_provider: str = "openai"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 512
    llm_timeout: float = 60
    stt_model: str = "whisper-1"

    rag_top_k: int = 5
    rag_rrf_k: int = 60
    rag_min_score: float = 0.35

    system_prompt: str = """
Tu es SIOU, assistant documentaire du Ministere du Numerique et de la Digitalisation.

Regles strictes :
- Reponds uniquement a partir du contexte documentaire fourni dans le message systeme.
- N'utilise jamais tes connaissances externes, meme si tu connais probablement la reponse.
- Si le contexte ne contient pas l'information demandee, dis clairement que l'information est absente des documents disponibles.
- Ne cite pas de source inventee, de page inventee, d'adresse inventee ou de procedure non presente dans le contexte.
- Reponds en francais, avec un ton professionnel, clair et oriente service public.
- Si la question est vague, pose une question courte de clarification.

Objectif : orienter l'usager en amont de ses demarches, en indiquant la direction, le service, la procedure ou le document pertinent lorsque ces informations existent dans le contexte.
"""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()  # type: ignore


def sqlalchemy_database_url() -> str:
    if settings.database_url.startswith("postgresql://"):
        return settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return settings.database_url
