from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.models.enums import NotificationType
from app.db.session import get_db
from app.schemas.collection import (
    CollectionCreateIn,
    CollectionItemIn,
    CollectionItemUpdateIn,
    CollectionListItemOut,
    CollectionOut,
    CollectionShareOut,
    CollectionUpdateIn,
)
from app.services.notification_service import create_notification, user_nickname
from app.services.collection_service import (
    add_collection_item,
    create_collection,
    delete_collection,
    get_collection_by_id,
    list_collections,
    remove_collection_item,
    save_collection_to_user,
    update_collection,
    update_collection_item_metadata,
)
from app.services.preference_weight_service import apply_preference_action

router = APIRouter()


@router.get('', response_model=list[CollectionListItemOut])
def get_collections(
    owner_id: str,
    section: str | None = None,
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_collections(db, owner_id, section)


@router.post('', response_model=CollectionOut, status_code=status.HTTP_201_CREATED)
def create_new_collection(
    payload: CollectionCreateIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = create_collection(
        db,
        str(current_user.id),
        payload.title,
        payload.description,
        payload.collection_type,
        payload.is_private,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Collection title is required')
    result = get_collection_by_id(db, str(row.id))
    result['can_edit'] = True
    return result


@router.get('/{collection_id}', response_model=CollectionOut)
def get_collection(
    collection_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = get_collection_by_id(db, collection_id)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Collection not found')

    is_owner = str(payload['owner_id']) == str(current_user.id)
    if payload['is_private'] and not is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Collection is private')

    payload['can_edit'] = is_owner
    return payload


@router.patch('/{collection_id}', response_model=CollectionOut)
def patch_collection(
    collection_id: str,
    payload: CollectionUpdateIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _updated, error = update_collection(
        db,
        collection_id,
        str(current_user.id),
        payload.title,
        payload.description,
        payload.is_private,
    )
    if error == 'not_found':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Collection not found')
    if error == 'forbidden':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    if error == 'title_locked':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Default collection title cannot be changed')
    if error == 'empty_title':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Collection title is required')

    result = get_collection_by_id(db, collection_id)
    result['can_edit'] = True
    return result


@router.delete('/{collection_id}', status_code=status.HTTP_204_NO_CONTENT)
def remove_collection(
    collection_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    error = delete_collection(db, collection_id, str(current_user.id))
    if error == 'not_found':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Collection not found')
    if error == 'forbidden':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    if error == 'system_locked':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='System collection cannot be deleted')
    return None


@router.post('/{collection_id}/items', status_code=status.HTTP_204_NO_CONTENT)
def add_item(
    collection_id: str,
    payload: CollectionItemIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    created = add_collection_item(
        db,
        collection_id,
        str(current_user.id),
        payload.sketch_id,
        payload.sort_order,
        work_duration_houres=payload.work_duration_houres,
        work_price=payload.work_price,
        currency=payload.currency,
        note=payload.note,
    )
    if created == 'not_found':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Collection not found')
    if created == 'forbidden':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    if created == 'forbidden_my_posts':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Only your own posts can be added to My posts',
        )
    if created == 'sketch_not_found':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Post not found')
    if created:
        apply_preference_action(db, str(current_user.id), payload.sketch_id, 'save')
    return None


@router.delete('/{collection_id}/items/{sketch_id}', status_code=status.HTTP_204_NO_CONTENT)
def remove_item(
    collection_id: str,
    sketch_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    error = remove_collection_item(db, collection_id, sketch_id, str(current_user.id))
    if error == 'not_found':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Collection not found')
    if error == 'forbidden':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    if error == 'item_not_found':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Collection item not found')
    return None


@router.patch('/{collection_id}/items/{sketch_id}', status_code=status.HTTP_204_NO_CONTENT)
def patch_item_metadata(
    collection_id: str,
    sketch_id: str,
    payload: CollectionItemUpdateIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    error = update_collection_item_metadata(
        db,
        collection_id,
        sketch_id,
        str(current_user.id),
        work_duration_houres=payload.work_duration_houres,
        work_price=payload.work_price,
        currency=payload.currency,
        note=payload.note,
    )
    if error == 'not_found':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Collection not found')
    if error == 'forbidden':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Forbidden')
    if error == 'item_not_found':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Collection item not found')
    return None


@router.post('/{collection_id}/share', response_model=CollectionShareOut)
def share_collection(
    collection_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = get_collection_by_id(db, collection_id)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Collection not found')
    is_owner = str(payload['owner_id']) == str(current_user.id)
    if payload['is_private'] and not is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Collection is private')

    return {'share_url': f'https://inkmatch.app/c/{collection_id}'}


@router.post('/{collection_id}/save', response_model=CollectionOut, status_code=status.HTTP_201_CREATED)
def save_collection(
    collection_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clone, error = save_collection_to_user(db, collection_id, str(current_user.id))
    if error == 'not_found':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Collection not found')
    if error == 'forbidden':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Collection is private')

    payload = get_collection_by_id(db, str(clone.id))
    payload['can_edit'] = True

    source = get_collection_by_id(db, collection_id)
    if source and str(source['owner_id']) != str(current_user.id):
        actor = user_nickname(db, str(current_user.id))
        create_notification(
            db,
            user_id=str(source['owner_id']),
            type_=NotificationType.system,
            title='Коллекция сохранена',
            body=f'{actor} сохранил(а) вашу коллекцию',
            deep_link=f'/collection/{collection_id}',
            links=[('collection', collection_id)],
        )
        db.commit()

    return payload
