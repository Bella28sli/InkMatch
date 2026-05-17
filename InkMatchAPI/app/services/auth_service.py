from datetime import datetime, timedelta, timezone
import uuid
from uuid import UUID
from secrets import randbelow, token_urlsafe

from jose import JWTError, jwt
from sqlalchemy import delete, func, or_, select
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
from app.models.pending_registration import PendingRegistration
from app.models.verification_codes import VerificationCode
from app.models.refresh_token import RefreshToken
from app.models.messaging import Notification, NotificationLink, UserPushToken
from app.models.user import User


STYLE_ALIASES = {
    'abstract': 'абстракция',
    'blackgray': 'блэк-н-грэй',
    'blackwork': 'блэкворк',
    'fineline': 'лайнворк',
    'nature': 'ботаника',
    'neotrad': 'нео-традишнл',
    'oldschool': 'олдскул',
    'realism': 'реализм',
    'trashpolka': 'трэш-полька',
}

TAG_ALIASES = {
    'animals': 'животные',
    'anime': 'аниме',
    'cyberpunk': 'мистика',
    'flowers': 'цветы',
    'gothic': 'готика',
    'lettering': 'тату-эскиз',
    'mini': 'мини',
    'ornamental': 'орнамент',
    'zodiac': 'зодиак',
}


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


def _normalize_preference_aliases(values: list[str], aliases: dict[str, str]) -> list[str]:
    normalized: list[str] = []
    for raw in values:
        value = raw.strip().lower()
        if not value:
            continue
        normalized.append(aliases.get(value, value))
    return normalized


def _pending_registration_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=24)


def _create_pending_registration(
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
) -> PendingRegistration:
    pending = PendingRegistration(
        token=token_urlsafe(32),
        email=email,
        phone=phone,
        password_hash=hash_password(password),
        role=role,
        profile_data=profile_data,
        preferred_style_ids=preferred_style_ids,
        preferred_tag_ids=preferred_tag_ids,
        preferences_data=preferences_data,
        master_profile_data=master_profile_data,
        workplace_data=workplace_data,
        expires_at=_pending_registration_expiry(),
    )
    db.add(pending)
    db.commit()
    db.refresh(pending)
    return pending


def _cleanup_pending_registration(db: Session, pending: PendingRegistration) -> None:
    db.delete(pending)
    db.commit()


def _finalize_pending_registration(db: Session, pending: PendingRegistration) -> User | None:
    role = pending.role
    if role not in {r.value for r in UserRole}:
        _cleanup_pending_registration(db, pending)
        return None
    nickname = (pending.profile_data.get('nickname') or '').strip()
    if not nickname or get_profile_by_nickname(db, nickname):
        _cleanup_pending_registration(db, pending)
        return None
    user = User(
        email=pending.email,
        phone=pending.phone,
        password_hash=pending.password_hash,
        role=role,
        is_verified=True if pending.email else False,
    )
    db.add(user)
    db.flush()
    db.add(Profile(user_id=user.id, **pending.profile_data))
    ensure_likes_collection(db, str(user.id))
    ensure_my_posts_collection(db, str(user.id))
    ensure_inkmatch_collection(db, str(user.id))
    for style_id in pending.preferred_style_ids:
        db.add(FeedPreferredStyle(user_id=user.id, style_id=style_id, weight=1))
    for tag_id in pending.preferred_tag_ids:
        db.add(FeedPreferredTag(user_id=user.id, tag_id=tag_id, weight=1))
    if pending.preferences_data:
        db.add(InkmatchDefaults(user_id=user.id, **pending.preferences_data))
    if role == UserRole.master.value:
        if not pending.master_profile_data or pending.master_profile_data.get('experience_years') is None:
            _cleanup_pending_registration(db, pending)
            return None
        db.add(MasterProfile(user_id=user.id, **pending.master_profile_data))
        _create_base_master_collections(db, user.id)
        if pending.workplace_data:
            db.add(MasterWorkplace(master_id=user.id, **pending.workplace_data))
    db.delete(pending)
    db.commit()
    db.refresh(user)
    return user


def _issue_pending_code(pending: PendingRegistration) -> str:
    code = f"{randbelow(1000000):06d}"
    pending.code = code
    pending.code_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.verification_code_ttl_minutes
    )
    return code


def get_pending_registration_by_token(db: Session, token: str) -> PendingRegistration | None:
    normalized = token.strip()
    if not normalized:
        return None
    stmt = select(PendingRegistration).where(PendingRegistration.token == normalized)
    pending = db.execute(stmt).scalar_one_or_none()
    if not pending:
        return None
    if pending.expires_at < datetime.now(timezone.utc):
        db.delete(pending)
        db.commit()
        return None
    return pending



def _split_ids_and_names(values: list[str]):
    ids = []
    names = []
    for v in values:
        try:
            ids.append(uuid.UUID(v))
        except Exception:
            names.append(v)
    return ids, names


def inspect_preference_resolution(db: Session, preferred_style_ids: list[str], preferred_tag_ids: list[str]) -> dict:
    normalized_styles = _normalize_preference_aliases(preferred_style_ids, STYLE_ALIASES)
    normalized_tags = _normalize_preference_aliases(preferred_tag_ids, TAG_ALIASES)

    style_ids, style_names = _split_ids_and_names(normalized_styles)
    tag_ids, tag_names = _split_ids_and_names(normalized_tags)

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

    resolved_style_names = sorted({s.name for s in styles})
    resolved_tag_names = sorted({t.name for t in tags})

    return {
        'received_styles': preferred_style_ids,
        'received_tags': preferred_tag_ids,
        'normalized_styles': normalized_styles,
        'normalized_tags': normalized_tags,
        'resolved_styles': resolved_style_names,
        'resolved_tags': resolved_tag_names,
        'missing_styles': sorted(set(normalized_styles) - set(resolved_style_names)),
        'missing_tags': sorted(set(normalized_tags) - set(resolved_tag_names)),
    }




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
        return None, "invalid_role", None
    if get_user_by_email_or_phone(db, email, phone):
        return None, "conflict", None
    nickname = (profile_data.get("nickname") or "").strip()
    if not nickname:
        return None, "invalid_profile", None
    if get_profile_by_nickname(db, nickname):
        return None, "nickname_conflict", None
    try:
        preferred_style_ids = _normalize_preference_aliases(preferred_style_ids, STYLE_ALIASES)
        preferred_tag_ids = _normalize_preference_aliases(preferred_tag_ids, TAG_ALIASES)
        if len(preferred_style_ids) != 3 or len(preferred_tag_ids) != 3:
            return None, "invalid_preferences", None

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
            return None, "invalid_preferences", None

        preferred_style_ids = [str(s) for s in styles]
        preferred_tag_ids = [str(t) for t in tags]

        if email:
            pending = _create_pending_registration(
                db,
                email,
                phone,
                password,
                role,
                profile_data,
                preferred_style_ids,
                preferred_tag_ids,
                preferences_data,
                master_profile_data,
                workplace_data,
            )
            return None, None, pending.token

        user = User(
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            role=role,
            is_verified=True,
        )
        db.add(user)
        db.flush()

        profile = Profile(user_id=user.id, **profile_data)
        db.add(profile)

        ensure_likes_collection(db, str(user.id))
        ensure_my_posts_collection(db, str(user.id))
        ensure_inkmatch_collection(db, str(user.id))

        for style_id in preferred_style_ids:
            db.add(FeedPreferredStyle(user_id=user.id, style_id=style_id, weight=1))
        for tag_id in preferred_tag_ids:
            db.add(FeedPreferredTag(user_id=user.id, tag_id=tag_id, weight=1))

        if preferences_data:
            db.add(InkmatchDefaults(user_id=user.id, **preferences_data))

        if role == UserRole.master.value:
            if not master_profile_data or master_profile_data.get("experience_years") is None:
                return None, "missing_master_profile", None
            db.add(MasterProfile(user_id=user.id, **master_profile_data))
            _create_base_master_collections(db, user.id)
            if workplace_data:
                db.add(MasterWorkplace(master_id=user.id, **workplace_data))

        db.commit()
        db.refresh(user)
        return user, None, None
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


def verify_verification_code(db: Session, user: User, channel: str, code: str) -> bool:
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
    return True


def consume_verification_code(db: Session, user: User, channel: str, code: str) -> bool:
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
    db.commit()
    return True


def purge_unverified_email_registration(db: Session, login: str) -> bool:
    normalized = login.strip()
    if not normalized:
        return False

    user = get_user_by_login(db, normalized)
    if not user or not user.email or user.is_verified:
        return False

    user_id = user.id

    notification_ids = [
        row[0]
        for row in db.execute(
            select(Notification.id).where(Notification.user_id == user_id)
        ).all()
    ]

    if notification_ids:
        db.execute(delete(NotificationLink).where(NotificationLink.notification_id.in_(notification_ids)))
        db.execute(delete(Notification).where(Notification.id.in_(notification_ids)))

    db.execute(delete(UserPushToken).where(UserPushToken.user_id == user_id))
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
    db.execute(delete(VerificationCode).where(VerificationCode.user_id == user_id))
    db.execute(delete(FeedPreferredStyle).where(FeedPreferredStyle.user_id == user_id))
    db.execute(delete(FeedPreferredTag).where(FeedPreferredTag.user_id == user_id))
    db.execute(delete(InkmatchDefaults).where(InkmatchDefaults.user_id == user_id))
    db.execute(delete(MasterWorkplace).where(MasterWorkplace.master_id == user_id))
    db.execute(delete(MasterProfile).where(MasterProfile.user_id == user_id))
    db.execute(delete(Collection).where(Collection.owner_id == user_id))
    db.execute(delete(Profile).where(Profile.user_id == user_id))
    db.execute(delete(User).where(User.id == user_id))
    db.commit()
    return True
