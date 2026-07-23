"""Dépendances FastAPI pour l'authentification et le contrôle d'accès par rôle.

`get_current_user` est prévue pour être utilisée avec `Depends(...)` sur
toute route nécessitant un utilisateur connecté ; `require_role(...)`
s'appuie dessus pour en plus restreindre une route à certains rôles
(ex. "admin").
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import decode_token
from backend.models.user_model import User, normalize_role

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Résout l'utilisateur authentifié à partir de l'en-tête `Authorization: Bearer <token>`.

    Décode et vérifie le JWT, le rejette si ce n'est pas un jeton d'accès
    (un jeton de rafraîchissement ne doit jamais donner accès à l'API à lui
    seul), charge l'utilisateur correspondant en base, et rejette les
    comptes inactifs/supprimés. Lève un 401 à chaque étape d'échec, sans
    distinguer « jeton invalide » de « utilisateur inconnu/inactif » (pour
    ne pas révéler l'état des comptes).
    """
    invalid_token_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Jeton invalide ou expiré.",
    )

    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise invalid_token_error

    if payload.get("type") != "access":
        raise invalid_token_error

    try:
        user_id = uuid.UUID(payload.get("sub"))
    except (TypeError, ValueError):
        raise invalid_token_error

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable ou inactif.",
        )

    return user


def require_role(*allowed_roles: str):
    """
    Construit une dépendance qui n'autorise que les rôles donnés (ex. `require_role("admin")`).

    À utiliser comme `Depends(require_role("admin", "validator"))` sur une
    route. Exécute d'abord `get_current_user`, donc un jeton invalide/absent
    est déjà rejeté (401) avant même que le contrôle de rôle (403) n'entre
    en jeu.
    """

    normalized_allowed_roles = {normalize_role(role) for role in allowed_roles}

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if normalize_role(current_user.role) not in normalized_allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé pour ce rôle.",
            )
        return current_user

    return dependency


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dépendance restreignant une route aux administrateurs, via la méthode
    `is_admin()` du modèle (centralisée ici plutôt que de comparer
    `current_user.role == "admin"` à chaque endroit où c'est nécessaire).
    """
    if not current_user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs.",
        )
    return current_user
