from datetime import datetime, timedelta, timezone
import uuid
from uuid import UUID
from secrets import randbelow

from jose import JWTError, jwt
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.enums import CollectionType, UserRole
from app.models.profiles import InkmatchDefaults, MasterProfile, Profile
from app.models.sketches import Collection, FeedPreferredStyle, FeedPreferredTag, Style, Tag
from app.services.collection_service import ensure_inkmatch_collection, ensure_likes_collection, ensure_my_posts_collection
from app.models.locations import MasterWorkplace
from app.models.verification_codes import VerificationCode
from app.models.refresh_token import RefreshToken
from app.models.user import User


def get_user_by_login(db: Session, login: str) -> User | None:
    stmt = select(User).where(or_(User.email == login, User.phone == login))
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_email_or_phone(db: Session, email: str | None, phone: str | None) -> User | None:
    conditions = []
    if email is not None:
        conditions.append(User.email == email)
    if phone is not None:
        conditions.append(User.phone == phone)
    if not conditions:
        return None
    stmt = select(User).where(or_(*conditions))
    return db.execute(stmt).scalar_one_or_none()


def get_profile_by_nickname(db: Session, nickname: str) -> Profile | None:
    normalized = nickname.strip().lower()
    if not normalized:
        return None
    stmt = select(Profile).where(func.lower(Profile.nickname) == normalized)
    return db.execute(stmt).scalar_one_or_none()




def _split_ids_and_names(values: list[str]):
    ids = []
    names = []
    for v in values:
        try:
            ids.append(uuid.UUID(v))
        except Exception:
            names.append(v)
    return ids, names




def _create_base_master_collections(db: Session, user_id):
    base = [
        (CollectionType.portfolio, 'Портфолио', 'Главные работы мастера'),
        (CollectionType.process, 'Процесс', 'Процесс и этапы выполнения работ'),
        (CollectionType.materials, 'Материалы', 'Инструменты и материалы'),
        (CollectionType.find_us, 'Как нас найти', 'Где нас найти и как до нас добраться'),
    ]
    for ctype, title, description in base:
        row = Collection(
            owner_id=user_id,
            collection_type=ctype,
            title=title,
            description=description,
            is_system=True,
            is_private=False,
        )
        db.add(row)

def register_user(
    db: Session,
    email: str | None,
    phone: str | None,
    password: str,
    role: str,
    profile_data: dict,
    preferred_style_ids: list[str],
    preferred_tag_ids: list[str],
    preferences_data: dict | None,
    master_profile_data: dict | None,
    workplace_data: dict | None,
):
    if role not in {r.value for r in UserRole}:
        return None, "invalid_role"
    if get_user_by_email_or_phone(db, email, phone):
        return None, "conflict"
    nickname = (profile_data.get("nickname") or "").strip()
    if not nickname:
        return None, "invalid_profile"
    if get_profile_by_nickname(db, nickname):
        return None, "nickname_conflict"
    try:
        # Validate preferred styles/tags existence
        if len(preferred_style_ids) != 3 or len(preferred_tag_ids) != 3:
            return None, "invalid_preferences"

        style_ids, style_names = _split_ids_and_names(preferred_style_ids)
        tag_ids, tag_names = _split_ids_and_names(preferred_tag_ids)

        styles = []
        if style_ids:
            styles += db.execute(select(Style).where(Style.id.in_(style_ids))).scalars().all()
        if style_names:
            styles += db.execute(select(Style).where(Style.name.in_(style_names))).scalars().all()

        tags = []
        if tag_ids:
            tags += db.execute(select(Tag).where(Tag.id.in_(tag_ids))).scalars().all()
        if tag_names:
            tags += db.execute(select(Tag).where(Tag.name.in_(tag_names))).scalars().all()

        styles = {s.id for s in styles}
        tags = {t.id for t in tags}
        if len(styles) != 3 or len(tags) != 3:
            return None, "invalid_preferences"

        preferred_style_ids = [str(s) for s in styles]
        preferred_tag_ids = [str(t) for t in tags]

        user = User(
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            role=role,
            is_verified=not bool(email),
        )
        db.add(user)
        db.flush()

        profile = Profile(user_id=user.id, **profile_data)
        db.add(profile)

        ensure_likes_collection(db, str(user.id))
        ensure_my_posts_collection(db, str(user.id))
        ensure_inkmatch_collection(db, str(user.id))

        for style_id in preferred_style_ids:
            db.add(FeedPreferredStyle(user_id=user.id, style_id=style_id))
        for tag_id in preferred_tag_ids:
            db.add(FeedPreferredTag(user_id=user.id, tag_id=tag_id))

        if preferences_data:
            db.add(InkmatchDefaults(user_id=user.id, **preferences_data))

        if role == UserRole.master.value:
            if not master_profile_data or master_profile_data.get("experience_years") is None:
                return None, "missing_master_profile"
            db.add(MasterProfile(user_id=user.id, **master_profile_data))
            _create_base_master_collections(db, user.id)
            if workplace_data:
                db.add(MasterWorkplace(master_id=user.id, **workplace_data))

        db.commit()
        db.refresh(user)
        return user, None
    except Exception:
        db.rollback()
        raise


def login_user(db: Session, login: str, password: str):
    user = get_user_by_login(db, login)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def issue_tokens(db: Session, user: User):
    access_token, exp_ts = create_access_token(user.id, user.role.value)
    refresh_token, jti, exp_dt = create_refresh_token(user.id)
    db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=exp_dt))
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": settings.access_token_ttl_minutes * 60,
    }


def refresh_access_token(db: Session, refresh_token: str):
    try:
        payload = jwt.decode(
            refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None
    if payload.get("type") != "refresh":
        return None

    jti = payload.get("jti")
    user_id = payload.get("sub")
    if not jti or not user_id:
        return None

    stmt = select(RefreshToken).where(RefreshToken.jti == jti)
    token_row = db.execute(stmt).scalar_one_or_none()
    if not token_row or token_row.revoked:
        return None

    if token_row.expires_at < datetime.now(timezone.utc):
        return None

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        return None
    stmt_user = select(User).where(User.id == user_uuid)
    user = db.execute(stmt_user).scalar_one_or_none()
    if not user:
        return None
    access_token, _exp_ts = create_access_token(user_id, user.role)
    return {
        "access_token": access_token,
        "expires_in": settings.access_token_ttl_minutes * 60,
    }


def revoke_refresh_token(db: Session, refresh_token: str) -> bool:
    try:
        payload = jwt.decode(
            refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return False
    if payload.get("type") != "refresh":
        return False
    jti = payload.get("jti")
    if not jti:
        return False
    stmt = select(RefreshToken).where(RefreshToken.jti == jti)
    token_row = db.execute(stmt).scalar_one_or_none()
    if not token_row:
        return False
    token_row.revoked = True
    db.commit()
    return True


def create_verification_code(db: Session, user: User, channel: str) -> str:
    code = f"{randbelow(1000000):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.verification_code_ttl_minutes
    )
    db.add(
        VerificationCode(
            user_id=user.id,
            channel=channel,
            code=code,
            expires_at=expires_at,
        )
    )
    db.commit()
    return code


def confirm_verification_code(db: Session, user: User, channel: str, code: str) -> bool:
    stmt = (
        select(VerificationCode)
        .where(
            VerificationCode.user_id == user.id,
            VerificationCode.channel == channel,
            VerificationCode.code == code,
            VerificationCode.used_at.is_(None),
        )
        .order_by(VerificationCode.created_at.desc())
    )
    row = db.execute(stmt).scalar_one_or_none()
    if not row:
        return False
    if row.expires_at < datetime.now(timezone.utc):
        return False
    row.used_at = datetime.now(timezone.utc)
    user.is_verified = True
    db.commit()
    return True
