from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.sketches import Style, Tag
from app.schemas.catalog import StyleIn, StyleOut, TagIn, TagOut

router = APIRouter()

_STYLE_RU = {
    'abstract': 'Абстракт',
    'blackgray': 'Черно-серый',
    'blackwork': 'Блэкворк',
    'fineline': 'Тонкая линия',
    'nature': 'Природа',
    'neotrad': 'Неотрадишнл',
    'oldschool': 'Олдскул',
    'realism': 'Реализм',
    'trashpolka': 'Трэш-полька',
}

_TAG_RU = {
    'animals': 'Животные',
    'anime': 'Аниме',
    'cyberpunk': 'Киберпанк',
    'flowers': 'Цветы',
    'gothic': 'Готика',
    'lettering': 'Леттеринг',
    'mini': 'Мини',
    'ornamental': 'Орнамент',
    'zodiac': 'Зодиак',
}



def _style_name(name: str, lang: str) -> str:
    if lang == 'ru':
        return _STYLE_RU.get(name.lower(), name)
    return name


def _tag_name(name: str, lang: str) -> str:
    if lang == 'ru':
        return _TAG_RU.get(name.lower(), name)
    return name



@router.get('/styles', response_model=list[StyleOut])
def list_styles(lang: str = 'ru', db: Session = Depends(get_db), _current_user=Depends(get_current_user)):
    rows = db.execute(select(Style).order_by(Style.name.asc())).scalars().all()
    return [{'id': str(r.id), 'name': _style_name(r.name, lang), 'description': r.description} for r in rows]


@router.post('/styles', response_model=StyleOut, status_code=status.HTTP_201_CREATED)
def create_style(payload: StyleIn, db: Session = Depends(get_db), _current_user=Depends(get_current_user)):
    row = Style(name=payload.name.strip(), description=payload.description)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'id': str(row.id), 'name': row.name, 'description': row.description}


@router.patch('/styles/{style_id}', response_model=StyleOut)
def update_style(style_id: str, payload: StyleIn, db: Session = Depends(get_db), _current_user=Depends(get_current_user)):
    row = db.execute(select(Style).where(Style.id == style_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Style not found')
    row.name = payload.name.strip()
    row.description = payload.description
    db.commit()
    db.refresh(row)
    return {'id': str(row.id), 'name': row.name, 'description': row.description}


@router.delete('/styles/{style_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_style(style_id: str, db: Session = Depends(get_db), _current_user=Depends(get_current_user)):
    row = db.execute(select(Style).where(Style.id == style_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Style not found')
    db.delete(row)
    db.commit()
    return None


@router.get('/tags', response_model=list[TagOut])
def list_tags(lang: str = 'ru', db: Session = Depends(get_db), _current_user=Depends(get_current_user)):
    rows = db.execute(select(Tag).order_by(Tag.name.asc())).scalars().all()
    return [{'id': str(r.id), 'name': _tag_name(r.name, lang)} for r in rows]


@router.post('/tags', response_model=TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagIn, db: Session = Depends(get_db), _current_user=Depends(get_current_user)):
    row = Tag(name=payload.name.strip())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'id': str(row.id), 'name': row.name}


@router.patch('/tags/{tag_id}', response_model=TagOut)
def update_tag(tag_id: str, payload: TagIn, db: Session = Depends(get_db), _current_user=Depends(get_current_user)):
    row = db.execute(select(Tag).where(Tag.id == tag_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tag not found')
    row.name = payload.name.strip()
    db.commit()
    db.refresh(row)
    return {'id': str(row.id), 'name': row.name}


@router.delete('/tags/{tag_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: str, db: Session = Depends(get_db), _current_user=Depends(get_current_user)):
    row = db.execute(select(Tag).where(Tag.id == tag_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Tag not found')
    db.delete(row)
    db.commit()
    return None
