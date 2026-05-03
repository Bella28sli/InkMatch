from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.messaging import Chat, ChatParticipant


def get_or_create_direct_chat(db: Session, user_a_id: str, user_b_id: str) -> Chat:
    user_a_uuid = UUID(str(user_a_id))
    user_b_uuid = UUID(str(user_b_id))

    existing = db.execute(
        select(Chat)
        .join(ChatParticipant, ChatParticipant.chat_id == Chat.id)
        .where(ChatParticipant.user_id == user_a_uuid)
    ).scalars().all()

    for chat in existing:
        participants = db.execute(
            select(ChatParticipant.user_id).where(ChatParticipant.chat_id == chat.id)
        ).scalars().all()
        participant_ids = {str(p) for p in participants}
        if participant_ids == {str(user_a_uuid), str(user_b_uuid)}:
            return chat

    chat = Chat(created_by_user_id=user_a_uuid)
    db.add(chat)
    db.flush()

    db.add(ChatParticipant(chat_id=chat.id, user_id=user_a_uuid))
    db.add(ChatParticipant(chat_id=chat.id, user_id=user_b_uuid))
    db.flush()
    return chat


def is_chat_participant(db: Session, chat_id: str, user_id: str) -> bool:
    chat_uuid = UUID(str(chat_id))
    user_uuid = UUID(str(user_id))
    row = db.execute(
        select(ChatParticipant).where(
            ChatParticipant.chat_id == chat_uuid,
            ChatParticipant.user_id == user_uuid,
        )
    ).scalar_one_or_none()
    return row is not None
