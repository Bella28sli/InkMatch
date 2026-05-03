from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.enums import (
    AppealStatus,
    AppealTargetType,
    AuditSource,
    ChatKind,
    CollectionType,
    ComplaintStatus,
    ComplaintTargetType,
    DocumentType,
    FileType,
    InkmatchRequestStatus,
    InkmatchStatus,
    LocationPrecisionLevel,
    LocationProvider,
    MediaType,
    ModerationActionType,
    ModerationQueueEntityType,
    ModerationQueueStatus,
    NotificationType,
    OriginalAuthorType,
    RequestCreatorRole,
    RestrictionType,
    SearchMode,
    SketchContentType,
    UserRole,
    VerificationStatus,
    WorkplaceDisplayMode,
    WorkplaceType,
)
from app.models.inkmatch import (
    ClientInkmatchParams,
    Inkmatch,
    InkmatchRequest,
    InkmatchReview,
    InkmatchReviewAttachment,
    MasterInkmatchOffer,
)
from app.models.locations import Location, MasterWorkplace, MetroStation
from app.models.messaging import (
    Chat,
    ChatParticipant,
    Message,
    MessageAttachment,
    Notification,
    NotificationLink,
)
from app.models.moderation import (
    Appeal,
    AppealAttachment,
    AuditEvent,
    AuditEventTarget,
    Complaint,
    ModerationAction,
    ModerationQueueItem,
    ModerationReason,
)
from app.models.profiles import InkmatchDefaults, MasterProfile, Profile
from app.models.sketches import (
    Collection,
    CollectionItem,
    CommentAttachment,
    FeedPreferredStyle,
    FeedPreferredTag,
    Sketch,
    SketchComment,
    SketchCommentLike,
    SketchMedia,
    SketchPin,
    SketchStyle,
    SketchTag,
    Style,
    Tag,
)
from app.models.user import User
from app.models.user_extras import Subscription, UserRestriction
from app.models.verification import (
    MasterVerificationDocument,
    MasterVerificationDocumentFile,
    MasterVerificationPersonalData,
    MasterVerificationRequest,
)
from app.scripts.seed_core import seed_locations, seed_metro, seed_styles, seed_tags

SEED = 42690
CLIENT_COUNT = 5
MASTER_COUNT = 5
MODERATOR_COUNT = 1
OTHER_COUNT = 20
SEED_PASSWORD = 'Passw0rd!'


rnd = random.Random(SEED)


def count_rows(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def fill_to_count(session, model, target: int, factory, label: str) -> int:
    created = 0
    while count_rows(session, model) < target:
        session.add(factory())
        created += 1
    if created:
        session.flush()
    print(f'{label}: +{created} (total={count_rows(session, model)})')
    return created


def ensure_users(session) -> tuple[list[User], list[User], list[User]]:
    role_plan = [
        (UserRole.client, CLIENT_COUNT, 'client', '1'),
        (UserRole.master, MASTER_COUNT, 'master', '2'),
        (UserRole.moderator, MODERATOR_COUNT, 'moderator', '3'),
    ]

    for role, total, prefix, phone_prefix in role_plan:
        for i in range(1, total + 1):
            email = f'{prefix}{i}@seed.inkmatch'
            existing = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if existing:
                continue
            session.add(
                User(
                    email=email,
                    phone=f'+799900{phone_prefix}{i:04d}',
                    password_hash=hash_password(SEED_PASSWORD),
                    role=role,
                    is_verified=True,
                )
            )

    session.flush()

    clients = session.execute(select(User).where(User.role == UserRole.client)).scalars().all()
    masters = session.execute(select(User).where(User.role == UserRole.master)).scalars().all()
    moderators = session.execute(select(User).where(User.role == UserRole.moderator)).scalars().all()

    print(f'users: clients={len(clients)}, masters={len(masters)}, moderators={len(moderators)}')
    return clients, masters, moderators


def ensure_profile_stack(session, users: list[User], masters: list[User], locations: list[Location], metros: list[MetroStation], styles: list[Style], tags: list[Tag]):
    for idx, user in enumerate(users, start=1):
        profile = session.get(Profile, user.id)
        if not profile:
            session.add(
                Profile(
                    user_id=user.id,
                    nickname=f'{user.role.value}_{idx}',
                    avatar_url=f'https://cdn.seed.inkmatch/avatar/{idx}.jpg',
                    bio='Seed account for demo',
                    home_location_id=rnd.choice(locations).id,
                    default_currency='RUB',
                )
            )

        defaults = session.get(InkmatchDefaults, user.id)
        if not defaults:
            city = rnd.choice(locations)
            session.add(
                InkmatchDefaults(
                    user_id=user.id,
                    experience_years_min=rnd.randint(0, 5),
                    rating_min=round(rnd.uniform(3.5, 5.0), 2),
                    workplace=rnd.choice(list(WorkplaceType)),
                    search_mode=rnd.choice(list(SearchMode)),
                    city_location_id=city.id,
                    region_location_id=city.id,
                    radius_meters=rnd.choice([2000, 3000, 5000]),
                    center_lat=city.lat,
                    center_lon=city.lon,
                    default_size_sm=rnd.randint(5, 20),
                    default_price_min=3000,
                    default_price_max=12000,
                )
            )

        pref_styles = session.execute(select(FeedPreferredStyle).where(FeedPreferredStyle.user_id == user.id)).scalars().all()
        if len(pref_styles) < 3:
            picked = rnd.sample(styles, k=3)
            for style in picked:
                exists = session.get(FeedPreferredStyle, {'user_id': user.id, 'style_id': style.id})
                if not exists:
                    session.add(FeedPreferredStyle(user_id=user.id, style_id=style.id, weight=rnd.randint(1, 5)))

        pref_tags = session.execute(select(FeedPreferredTag).where(FeedPreferredTag.user_id == user.id)).scalars().all()
        if len(pref_tags) < 3:
            picked = rnd.sample(tags, k=3)
            for tag in picked:
                exists = session.get(FeedPreferredTag, {'user_id': user.id, 'tag_id': tag.id})
                if not exists:
                    session.add(FeedPreferredTag(user_id=user.id, tag_id=tag.id, weight=rnd.randint(1, 5)))

    for idx, master in enumerate(masters, start=1):
        master_profile = session.get(MasterProfile, master.id)
        if not master_profile:
            session.add(
                MasterProfile(
                    user_id=master.id,
                    experience_years=rnd.randint(1, 12),
                    price_min=2500,
                    price_max=15000,
                    description=f'Seed master profile #{idx}',
                    is_verified=True,
                    rating_avg=round(rnd.uniform(4.0, 5.0), 2),
                    completed_sessions_count=rnd.randint(10, 300),
                )
            )

        workplace = session.execute(select(MasterWorkplace).where(MasterWorkplace.master_id == master.id)).scalar_one_or_none()
        if not workplace:
            loc = rnd.choice(locations)
            metro = rnd.choice(metros) if metros else None
            session.add(
                MasterWorkplace(
                    master_id=master.id,
                    location_id=loc.id,
                    is_home_studio=False,
                    studio_name=f'Studio {idx}',
                    public_display_mode=WorkplaceDisplayMode.metro if metro else WorkplaceDisplayMode.city_only,
                    public_metro_station_id=metro.id if metro else None,
                    public_text_override='Near city center',
                    show_on_map=True,
                    public_lat=loc.lat,
                    public_lon=loc.lon,
                    is_primary=True,
                )
            )

    session.flush()


def seed_other_entities(session, clients: list[User], masters: list[User], moderators: list[User], styles: list[Style], tags: list[Tag], locations: list[Location]):
    users = clients + masters + moderators
    moderator = moderators[0]

    fill_to_count(
        session,
        ModerationReason,
        OTHER_COUNT,
        lambda: ModerationReason(code=f'seed_{uuid4().hex[:8]}', title='Seed reason', description='Auto generated'),
        'moderation_reasons',
    )

    reason_ids = session.execute(select(ModerationReason.id)).scalars().all()

    fill_to_count(
        session,
        Sketch,
        OTHER_COUNT,
        lambda: Sketch(
            author_id=rnd.choice(masters).id,
            content_type=SketchContentType.sketch,
            feed_visibility='public',
            title=f'Seed sketch {uuid4().hex[:6]}',
            description='Seed sketch for feed',
            original_author_type=OriginalAuthorType.self_,
            like_amount=rnd.randint(0, 400),
            reviewed=True,
        ),
        'sketches',
    )

    sketches = session.execute(select(Sketch)).scalars().all()

    fill_to_count(
        session,
        SketchMedia,
        OTHER_COUNT,
        lambda: SketchMedia(
            sketch_id=rnd.choice(sketches).id,
            media_type=MediaType.image,
            url=f'https://cdn.seed.inkmatch/sketch/{uuid4().hex}.jpg',
            preview_image_url=None,
            width=1080,
            height=1080,
            file_size_bytes=rnd.randint(200_000, 2_000_000),
            sha256=uuid4().hex + uuid4().hex,
            phash=uuid4().hex[:16],
            sort_order=0,
        ),
        'sketch_media',
    )

    created_links = 0
    attempts = 0
    while count_rows(session, SketchStyle) < OTHER_COUNT and attempts < OTHER_COUNT * 30:
        attempts += 1
        sketch = rnd.choice(sketches)
        style = rnd.choice(styles)
        if session.get(SketchStyle, {'sketch_id': sketch.id, 'style_id': style.id}):
            continue
        session.add(SketchStyle(sketch_id=sketch.id, style_id=style.id))
        created_links += 1
    print(f'sketch_styles: +{created_links} (total={count_rows(session, SketchStyle)})')

    created_links = 0
    attempts = 0
    while count_rows(session, SketchTag) < OTHER_COUNT and attempts < OTHER_COUNT * 30:
        attempts += 1
        sketch = rnd.choice(sketches)
        tag = rnd.choice(tags)
        if session.get(SketchTag, {'sketch_id': sketch.id, 'tag_id': tag.id}):
            continue
        session.add(SketchTag(sketch_id=sketch.id, tag_id=tag.id))
        created_links += 1
    print(f'sketch_tags: +{created_links} (total={count_rows(session, SketchTag)})')

    fill_to_count(
        session,
        SketchComment,
        OTHER_COUNT,
        lambda: SketchComment(
            sketch_id=rnd.choice(sketches).id,
            author_user_id=rnd.choice(users).id,
            body='Seed comment',
            is_deleted=False,
        ),
        'sketch_comments',
    )

    comments = session.execute(select(SketchComment)).scalars().all()

    fill_to_count(
        session,
        CommentAttachment,
        OTHER_COUNT,
        lambda: CommentAttachment(
            comment_id=rnd.choice(comments).id,
            file_url=f'https://cdn.seed.inkmatch/comment/{uuid4().hex}.jpg',
            file_type=FileType.image,
            mime_type='image/jpeg',
            file_size_bytes=rnd.randint(80_000, 500_000),
            width=900,
            height=900,
        ),
        'comments_attachments',
    )

    created_links = 0
    attempts = 0
    while count_rows(session, SketchCommentLike) < OTHER_COUNT and attempts < OTHER_COUNT * 40:
        attempts += 1
        user = rnd.choice(users)
        comment = rnd.choice(comments)
        if session.get(SketchCommentLike, {'user_id': user.id, 'comment_id': comment.id}):
            continue
        session.add(SketchCommentLike(user_id=user.id, comment_id=comment.id))
        created_links += 1
    print(f'sketch_comment_likes: +{created_links} (total={count_rows(session, SketchCommentLike)})')

    created_links = 0
    attempts = 0
    while count_rows(session, SketchPin) < OTHER_COUNT and attempts < OTHER_COUNT * 40:
        attempts += 1
        sketch = rnd.choice(sketches)
        comment = rnd.choice(comments)
        if session.get(SketchPin, {'sketch_id': sketch.id}):
            continue
        session.add(
            SketchPin(
                sketch_id=sketch.id,
                pinned_comment_id=comment.id,
                pinned_by_user_id=rnd.choice(masters).id,
                pinned_reason='inkmatch_review',
            )
        )
        created_links += 1
    print(f'sketch_pins: +{created_links} (total={count_rows(session, SketchPin)})')

    fill_to_count(
        session,
        Collection,
        OTHER_COUNT,
        lambda: Collection(
            owner_id=rnd.choice(users).id,
            collection_type=rnd.choice(list(CollectionType)),
            title=f'Seed collection {uuid4().hex[:5]}',
            description='Seed collection',
            is_system=False,
        ),
        'collections',
    )

    collections = session.execute(select(Collection)).scalars().all()

    created_links = 0
    attempts = 0
    while count_rows(session, CollectionItem) < OTHER_COUNT and attempts < OTHER_COUNT * 40:
        attempts += 1
        collection = rnd.choice(collections)
        sketch = rnd.choice(sketches)
        if session.get(CollectionItem, {'collection_id': collection.id, 'sketch_id': sketch.id}):
            continue
        session.add(
            CollectionItem(
                collection_id=collection.id,
                sketch_id=sketch.id,
                sort_order=rnd.randint(1, 20),
                work_duration_houres=rnd.randint(1, 6),
                work_price=rnd.randint(3000, 15000),
                currency='RUB',
                note='Seed item',
            )
        )
        created_links += 1
    print(f'collection_items: +{created_links} (total={count_rows(session, CollectionItem)})')

    fill_to_count(
        session,
        Chat,
        OTHER_COUNT,
        lambda: Chat(chat_kind=ChatKind.direct, created_by_user_id=rnd.choice(users).id),
        'chats',
    )

    chats = session.execute(select(Chat)).scalars().all()

    created_links = 0
    attempts = 0
    while count_rows(session, ChatParticipant) < OTHER_COUNT * 2 and attempts < OTHER_COUNT * 80:
        attempts += 1
        chat = rnd.choice(chats)
        user = rnd.choice(users)
        if session.get(ChatParticipant, {'chat_id': chat.id, 'user_id': user.id}):
            continue
        session.add(ChatParticipant(chat_id=chat.id, user_id=user.id))
        created_links += 1
    print(f'chat_participants: +{created_links} (total={count_rows(session, ChatParticipant)})')

    fill_to_count(
        session,
        Message,
        OTHER_COUNT,
        lambda: Message(
            chat_id=rnd.choice(chats).id,
            sender_id=rnd.choice(users).id,
            message_type='text',
            text='Seed message',
            payload={'seed': True},
        ),
        'messages',
    )

    messages = session.execute(select(Message)).scalars().all()

    fill_to_count(
        session,
        MessageAttachment,
        OTHER_COUNT,
        lambda: MessageAttachment(
            message_id=rnd.choice(messages).id,
            file_url=f'https://cdn.seed.inkmatch/message/{uuid4().hex}.jpg',
            file_type=FileType.image,
            mime_type='image/jpeg',
            file_size_bytes=rnd.randint(120_000, 700_000),
            width=1000,
            height=1000,
            duration_seconds=None,
        ),
        'message_attachments',
    )

    fill_to_count(
        session,
        Notification,
        OTHER_COUNT,
        lambda: Notification(
            user_id=rnd.choice(users).id,
            type=rnd.choice(list(NotificationType)),
            title='Seed notification',
            body='Notification body',
            is_read=False,
            image_url=None,
        ),
        'notifications',
    )

    notifications = session.execute(select(Notification)).scalars().all()

    fill_to_count(
        session,
        NotificationLink,
        OTHER_COUNT,
        lambda: NotificationLink(
            notification_id=rnd.choice(notifications).id,
            entity_type='sketch',
            entity_id=rnd.choice(sketches).id,
        ),
        'notification_links',
    )

    fill_to_count(
        session,
        Complaint,
        OTHER_COUNT,
        lambda: Complaint(
            author_id=rnd.choice(users).id,
            target_type=ComplaintTargetType.sketch,
            target_id=rnd.choice(sketches).id,
            reason='Seed complaint reason',
            details='Seed complaint details',
            status=rnd.choice(list(ComplaintStatus)),
        ),
        'complaints',
    )

    complaints = session.execute(select(Complaint)).scalars().all()

    fill_to_count(
        session,
        ModerationQueueItem,
        OTHER_COUNT,
        lambda: ModerationQueueItem(
            entity_type=rnd.choice(list(ModerationQueueEntityType)),
            entity_id=rnd.choice(complaints).id,
            priority=rnd.randint(1, 5),
            status=rnd.choice(list(ModerationQueueStatus)),
            assigned_moderator_id=moderator.id,
        ),
        'moderation_queue_items',
    )

    fill_to_count(
        session,
        Appeal,
        OTHER_COUNT,
        lambda: Appeal(
            appellant_user_id=rnd.choice(users).id,
            target_type=AppealTargetType.complaint,
            target_id=rnd.choice(complaints).id,
            description='Seed appeal description',
            status=rnd.choice(list(AppealStatus)),
            reason_text='Seed reason',
            reviewed_by_moderator_id=moderator.id,
            reviewed_at=datetime.now(timezone.utc),
            decision_note='Checked by seed',
        ),
        'appeals',
    )

    appeals = session.execute(select(Appeal)).scalars().all()

    fill_to_count(
        session,
        AppealAttachment,
        OTHER_COUNT,
        lambda: AppealAttachment(
            appeal_id=rnd.choice(appeals).id,
            file_url=f'https://cdn.seed.inkmatch/appeal/{uuid4().hex}.pdf',
            file_type=FileType.document,
        ),
        'appeal_attachments',
    )

    fill_to_count(
        session,
        ModerationAction,
        OTHER_COUNT,
        lambda: ModerationAction(
            moderator_id=moderator.id,
            action_type=rnd.choice(list(ModerationActionType)),
            target_type=ComplaintTargetType.sketch,
            target_id=rnd.choice(sketches).id,
            complaint_id=rnd.choice(complaints).id,
            reason='Seed moderation action',
            params={'seed': True},
        ),
        'moderation_actions',
    )

    fill_to_count(
        session,
        AuditEvent,
        OTHER_COUNT,
        lambda: AuditEvent(
            occurred_at=datetime.now(timezone.utc),
            actor_user_id=rnd.choice(users).id,
            actor_role='user',
            event_type='seed_event',
            source=rnd.choice(list(AuditSource)),
            ip_hash=uuid4().hex,
            context={'seed': True},
        ),
        'audit_events',
    )

    events = session.execute(select(AuditEvent)).scalars().all()

    fill_to_count(
        session,
        AuditEventTarget,
        OTHER_COUNT,
        lambda: AuditEventTarget(
            audit_event_id=rnd.choice(events).id,
            target_type='sketch',
            target_id=rnd.choice(sketches).id,
        ),
        'audit_event_targets',
    )

    fill_to_count(
        session,
        UserRestriction,
        OTHER_COUNT,
        lambda: UserRestriction(
            user_id=rnd.choice(users).id,
            imposed_by_moderator_id=moderator.id,
            restriction_type=rnd.choice(list(RestrictionType)),
            starts_at=datetime.now(timezone.utc) - timedelta(days=rnd.randint(1, 7)),
            ends_at=datetime.now(timezone.utc) + timedelta(days=rnd.randint(7, 30)),
            is_active=True,
            reason_id=rnd.choice(reason_ids),
        ),
        'user_restrictions',
    )

    created_links = 0
    attempts = 0
    while count_rows(session, Subscription) < OTHER_COUNT and attempts < OTHER_COUNT * 80:
        attempts += 1
        follower = rnd.choice(users)
        followed = rnd.choice(users)
        if follower.id == followed.id:
            continue
        if session.get(Subscription, {'follower_id': follower.id, 'followed_id': followed.id}):
            continue
        session.add(Subscription(follower_id=follower.id, followed_id=followed.id))
        created_links += 1
    print(f'subscriptions: +{created_links} (total={count_rows(session, Subscription)})')

    fill_to_count(
        session,
        MasterVerificationRequest,
        OTHER_COUNT,
        lambda: MasterVerificationRequest(
            master_id=rnd.choice(masters).id,
            status=rnd.choice(list(VerificationStatus)),
            comments='Seed verification request',
            submitted_at=datetime.now(timezone.utc) - timedelta(days=rnd.randint(1, 5)),
            reviewed_at=datetime.now(timezone.utc),
            reviewed_by_moderator_id=moderator.id,
            rejection_reason=None,
        ),
        'master_verification_requests',
    )

    verif_requests = session.execute(select(MasterVerificationRequest)).scalars().all()

    created_personal = 0
    for req in verif_requests:
        if session.get(MasterVerificationPersonalData, req.id):
            continue
        session.add(
            MasterVerificationPersonalData(
                request_id=req.id,
                first_name='Seed',
                second_name='User',
                last_name=f'#{rnd.randint(1, 999)}',
                patronymic=None,
                birth_date=date(1995, 5, 15),
                citizenship='RU',
            )
        )
        created_personal += 1
    if created_personal:
        session.flush()
    print(f'master_verification_personal_data: +{created_personal} (total={count_rows(session, MasterVerificationPersonalData)})')

    fill_to_count(
        session,
        MasterVerificationDocument,
        OTHER_COUNT,
        lambda: MasterVerificationDocument(
            request_id=rnd.choice(verif_requests).id,
            document_type=rnd.choice(list(DocumentType)),
            title='Seed document',
            issuer='Seed issuer',
            issued_date=date(2020, 1, 1),
        ),
        'master_verification_documents',
    )

    verif_docs = session.execute(select(MasterVerificationDocument)).scalars().all()

    fill_to_count(
        session,
        MasterVerificationDocumentFile,
        OTHER_COUNT,
        lambda: MasterVerificationDocumentFile(
            document_id=rnd.choice(verif_docs).id,
            file_url=f'https://cdn.seed.inkmatch/doc/{uuid4().hex}.jpg',
            file_type='image',
        ),
        'master_verification_document_files',
    )

    fill_to_count(
        session,
        InkmatchRequest,
        OTHER_COUNT,
        lambda: InkmatchRequest(
            created_by_user_id=rnd.choice(users).id,
            created_by_role=rnd.choice(list(RequestCreatorRole)),
            sketch_id=rnd.choice(sketches).id,
            status=rnd.choice(list(InkmatchRequestStatus)),
        ),
        'inkmatch_requests',
    )

    requests = session.execute(select(InkmatchRequest)).scalars().all()

    created_params = 0
    for req in requests:
        if session.get(ClientInkmatchParams, req.id):
            continue
        city = rnd.choice(locations)
        session.add(
            ClientInkmatchParams(
                request_id=req.id,
                size_sm=rnd.randint(5, 25),
                price_min=3000,
                price_max=18000,
                search_mode=rnd.choice(list(SearchMode)),
                city_location_id=city.id,
                region_location_id=city.id,
                center_lat=city.lat,
                center_lon=city.lon,
                radius_meters=rnd.choice([1000, 3000, 7000]),
                preferred_experience_years_min=rnd.randint(0, 8),
                preferred_rating_min=round(rnd.uniform(3.5, 5.0), 2),
                preferred_workplace=rnd.choice(list(WorkplaceType)),
            )
        )
        created_params += 1
    if created_params:
        session.flush()
    print(f'client_inkmatch_params: +{created_params} (total={count_rows(session, ClientInkmatchParams)})')

    created_offers = 0
    for req in requests:
        if session.get(MasterInkmatchOffer, req.id):
            continue
        session.add(
            MasterInkmatchOffer(
                request_id=req.id,
                offer_price=rnd.randint(4000, 20000),
                offer_duration_minutes=rnd.choice([60, 90, 120, 180]),
            )
        )
        created_offers += 1
    if created_offers:
        session.flush()
    print(f'master_inkmatch_offer: +{created_offers} (total={count_rows(session, MasterInkmatchOffer)})')

    fill_to_count(
        session,
        Inkmatch,
        OTHER_COUNT,
        lambda: Inkmatch(
            sketch_id=rnd.choice(sketches).id,
            client_request_id=rnd.choice(requests).id,
            master_request_id=rnd.choice(requests).id,
            status=rnd.choice(list(InkmatchStatus)),
        ),
        'inkmatches',
    )

    inkmatches = session.execute(select(Inkmatch)).scalars().all()

    created_reviews = 0
    for match in inkmatches:
        exists = session.execute(select(InkmatchReview).where(InkmatchReview.inkmatch_id == match.id)).scalar_one_or_none()
        if exists:
            continue
        rating = rnd.randint(3, 5)
        session.add(
            InkmatchReview(
                inkmatch_id=match.id,
                rating_overall=rating,
                rating_communication=rating,
                rating_cleanliness=rating,
                rating_quality=rating,
                rating_punctuality=rating,
                rating_price_fairness=rating,
                body='Seed review',
            )
        )
        created_reviews += 1
    if created_reviews:
        session.flush()
    print(f'inkmatch_reviews: +{created_reviews} (total={count_rows(session, InkmatchReview)})')

    reviews = session.execute(select(InkmatchReview)).scalars().all()

    fill_to_count(
        session,
        InkmatchReviewAttachment,
        OTHER_COUNT,
        lambda: InkmatchReviewAttachment(
            review_id=rnd.choice(reviews).id,
            file_url=f'https://cdn.seed.inkmatch/review/{uuid4().hex}.jpg',
            file_type=FileType.image,
        ),
        'inkmatch_review_attachments',
    )


def main():
    session = SessionLocal()
    try:
        seed_styles(session)
        seed_tags(session)
        city_map = seed_locations(session)
        seed_metro(session, city_map)
        session.flush()

        styles = session.execute(select(Style)).scalars().all()
        tags = session.execute(select(Tag)).scalars().all()
        locations = session.execute(select(Location)).scalars().all()
        metros = session.execute(select(MetroStation)).scalars().all()

        clients, masters, moderators = ensure_users(session)
        ensure_profile_stack(session, clients + masters + moderators, masters, locations, metros, styles, tags)
        seed_other_entities(session, clients, masters, moderators, styles, tags, locations)

        session.commit()
        print('Seed completed successfully.')
        print(f'Login password for all seed users: {SEED_PASSWORD}')
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == '__main__':
    main()
