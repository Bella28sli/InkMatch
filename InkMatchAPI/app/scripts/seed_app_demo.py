from __future__ import annotations

import random
import shutil
from pathlib import Path
from typing import Iterable

from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.enums import CollectionType, MediaType, OriginalAuthorType, SketchContentType, UserRole
from app.models.locations import Location
from app.models.profiles import MasterProfile, Profile
from app.models.sketches import (
    Collection,
    CollectionItem,
    FeedPreferredStyle,
    FeedPreferredTag,
    Sketch,
    SketchMedia,
    SketchStyle,
    SketchTag,
    Style,
    Tag,
)
from app.models.user import User
from app.scripts.seed_core import seed_locations, seed_metro, seed_styles, seed_tags

SEED_PASSWORD = 'Passw0rd!'
SEED_RANDOM = random.Random(2206)
CLIENT_COUNT = 5
MASTER_COUNT = 5
MODERATOR_COUNT = 1
SKETCH_COUNT = 20
COLLECTION_COUNT = 20

API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
UPLOADS_ROOT = API_ROOT / 'uploads' / 'seed_demo'
ASSET_DIRS = [
    REPO_ROOT / 'InkMatchMobile' / 'assets' / 'styles',
    REPO_ROOT / 'InkMatchMobile' / 'assets' / 'tags',
]


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _public_media_base() -> str:
    return settings.media_base_url.rstrip('/')


def _prepare_seed_media() -> list[str]:
    UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)

    urls: list[str] = []
    base = _public_media_base()

    for src_dir in ASSET_DIRS:
        if not src_dir.exists():
            continue
        for file in src_dir.glob('*'):
            if not file.is_file() or file.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp'}:
                continue
            target = UPLOADS_ROOT / file.name
            if not target.exists():
                shutil.copy2(file, target)
            urls.append(f'{base}/uploads/seed_demo/{target.name}')

    if not urls:
        raise RuntimeError('No local asset images found to seed media.')

    return sorted(set(urls))


def _ensure_user(session, *, email: str, phone: str, role: UserRole) -> User:
    existing = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing:
        return existing

    user = User(
        email=email,
        phone=phone,
        password_hash=hash_password(SEED_PASSWORD),
        role=role,
        is_verified=True,
    )
    session.add(user)
    session.flush()
    return user


def _ensure_profile(session, user: User, location_id: str, nickname: str) -> None:
    if session.get(Profile, user.id):
        return
    session.add(
        Profile(
            user_id=user.id,
            nickname=nickname,
            avatar_url=None,
            bio='Seed account',
            home_location_id=location_id,
            default_currency='RUB',
        )
    )


def _ensure_master_profile(session, user: User) -> None:
    if session.get(MasterProfile, user.id):
        return
    session.add(
        MasterProfile(
            user_id=user.id,
            experience_years=SEED_RANDOM.randint(1, 10),
            price_min=3000,
            price_max=15000,
            description='Seed master profile',
            is_verified=False,
            rating_avg=round(SEED_RANDOM.uniform(4.0, 5.0), 2),
            completed_sessions_count=SEED_RANDOM.randint(5, 120),
        )
    )


def _ensure_preferences(session, user_id: str, styles: list[Style], tags: list[Tag]) -> None:
    existing_styles = session.execute(select(FeedPreferredStyle).where(FeedPreferredStyle.user_id == user_id)).scalars().all()
    if len(existing_styles) < 3 and len(styles) >= 3:
        for style in SEED_RANDOM.sample(styles, k=3):
            if not session.get(FeedPreferredStyle, {'user_id': user_id, 'style_id': style.id}):
                session.add(FeedPreferredStyle(user_id=user_id, style_id=style.id, weight=SEED_RANDOM.randint(1, 5)))

    existing_tags = session.execute(select(FeedPreferredTag).where(FeedPreferredTag.user_id == user_id)).scalars().all()
    if len(existing_tags) < 3 and len(tags) >= 3:
        for tag in SEED_RANDOM.sample(tags, k=3):
            if not session.get(FeedPreferredTag, {'user_id': user_id, 'tag_id': tag.id}):
                session.add(FeedPreferredTag(user_id=user_id, tag_id=tag.id, weight=SEED_RANDOM.randint(1, 5)))


def _seed_sketches(session, masters: list[User], styles: list[Style], tags: list[Tag], media_pool: list[str]) -> list[Sketch]:
    existing = session.execute(select(Sketch).where(Sketch.title.like('Seed sketch %'))).scalars().all()

    needed = max(0, SKETCH_COUNT - len(existing))
    created: list[Sketch] = []

    for i in range(needed):
        sketch = Sketch(
            author_id=SEED_RANDOM.choice(masters).id,
            content_type=SketchContentType.sketch,
            feed_visibility='public',
            title=f'Seed sketch {len(existing) + i + 1}',
            description='Demo sketch for feed',
            original_author_type=OriginalAuthorType.self_,
            like_amount=SEED_RANDOM.randint(0, 200),
            reviewed=True,
        )
        session.add(sketch)
        created.append(sketch)

    session.flush()

    targets = existing + created

    for sketch in targets:
        media_row = session.execute(
            select(SketchMedia).where(SketchMedia.sketch_id == sketch.id).order_by(SketchMedia.sort_order.asc())
        ).scalar_one_or_none()

        image_url = SEED_RANDOM.choice(media_pool)

        if media_row is None:
            session.add(
                SketchMedia(
                    sketch_id=sketch.id,
                    media_type=MediaType.image,
                    url=image_url,
                    preview_image_url=None,
                    width=1200,
                    height=1200,
                    file_size_bytes=350_000,
                    sha256=(sketch.id.hex * 2)[:64],
                    phash=sketch.id.hex[:16],
                    sort_order=0,
                )
            )
        else:
            media_row.url = image_url
            if not media_row.media_type:
                media_row.media_type = MediaType.image

        for style in SEED_RANDOM.sample(styles, k=min(2, len(styles))):
            if not session.get(SketchStyle, {'sketch_id': sketch.id, 'style_id': style.id}):
                session.add(SketchStyle(sketch_id=sketch.id, style_id=style.id))

        for tag in SEED_RANDOM.sample(tags, k=min(2, len(tags))):
            if not session.get(SketchTag, {'sketch_id': sketch.id, 'tag_id': tag.id}):
                session.add(SketchTag(sketch_id=sketch.id, tag_id=tag.id))

    session.flush()
    return session.execute(select(Sketch)).scalars().all()


def _seed_collections(session, users: Iterable[User], sketches: list[Sketch]) -> None:
    existing_count = _count(session, Collection)
    if existing_count >= COLLECTION_COUNT:
        return

    users_list = list(users)
    needed = COLLECTION_COUNT - existing_count

    for i in range(needed):
        collection = Collection(
            owner_id=SEED_RANDOM.choice(users_list).id,
            collection_type=CollectionType.custom,
            title=f'Seed collection {existing_count + i + 1}',
            description='Demo collection',
            is_system=False,
            is_private=False,
        )
        session.add(collection)
        session.flush()

        for order, sketch in enumerate(SEED_RANDOM.sample(sketches, k=min(6, len(sketches))), start=1):
            if session.get(CollectionItem, {'collection_id': collection.id, 'sketch_id': sketch.id}):
                continue
            session.add(
                CollectionItem(
                    collection_id=collection.id,
                    sketch_id=sketch.id,
                    sort_order=order,
                    work_duration_houres=SEED_RANDOM.choice([1, 2, 3, 4]),
                    work_price=SEED_RANDOM.randint(3000, 17000),
                    currency='RUB',
                    note='Seed item',
                )
            )


def main() -> None:
    session = SessionLocal()
    try:
        media_pool = _prepare_seed_media()

        seed_styles(session)
        seed_tags(session)
        city_map = seed_locations(session)
        seed_metro(session, city_map)

        styles = session.execute(select(Style)).scalars().all()
        tags = session.execute(select(Tag)).scalars().all()
        locations = session.execute(select(Location)).scalars().all()
        if not locations:
            raise RuntimeError('No locations available for demo seeding')

        clients: list[User] = []
        masters: list[User] = []
        moderators: list[User] = []

        for i in range(1, CLIENT_COUNT + 1):
            user = _ensure_user(
                session,
                email=f'client{i}@seed.inkmatch',
                phone=f'+799910{i:04d}',
                role=UserRole.client,
            )
            clients.append(user)

        for i in range(1, MASTER_COUNT + 1):
            user = _ensure_user(
                session,
                email=f'master{i}@seed.inkmatch',
                phone=f'+799920{i:04d}',
                role=UserRole.master,
            )
            masters.append(user)

        for i in range(1, MODERATOR_COUNT + 1):
            user = _ensure_user(
                session,
                email=f'moderator{i}@seed.inkmatch',
                phone=f'+799930{i:04d}',
                role=UserRole.moderator,
            )
            moderators.append(user)

        all_users = clients + masters + moderators

        for idx, user in enumerate(all_users, start=1):
            location_id = SEED_RANDOM.choice(locations).id
            _ensure_profile(session, user, location_id, f'{user.role.value}_{idx}')
            if user.role == UserRole.master:
                _ensure_master_profile(session, user)
            if user.role == UserRole.client:
                _ensure_preferences(session, user.id, styles, tags)

        sketches = _seed_sketches(session, masters, styles, tags, media_pool)
        _seed_collections(session, all_users, sketches)

        session.commit()
        print('Demo seed completed.')
        print(f'Seed password: {SEED_PASSWORD}')
        print(f'Users: {len(all_users)}, sketches: {_count(session, Sketch)}, collections: {_count(session, Collection)}')
        print(f'Media source: {UPLOADS_ROOT}')
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == '__main__':
    main()
