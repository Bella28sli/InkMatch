from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User

router = APIRouter()


@router.get('')
def list_users(
    role: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    rows = db.execute(stmt.order_by(User.id.asc()).offset(offset).limit(limit)).scalars().all()
    return [
        {
            'id': str(r.id),
            'email': r.email,
            'phone': r.phone,
            'role': r.role.value,
            'is_verified': bool(r.is_verified),
        }
        for r in rows
    ]


@router.get('/{user_id}')
def get_user(user_id: str, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not row:
        return None
    return {
        'id': str(row.id),
        'email': row.email,
        'phone': row.phone,
        'role': row.role.value,
        'is_verified': bool(row.is_verified),
    }
