"""Lexi conversation endpoints. Every conversation is owned by exactly one user;
other users receive 404 for its ID."""


from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.chat.schemas import (
    ChatStatusResponse,
    ConversationCreate,
    ConversationResponse,
    ExchangeResponse,
    MessageCreate,
    MessageListResponse,
    MessageResponse,
)
from app.chat.service import LexiError, build_prompt, get_provider, provider_status
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.time import utcnow
from app.database import get_db
from app.models import Conversation, Message, User

router = APIRouter(prefix="/api/chat", tags=["lexi-chat"])
_settings = get_settings()
MAX_CONVERSATIONS_PER_USER = 200


def _owned_conversation(db: Session, user: User, conversation_id: UUID) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.get("/status", response_model=ChatStatusResponse)
def chat_status(_: User = Depends(get_current_user)) -> dict:
    return provider_status()


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(payload: ConversationCreate | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Conversation:
    count = len(db.scalars(select(Conversation.id).where(Conversation.user_id == user.id)).all())
    if count >= MAX_CONVERSATIONS_PER_USER:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conversation limit reached; delete older conversations first")
    conversation = Conversation(user_id=user.id, title=(payload.title.strip() or None) if payload and payload.title else None)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Conversation]:
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc(), Conversation.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Conversation:
    return _owned_conversation(db, user, conversation_id)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    conversation = _owned_conversation(db, user, conversation_id)
    db.delete(conversation)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
def list_messages(
    conversation_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    before: datetime | None = Query(default=None, description="Return messages created before this timestamp (pagination)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageListResponse:
    conversation = _owned_conversation(db, user, conversation_id)
    query = select(Message).where(Message.conversation_id == conversation.id)
    if before is not None:
        query = query.where(Message.created_at < before.replace(tzinfo=None))
    rows = list(db.scalars(query.order_by(Message.created_at.desc()).limit(limit + 1)))
    has_more = len(rows) > limit
    rows = list(reversed(rows[:limit]))
    return MessageListResponse(messages=[MessageResponse.model_validate(row) for row in rows], has_more=has_more)


def _existing_exchange(db: Session, conversation: Conversation, client_message_id: UUID) -> ExchangeResponse | None:
    user_message = db.get(Message, client_message_id)
    if user_message is None:
        return None
    if user_message.conversation_id != conversation.id or user_message.role != "user":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="client_message_id was already used")
    reply = db.scalar(
        select(Message)
        .where(Message.conversation_id == conversation.id, Message.role == "assistant", Message.created_at >= user_message.created_at, Message.id != user_message.id)
        .order_by(Message.created_at)
        .limit(1)
    )
    if reply is None:
        return None
    return ExchangeResponse(
        conversation=ConversationResponse.model_validate(conversation),
        user_message=MessageResponse.model_validate(user_message),
        assistant_message=MessageResponse.model_validate(reply),
    )


@router.post("/conversations/{conversation_id}/messages", response_model=ExchangeResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(_settings.rate_limit_chat)
def post_message(
    conversation_id: UUID,
    payload: MessageCreate,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExchangeResponse:
    """Send a message and return Lexi's model-generated reply.

    Nothing is written until the provider has answered, so a failed call leaves
    the conversation unchanged and the client can safely retry.
    """
    conversation = _owned_conversation(db, user, conversation_id)
    if payload.client_message_id is not None:
        existing = _existing_exchange(db, conversation, payload.client_message_id)
        if existing is not None:
            response.status_code = status.HTTP_200_OK
            return existing

    history = [(message.role, message.content) for message in conversation.messages]
    # Release the read transaction before the (potentially slow) provider call.
    db.commit()
    try:
        provider = get_provider()
        reply_text = provider.complete(build_prompt(history, payload.content))
    except LexiError as error:
        raise HTTPException(status_code=error.status_code, detail={"code": error.code, "message": error.message})

    now = utcnow()
    user_message = Message(conversation_id=conversation.id, role="user", content=payload.content, created_at=now)
    if payload.client_message_id is not None:
        user_message.id = payload.client_message_id
    assistant_message = Message(conversation_id=conversation.id, role="assistant", content=reply_text, model=provider.model, created_at=utcnow())
    if assistant_message.created_at <= now:
        # Keep a strict ordering even on clocks with coarse resolution.
        assistant_message.created_at = now + timedelta(microseconds=1)
    conversation = db.get(Conversation, conversation.id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if not conversation.title:
        conversation.title = payload.content[:60] + ("…" if len(payload.content) > 60 else "")
    conversation.updated_at = assistant_message.created_at
    db.add_all([user_message, assistant_message])
    db.commit()
    db.refresh(conversation)
    return ExchangeResponse(
        conversation=ConversationResponse.model_validate(conversation),
        user_message=MessageResponse.model_validate(user_message),
        assistant_message=MessageResponse.model_validate(assistant_message),
    )
