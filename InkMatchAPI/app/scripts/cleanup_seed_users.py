from __future__ import annotations

from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models.inkmatch import (
    ClientInkmatchParams,
    Inkmatch,
    InkmatchRequest,
    InkmatchReview,
    MasterInkmatchOffer,
)
from app.models.locations import MasterWorkplace
from app.models.messaging import (
    Chat,
    ChatParticipant,
    Message,
    MessageAttachment,
    MessageRead,
    Notification,
    NotificationLink,
    UserPushToken,
)
from app.models.moderation import (
    Appeal,
    AppealAttachment,
    AuditEvent,
    AuditEventTarget,
    Complaint,
    ModerationAction,
    ModerationQueueItem,
    UserWarning,
)
from app.models.profiles import InkmatchDefaults, MasterProfile, Profile
from app.models.refresh_token import RefreshToken
from app.models.sketches import (
    Collection,
    CollectionItem,
    CommentAttachment,
    FeedPreferredStyle,
    FeedPreferredTag,
    Sketch,
    SketchComment,
    SketchCommentLike,
    SketchLike,
    SketchMedia,
    SketchPin,
    SketchStyle,
    SketchTag,
)
from app.models.user import User
from app.models.user_extras import Subscription, UserRestriction
from app.models.verification import (
    MasterVerificationDocument,
    MasterVerificationDocumentFile,
    MasterVerificationPersonalData,
    MasterVerificationRequest,
)
from app.models.verification_codes import VerificationCode


def cleanup_seed_users() -> None:
    with SessionLocal() as session:
        seed_users = session.execute(
            select(User).where(User.email.like("%@seed.inkmatch"))
        ).scalars().all()

        if not seed_users:
            print("No seed users found.")
            return

        seed_user_ids = [user.id for user in seed_users]

        sketch_ids = session.execute(
            select(Sketch.id).where(
                (Sketch.author_id.in_(seed_user_ids)) | (Sketch.original_author_user_id.in_(seed_user_ids))
            )
        ).scalars().all()

        request_ids = session.execute(
            select(InkmatchRequest.id).where(InkmatchRequest.created_by_user_id.in_(seed_user_ids))
        ).scalars().all()

        chat_ids = session.execute(
            select(Chat.id).where(Chat.created_by_user_id.in_(seed_user_ids))
        ).scalars().all()

        notification_ids = session.execute(
            select(Notification.id).where(Notification.user_id.in_(seed_user_ids))
        ).scalars().all()

        appeal_ids = session.execute(
            select(Appeal.id).where(Appeal.appellant_user_id.in_(seed_user_ids))
        ).scalars().all()

        complaint_ids = session.execute(
            select(Complaint.id).where(Complaint.author_id.in_(seed_user_ids))
        ).scalars().all()

        verification_request_ids = session.execute(
            select(MasterVerificationRequest.id).where(MasterVerificationRequest.master_id.in_(seed_user_ids))
        ).scalars().all()

        print(f"Seed users: {len(seed_user_ids)}")
        print(f"Seed sketches: {len(sketch_ids)}")
        print(f"Seed inkmatch requests: {len(request_ids)}")
        print(f"Seed chats: {len(chat_ids)}")

        # User-linked rows
        session.execute(delete(VerificationCode).where(VerificationCode.user_id.in_(seed_user_ids)))
        session.execute(delete(RefreshToken).where(RefreshToken.user_id.in_(seed_user_ids)))
        session.execute(delete(UserPushToken).where(UserPushToken.user_id.in_(seed_user_ids)))
        session.execute(delete(Profile).where(Profile.user_id.in_(seed_user_ids)))
        session.execute(delete(MasterProfile).where(MasterProfile.user_id.in_(seed_user_ids)))
        session.execute(delete(InkmatchDefaults).where(InkmatchDefaults.user_id.in_(seed_user_ids)))
        session.execute(delete(MasterWorkplace).where(MasterWorkplace.master_id.in_(seed_user_ids)))
        session.execute(delete(UserWarning).where(
            (UserWarning.user_id.in_(seed_user_ids)) | (UserWarning.issued_by_moderator_id.in_(seed_user_ids))
        ))
        session.execute(delete(UserRestriction).where(
            (UserRestriction.user_id.in_(seed_user_ids)) | (UserRestriction.imposed_by_moderator_id.in_(seed_user_ids))
        ))
        session.execute(delete(Subscription).where(
            (Subscription.follower_id.in_(seed_user_ids)) | (Subscription.followed_id.in_(seed_user_ids))
        ))
        session.execute(delete(ModerationQueueItem).where(ModerationQueueItem.assigned_moderator_id.in_(seed_user_ids)))
        session.execute(delete(ModerationAction).where(ModerationAction.moderator_id.in_(seed_user_ids)))
        session.execute(delete(NotificationLink).where(
            NotificationLink.notification_id.in_(notification_ids)
        ))
        session.execute(delete(Notification).where(Notification.user_id.in_(seed_user_ids)))

        # Messaging
        session.execute(delete(MessageAttachment).where(MessageAttachment.message_id.in_(
            select(Message.id).where(Message.chat_id.in_(chat_ids))
        )))
        session.execute(delete(MessageRead).where(MessageRead.user_id.in_(seed_user_ids)))
        session.execute(delete(Message).where(
            (Message.sender_id.in_(seed_user_ids)) | (Message.chat_id.in_(chat_ids))
        ))
        session.execute(delete(ChatParticipant).where(ChatParticipant.user_id.in_(seed_user_ids)))
        session.execute(delete(Chat).where(Chat.created_by_user_id.in_(seed_user_ids)))

        # Verification flow
        session.execute(delete(MasterVerificationDocumentFile).where(
            MasterVerificationDocumentFile.document_id.in_(
                select(MasterVerificationDocument.id).where(
                    MasterVerificationDocument.request_id.in_(verification_request_ids)
                )
            )
        ))
        session.execute(delete(MasterVerificationDocument).where(MasterVerificationDocument.request_id.in_(verification_request_ids)))
        session.execute(delete(MasterVerificationPersonalData).where(
            MasterVerificationPersonalData.request_id.in_(verification_request_ids)
        ))
        session.execute(delete(MasterVerificationRequest).where(
            MasterVerificationRequest.master_id.in_(seed_user_ids)
        ))

        # Moderation / complaints / appeals
        session.execute(delete(AppealAttachment).where(
            AppealAttachment.appeal_id.in_(appeal_ids)
        ))
        session.execute(delete(Appeal).where(Appeal.appellant_user_id.in_(seed_user_ids)))
        session.execute(delete(ModerationAction).where(
            ModerationAction.complaint_id.in_(complaint_ids)
        ))
        session.execute(delete(Complaint).where(Complaint.author_id.in_(seed_user_ids)))
        session.execute(delete(AuditEventTarget).where(
            AuditEventTarget.audit_event_id.in_(
                select(AuditEvent.id).where(AuditEvent.actor_user_id.in_(seed_user_ids))
            )
        ))
        session.execute(delete(AuditEvent).where(AuditEvent.actor_user_id.in_(seed_user_ids)))

        # Inkmatch flow
        session.execute(delete(InkmatchReview).where(
            InkmatchReview.inkmatch_id.in_(
                select(Inkmatch.id).where(
                    (Inkmatch.client_request_id.in_(request_ids)) | (Inkmatch.master_request_id.in_(request_ids))
                )
            )
        ))
        session.execute(delete(Inkmatch).where(
            (Inkmatch.client_request_id.in_(request_ids)) | (Inkmatch.master_request_id.in_(request_ids)) | (Inkmatch.sketch_id.in_(sketch_ids))
        ))
        session.execute(delete(ClientInkmatchParams).where(ClientInkmatchParams.request_id.in_(request_ids)))
        session.execute(delete(MasterInkmatchOffer).where(MasterInkmatchOffer.request_id.in_(request_ids)))
        session.execute(delete(InkmatchRequest).where(InkmatchRequest.created_by_user_id.in_(seed_user_ids)))

        # Sketch graph
        session.execute(delete(SketchCommentLike).where(
            SketchCommentLike.user_id.in_(seed_user_ids)
        ))
        session.execute(delete(SketchLike).where(SketchLike.user_id.in_(seed_user_ids)))
        session.execute(delete(SketchPin).where(SketchPin.pinned_by_user_id.in_(seed_user_ids)))
        session.execute(delete(FeedPreferredTag).where(FeedPreferredTag.user_id.in_(seed_user_ids)))
        session.execute(delete(FeedPreferredStyle).where(FeedPreferredStyle.user_id.in_(seed_user_ids)))
        session.execute(delete(CollectionItem).where(
            CollectionItem.collection_id.in_(
                select(Collection.id).where(Collection.owner_id.in_(seed_user_ids))
            )
        ))
        session.execute(delete(Collection).where(Collection.owner_id.in_(seed_user_ids)))
        session.execute(delete(CommentAttachment).where(
            CommentAttachment.comment_id.in_(
                select(SketchComment.id).where(SketchComment.author_user_id.in_(seed_user_ids))
            )
        ))
        session.execute(delete(SketchComment).where(SketchComment.author_user_id.in_(seed_user_ids)))
        session.execute(delete(SketchMedia).where(SketchMedia.sketch_id.in_(sketch_ids)))
        session.execute(delete(SketchStyle).where(SketchStyle.sketch_id.in_(sketch_ids)))
        session.execute(delete(SketchTag).where(SketchTag.sketch_id.in_(sketch_ids)))
        session.execute(delete(Sketch).where(
            (Sketch.author_id.in_(seed_user_ids)) | (Sketch.original_author_user_id.in_(seed_user_ids))
        ))

        session.execute(delete(AuditEventTarget).where(
            AuditEventTarget.target_id.in_(seed_user_ids)
        ))

        session.execute(delete(User).where(User.id.in_(seed_user_ids)))
        session.commit()

        print("Seed users and dependent records removed.")


if __name__ == "__main__":
    cleanup_seed_users()
