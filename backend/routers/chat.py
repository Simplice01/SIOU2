import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.deps import get_current_user
from backend.models.conversation_models import Conversation, Message, MessageSource
from backend.models.schemas import ChatRequest, ChatResponse, SourceCitation
from backend.models.user_model import User
from backend.services.llm import LLMError, generate_answer, stream_answer
from backend.services.rag import retrieve_context

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# Réponse de refus quand aucune source documentaire fiable n'est trouvée : SIOU ne
# répond qu'à partir du corpus officiel (« aucune réponse sans document source »).
REFUSAL_TEXT = (
    "Je ne dispose pas d'un document officiel permettant de répondre de manière "
    "fiable à cette question. Reformulez-la ou consultez un service compétent."
)


def _best_similarity(context: list[dict]) -> float | None:
    """Meilleure similarité cosinus [0,1] parmi les chunks récupérés (None si aucun)."""
    scores = [c["similarity"] for c in context if c.get("similarity") is not None]
    return max(scores) if scores else None


def _confidence(best_similarity: float | None) -> float:
    """Confiance = meilleure similarité cosinus des sources, bornée à [0,1].

    Remplace l'ancienne heuristique (fonction du *nombre* de sources) par une
    mesure calibrée et interprétable de la pertinence documentaire réelle.
    """
    if best_similarity is None:
        return 0.0
    return round(max(0.0, min(1.0, best_similarity)), 2)


def _build_sources(cited: list[dict]) -> list[SourceCitation]:
    """Construit les citations affichables à partir des chunks retenus."""
    return [
        SourceCitation(
            title=chunk["title"],
            meta=chunk["meta"],
            document_id=chunk["document_id"],
            score=round(chunk["similarity"], 4) if chunk.get("similarity") is not None else None,
        )
        for chunk in cited
    ]


async def _resolve_conversation(payload: ChatRequest, db: AsyncSession, current_user: User) -> Conversation:
    """Rattache la question à une conversation existante (contrôle d'appartenance) ou en crée une."""
    if payload.conversation_id is not None:
        conversation = await db.get(Conversation, payload.conversation_id)
        if conversation is None or (
            conversation.user_id != current_user.id and current_user.role != "admin"
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation introuvable")
    else:
        conversation = Conversation(user_id=current_user.id, title=payload.question[:80])
        db.add(conversation)
        await db.flush()  # attribue conversation.id sans clore la transaction
    return conversation


def _persist_sources(db: AsyncSession, message_id, cited: list[dict]) -> None:
    """Rattache les chunks cités au message IA (`message_sources`)."""
    for chunk in cited:
        db.add(
            MessageSource(
                message_id=message_id,
                chunk_id=chunk["chunk_id"],
                similarity_score=chunk.get("similarity"),
            )
        )


@router.post("", response_model=ChatResponse)
async def ask_question(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    """
    Reçoit une question, récupère le contexte documentaire (recherche hybride
    pgvector), génère une réponse via le LLM, puis persiste la conversation, les
    messages et les sources citées. Variante **non streamée** (réponse complète en
    une fois) ; voir `POST /api/chat/stream` pour l'affichage au fil de l'eau.
    """
    conversation = await _resolve_conversation(payload, db, current_user)

    # Enregistrer la question (message humain)
    db.add(Message(conversation_id=conversation.id, sender_type="human", content=payload.question))

    # Récupérer le contexte documentaire (recherche hybride ; dégrade en [] si indisponible)
    context = await retrieve_context(payload.question, top_k=settings.rag_top_k, rrf_k=settings.rag_rrf_k)
    best_similarity = _best_similarity(context)

    # Confidence gate. On refuse (sans appel LLM ni citation) si aucune source OU si
    # la meilleure similarité cosinus reste sous le seuil `rag_min_score` : mieux vaut
    # avouer l'absence de document fiable que d'inventer une réponse.
    passes_gate = best_similarity is not None and best_similarity >= settings.rag_min_score

    if not passes_gate:
        answer = {
            "text": REFUSAL_TEXT,
            "model": settings.llm_model,
            "prompt_tokens": None,
            "completion_tokens": None,
            "latency_ms": None,
        }
        cited: list[dict] = []
    else:
        cited = context
        try:
            answer = await generate_answer(payload.question, [chunk["content"] for chunk in context])
        except LLMError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service de génération indisponible. Réessayez plus tard.",
            ) from exc

    # Persister la réponse (message IA) puis les sources citées
    ia_message = Message(
        conversation_id=conversation.id,
        sender_type="ia",
        content=answer["text"],
        model_used=answer["model"],
        prompt_tokens=answer.get("prompt_tokens"),
        completion_tokens=answer.get("completion_tokens"),
        latency_ms=answer.get("latency_ms"),
    )
    db.add(ia_message)
    await db.flush()  # attribue ia_message.id pour les MessageSource
    _persist_sources(db, ia_message.id, cited)
    await db.commit()

    return ChatResponse(
        text=answer["text"],
        sources=_build_sources(cited),
        confidence=_confidence(best_similarity),
        model=answer["model"],
        conversation_id=conversation.id,
    )


def _sse(event: str, data: dict) -> str:
    """Sérialise un évènement Server-Sent Events (données en JSON, échappement sûr)."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def ask_question_stream(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Version **streamée** (Server-Sent Events) de `POST /api/chat` : les tokens du
    LLM sont renvoyés au fil de l'eau pour un affichage progressif côté client.

    Séquence d'évènements SSE :
      - `meta`  : `{conversation_id}` (connu immédiatement) ;
      - `token` : `{delta}` pour chaque fragment de texte ;
      - `done`  : `{sources, confidence, model}` en fin de génération ;
      - `error` : `{detail}` si le LLM devient indisponible en cours de flux.

    La validation (404 conversation) a lieu **avant** le flux (le client obtient un
    vrai code d'erreur). La question, le message IA et les citations sont ensuite
    persistés **en une seule transaction** à la fin du flux, via la session injectée
    (encore ouverte pendant le streaming, fermée seulement après). En cas d'échec de
    génération en cours de route, rien n'est committé (la question n'est pas enregistrée).
    """
    conversation = await _resolve_conversation(payload, db, current_user)
    db.add(Message(conversation_id=conversation.id, sender_type="human", content=payload.question))

    context = await retrieve_context(payload.question, top_k=settings.rag_top_k, rrf_k=settings.rag_rrf_k)
    best_similarity = _best_similarity(context)
    passes_gate = best_similarity is not None and best_similarity >= settings.rag_min_score
    cited = context if passes_gate else []

    conversation_id = conversation.id  # disponible (flush pour une nouvelle conv, connu sinon)
    confidence = _confidence(best_similarity)
    sources_payload = [source.model_dump(mode="json") for source in _build_sources(cited)]

    async def event_stream():
        yield _sse("meta", {"conversation_id": str(conversation_id)})

        parts: list[str] = []
        if not passes_gate:
            parts.append(REFUSAL_TEXT)
            yield _sse("token", {"delta": REFUSAL_TEXT})
        else:
            try:
                async for delta in stream_answer(payload.question, [chunk["content"] for chunk in context]):
                    parts.append(delta)
                    yield _sse("token", {"delta": delta})
            except LLMError:
                # Échec de génération : on abandonne la transaction (rollback à la
                # fermeture de session). Le client réaffiche l'erreur et peut réessayer.
                await db.rollback()
                yield _sse("error", {"detail": "Service de génération indisponible. Réessayez plus tard."})
                return

        # Persistance finale (question + message IA + citations) en une transaction.
        ia_message = Message(
            conversation_id=conversation_id,
            sender_type="ia",
            content="".join(parts),
            model_used=settings.llm_model,
        )
        db.add(ia_message)
        await db.flush()
        _persist_sources(db, ia_message.id, cited)
        await db.commit()

        yield _sse("done", {"sources": sources_payload, "confidence": confidence, "model": settings.llm_model})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
