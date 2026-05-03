from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_extras import Subscription


def is_subscribed(db: Session, follower_id: str, followed_id: str) -> bool:
    row = db.execute(
        select(Subscription).where(
            Subscription.follower_id == follower_id,
            Subscription.followed_id == followed_id,
        )
    ).scalar_one_or_none()
    return row is not None


def subscribe(db: Session, follower_id: str, followed_id: str) -> bool:
    if follower_id == followed_id:
        return False
    if is_subscribed(db, follower_id, followed_id):
        return True
    db.add(Subscription(follower_id=follower_id, followed_id=followed_id))
    db.commit()
    return True


def unsubscribe(db: Session, follower_id: str, followed_id: str) -> bool:
    row = db.execute(
        select(Subscription).where(
            Subscription.follower_id == follower_id,
            Subscription.followed_id == followed_id,
        )
    ).scalar_one_or_none()
    if not row:
        return True
    db.delete(row)
    db.commit()
    return True
