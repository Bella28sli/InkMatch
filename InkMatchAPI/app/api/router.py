from fastapi import APIRouter

from app.api.routes import (
    account,
    appeals,
    auth,
    catalogs,
    chats,
    collections,
    complaints,
    inkmatch,
    locations,
    moderation,
    notifications,
    posts,
    profiles,
    sketches,
    subscriptions,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix='/auth', tags=['auth'])
api_router.include_router(account.router, prefix='/account', tags=['account'])
api_router.include_router(appeals.router, prefix='/appeals', tags=['appeals'])
api_router.include_router(users.router, prefix='/users', tags=['users'])
api_router.include_router(profiles.router, prefix='/profiles', tags=['profiles'])
api_router.include_router(collections.router, prefix='/collections', tags=['collections'])
api_router.include_router(complaints.router, prefix='/complaints', tags=['complaints'])
api_router.include_router(posts.router, prefix='/posts', tags=['posts'])
api_router.include_router(sketches.router, prefix='/sketches', tags=['sketches'])
api_router.include_router(catalogs.router, prefix='/catalogs', tags=['catalogs'])
api_router.include_router(locations.router, prefix='/geo', tags=['locations'])
api_router.include_router(moderation.router, prefix='/moderation', tags=['moderation'])
api_router.include_router(chats.router, prefix='/chats', tags=['chats'])
api_router.include_router(notifications.router, prefix='/notifications', tags=['notifications'])
api_router.include_router(inkmatch.router, prefix='/inkmatch', tags=['inkmatch'])
api_router.include_router(subscriptions.router, prefix='/subscriptions', tags=['subscriptions'])
