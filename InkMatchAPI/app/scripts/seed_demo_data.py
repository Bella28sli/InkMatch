from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.models.profiles import MasterProfile, Profile
from app.models.user import User


SEED_PASSWORD = 'InkMatchSeedPassword'


@dataclass(frozen=True)
class SeedUser:
    role: UserRole
    nickname: str
    email: str
    phone: str


SEED_USERS: tuple[SeedUser, ...] = (
    SeedUser(
        role=UserRole.moderator,
        nickname='inkmatch_moderator',
        email='moderator.seed@inkmatch.local',
        phone='+79990000001',
    ),
    SeedUser(
        role=UserRole.client,
        nickname='inkmatch_client',
        email='client.seed@inkmatch.local',
        phone='+79990000002',
    ),
    SeedUser(
        role=UserRole.master,
        nickname='inkmatch_master',
        email='master.seed@inkmatch.local',
        phone='+79990000003',
    ),
)


def _get_user(session, *, email: str, phone: str) -> User | None:
    return session.execute(
        select(User).where((User.email == email) | (User.phone == phone))
    ).scalar_one_or_none()


def _ensure_profile(session, user: User, nickname: str) -> None:
    profile = session.get(Profile, user.id)
    if profile:
        profile.nickname = nickname
        profile.default_currency = 'RUB'
        return
    session.add(
        Profile(
            user_id=user.id,
            nickname=nickname,
            avatar_url=None,
            bio=None,
            home_location_id=None,
            default_currency='RUB',
        )
    )


def _ensure_master_profile(session, user: User) -> None:
    master_profile = session.get(MasterProfile, user.id)
    if master_profile:
        return
    session.add(
        MasterProfile(
            user_id=user.id,
            experience_years=None,
            price_min=None,
            price_max=None,
            description=None,
            is_verified=True,
            is_favorite=False,
            verification_skipped=False,
            rating_avg=0,
            completed_sessions_count=0,
        )
    )


def seed_checker_users(session=None) -> None:
    own_session = session is None
    if own_session:
        session = SessionLocal()

    try:
        for item in SEED_USERS:
            user = _get_user(session, email=item.email, phone=item.phone)
            if not user:
                user = User(
                    email=item.email,
                    phone=item.phone,
                    password_hash=hash_password(SEED_PASSWORD),
                    role=item.role,
                    is_verified=True,
                )
                session.add(user)
                session.flush()
            else:
                user.email = item.email
                user.phone = item.phone
                user.password_hash = hash_password(SEED_PASSWORD)
                user.role = item.role
                user.is_verified = True

            _ensure_profile(session, user, item.nickname)
            if item.role == UserRole.master:
                _ensure_master_profile(session, user)

        session.commit()
        print('seed_checker_users: ok')
    except Exception:
        if session is not None:
            session.rollback()
        raise
    finally:
        if own_session and session is not None:
            session.close()


if __name__ == '__main__':
    seed_checker_users()
