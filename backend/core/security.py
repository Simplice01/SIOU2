from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from backend.core.config import settings




pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET_KEY = settings.jwt_secret_key
JWT_ALGORITHM = settings.jwt_algorithm


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Jeton de courte durée (30 min par défaut), envoyé à chaque requête API."""
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=30))
    payload = {"sub": subject, "type": "access", "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Jeton de longue durée (7 jours par défaut), utilisé uniquement pour obtenir un nouveau jeton d'accès.

    La claim "type" est ce qui permet à /api/auth/refresh de rejeter un
    jeton d'accès présenté à la place d'un jeton de rafraîchissement, et à
    get_current_user de rejeter un jeton de rafraîchissement présenté à la
    place d'un jeton d'accès.
    """
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=7))
    payload = {"sub": subject, "type": "refresh", "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Décode et vérifie la signature/l'expiration d'un JWT. Lève jose.JWTError si invalide."""
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

"""
def build_llm_headers() -> dict[str, str]:
    return {
        "X-LLM-Provider": settings.llm_provider,
        "X-LLM-Model": settings.llm_model,
    }
    """