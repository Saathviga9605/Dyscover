from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.auth.routes import get_current_user
from app.database import get_db
from app.models import Conversation, Message, User
from app.schemas import (
    ConversationResponse,
    ConversationCreate,
    MessageCreate,
    MessageResponse,
    MessageListResponse,
)
from app.services.groq import generate_response

router = APIRouter(prefix="/chat", tags=["lexi-chat"])

@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    _: ConversationCreate | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new conversation for the authenticated user."""
    conv = Conversation(user_id=user.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return ConversationResponse.from_orm(conv)

@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    convs = db.scalars(
        Conversation.__table__.select().where(Conversation.user_id == user.id)
    ).all()
    return [ConversationResponse.from_orm(c) for c in convs]

@router.get("/conversations/{conv_id}", response_model=ConversationResponse)
def get_conversation(conv_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationResponse.from_orm(conv)

@router.delete("/conversations/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conv_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return

@router.get("/conversations/{conv_id}/messages", response_model=MessageListResponse)
def get_messages(conv_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    msgs = conv.messages
    return MessageListResponse(messages=[MessageResponse.from_orm(m) for m in msgs])

@router.post("/conversations/{conv_id}/messages", response_model=MessageResponse)
async def post_message(
    conv_id: UUID,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Add a user message, call Groq, store assistant reply, and return assistant message."""
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    # Store user message
    user_msg = Message(conversation_id=conv.id, role="user", content=payload.content)
    db.add(user_msg)
    db.flush()
    # Prepare recent history for Groq (including system prompt handled in service)
    recent = [
        {"role": "user", "content": m.content}
        for m in conv.messages  # includes the just added user message
        if m.role in ("user", "assistant")
    ]
    # Generate assistant response
    assistant_text = await generate_response(str(user.id), recent)
    assistant_msg = Message(conversation_id=conv.id, role="assistant", content=assistant_text)
    db.add(assistant_msg)
    # Update conversation timestamp
    conv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(assistant_msg)
    return MessageResponse.from_orm(assistant_msg)

