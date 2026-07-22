import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from backend.models.schemas import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    UserRead,
    UserSelfUpdate,
    UserSummary,
)
from backend.models.user_model import User

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)

INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Identifiant ou mot de passe incorrect.",
)

INVALID_REFRESH_TOKEN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Jeton de rafraîchissement invalide ou expiré.",
)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authentification.

    Cherche l'utilisateur par `username`, vérifie son mot de passe (hash bcrypt)
    et qu'il est actif. En cas de succès, renvoie un jeton d'accès (courte durée,
    "type": "access") et un jeton de rafraîchissement (longue durée, "type": "refresh"),
    plus les informations de l'utilisateur. Un seul message d'erreur générique
    (401) est utilisé pour mot de passe incorrect / utilisateur inconnu / inactif,
    pour ne pas révéler quels comptes existent.
    """
    result = await db.execute(select(User).where(User.email == payload.username))
    user = result.scalar_one_or_none()
    if user is None or not bool(user.is_active) or not verify_password(payload.password, str(user.password_hash)):
        raise INVALID_CREDENTIALS

    subject = str(user.id)
    return {
        "access_token": create_access_token(subject), # A ce niveau si on veut ajouter le temps de recharge d'un token au lieu de garder la valeur par défaut qui est de 30min
        "refresh_token": create_refresh_token(subject),
        "token_type": "bearer",
        "user": UserRead.model_validate(user),
    }


@router.post("/refresh")
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """
    Rafraîchit le JWT.

    Décode le jeton de rafraîchissement fourni et vérifie qu'il porte bien
    "type": "refresh" (un jeton d'accès présenté ici est donc rejeté), que
    l'utilisateur existe toujours et est actif, puis émet un nouveau jeton
    d'accès. Le jeton de rafraîchissement n'est pas renouvelé ici.
    """
    try:
        decoded = decode_token(payload.refresh_token)
    except JWTError:
        raise INVALID_REFRESH_TOKEN

    if decoded.get("type") != "refresh":
        raise INVALID_REFRESH_TOKEN

    try:
        user_id = uuid.UUID(decoded.get("sub"))
    except (TypeError, ValueError):
        raise INVALID_REFRESH_TOKEN

    user = await db.get(User, user_id)
    if user is None or not bool(user.is_active):
        raise INVALID_REFRESH_TOKEN

    return {"access_token": create_access_token(str(user.id)), "token_type": "bearer"}


@router.post("/logout")
async def logout():
    """
    Déconnexion.

    Le JWT est un jeton auto-suffisant qui ne peut pas être invalidé côté
    serveur sans une table de sessions/révocation (qui n'existe pas dans le
    schéma actuel). Cet endpoint est donc un no-op : il confirme la
    déconnexion, mais c'est au client de supprimer le jeton. À revoir si
    l'équipe ajoute une gestion de révocation.
    """
    return {"detail": "Déconnexion effectuée"}


@router.get("/me", response_model=UserSummary)
async def current_user(user: User = Depends(get_current_user)):
    """
    Informations utilisateur.

    L'utilisateur est déjà résolu et vérifié par la dépendance
    `get_current_user` (jeton valide, "type": "access", compte actif) ;
    cette fonction n'a plus qu'à le renvoyer.
    """
    return user


@router.patch("/me", response_model=UserSummary)
async def update_current_user(
    payload: UserSelfUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mise à jour du profil par l'utilisateur lui-même.

    Self-service : l'utilisateur courant (résolu par `get_current_user`)
    modifie sa propre identité (prénom / nom). Le rôle et l'état actif ne
    sont volontairement pas modifiables ici — cela reste réservé à un
    administrateur via `PATCH /api/admin/users/{id}`. Seuls les champs
    fournis (non nuls) sont appliqués.
    """
    for field_name in ("first_name", "last_name"):
        value = getattr(payload, field_name)
        if value is not None:
            setattr(user, field_name, value)

    await db.commit()
    await db.refresh(user)
    return user
