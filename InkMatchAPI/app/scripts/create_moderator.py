import argparse

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.models.profiles import Profile
from app.models.user import User


def main() -> None:
    parser = argparse.ArgumentParser(description='Create or update moderator user')
    parser.add_argument('--email', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--nickname', default='Moderator')
    args = parser.parse_args()

    session = SessionLocal()
    try:
        user = session.execute(select(User).where(User.email == args.email)).scalar_one_or_none()
        if user is None:
            user = User(
                email=args.email,
                phone=None,
                password_hash=hash_password(args.password),
                role=UserRole.moderator,
                is_verified=True,
            )
            session.add(user)
            session.flush()
            print(f'Created user: {user.id}')
        else:
            user.role = UserRole.moderator
            user.password_hash = hash_password(args.password)
            user.is_verified = True
            print(f'Updated user role to moderator: {user.id}')

        profile = session.execute(select(Profile).where(Profile.user_id == user.id)).scalar_one_or_none()
        if profile is None:
            profile = Profile(
                user_id=user.id,
                nickname=args.nickname,
                avatar_url=None,
                bio='System moderator account',
                home_location_id=None,
                default_currency='RUB',
            )
            session.add(profile)
        else:
            if not profile.nickname:
                profile.nickname = args.nickname

        session.commit()
        print('Moderator is ready.')
    finally:
        session.close()


if __name__ == '__main__':
    main()
