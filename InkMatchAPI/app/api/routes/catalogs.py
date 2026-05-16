from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.sketches import SketchStyle, SketchTag, Style, Tag
from app.schemas.catalog import StyleIn, StyleOut, TagIn, TagOut

router = APIRouter()

_STYLE_EN = {
    'Абстракция': 'Abstract',
    'Азия': 'Asian',
    'Акварель': 'Watercolor',
    'Биомеханика': 'Biomechanical',
    'Блэкаут': 'Blackout',
    'Блэк-н-грэй': 'Black and Grey',
    'Блэкворк': 'Blackwork',
    'Ботаника': 'Botanical',
    'Браш': 'Brush',
    'Восточный': 'Oriental',
    'Геометрия': 'Geometric',
    'Гравюра': 'Etching',
    'Готика': 'Gothic',
    'Дотворк': 'Dotwork',
    'Иллюстративный': 'Illustrative',
    'Каллиграфия': 'Script',
    'Киберсигил': 'Cybersigil',
    'Коллаж': 'Collage',
    'Комикс': 'Comic',
    'Космический': 'Space',
    'Лайнворк': 'Linework',
    'Минимализм': 'Minimalism',
    'Микрореализм': 'Microrealism',
    'Мозаика': 'Mosaic',
    'Набросок': 'Sketch',
    'Нео-традишнл': 'Neo-traditional',
    'Нео-японский': 'Neo-Japanese',
    'Новый скул': 'New School',
    'Олдскул': 'Old School',
    'Орнаментал': 'Ornamental',
    'Пейзаж': 'Landscape',
    'Пинап': 'Pin-up',
    'Портрет': 'Portrait',
    'Реализм': 'Realism',
    'Скетч': 'Sketch',
    'Стимпанк': 'Steampunk',
    'Стрэйт-лайн': 'Straight Line',
    'Сюрреализм': 'Surrealism',
    'Трайбл': 'Tribal',
    'Треш-полька': 'Trash Polka',
    'Традишнл': 'Traditional',
    'Флора': 'Floral',
    'Хэндпоук': 'Handpoke',
    'Хоррор': 'Horror',
    'Хэви чёрный': 'Heavy Black',
    'Чернила и тень': 'Ink and Shadow',
    'Чикано': 'Chicano',
    'Штриховка': 'Shading',
    'Японский': 'Japanese',
}

_TAG_EN = {
    'Абстрактные формы': 'Abstract shapes',
    'Аниме': 'Anime',
    'Архитектура': 'Architecture',
    'Астрология': 'Astrology',
    'Бабочки': 'Butterflies',
    'Берёзы': 'Birch',
    'Библия': 'Bible',
    'Бисер': 'Beads',
    'Волки': 'Wolves',
    'Вороны': 'Ravens',
    'Глаз': 'Eye',
    'Город': 'City',
    'Готика': 'Gothic',
    'Демон': 'Demon',
    'Деревья': 'Trees',
    'Драконы': 'Dragons',
    'Египет': 'Egypt',
    'Животные': 'Animals',
    'Жемчуг': 'Pearls',
    'Звёзды': 'Stars',
    'Зодиак': 'Zodiac',
    'Змея': 'Snake',
    'Игральные карты': 'Playing cards',
    'Кинжал': 'Dagger',
    'Космос': 'Space',
    'Кошки': 'Cats',
    'Крест': 'Cross',
    'Крылья': 'Wings',
    'Луна': 'Moon',
    'Листья': 'Leaves',
    'Лотос': 'Lotus',
    'Магия': 'Magic',
    'Маска': 'Mask',
    'Месяц': 'Crescent',
    'Мини': 'Mini',
    'Мистика': 'Mystic',
    'Море': 'Ocean',
    'Нежность': 'Tenderness',
    'Нож': 'Knife',
    'Огонь': 'Fire',
    'Орнамент': 'Ornament',
    'Паутина': 'Web',
    'Пейзаж': 'Landscape',
    'Птицы': 'Birds',
    'Планеты': 'Planets',
    'Пчёлы': 'Bees',
    'Растения': 'Plants',
    'Розы': 'Roses',
    'Романтика': 'Romance',
    'Руна': 'Rune',
    'Свечи': 'Candles',
    'Сердца': 'Hearts',
    'Скелет': 'Skeleton',
    'Сны': 'Dreams',
    'Солнце': 'Sun',
    'Стилизация': 'Stylization',
    'Тёмная фантазия': 'Dark fantasy',
    'Тени': 'Shadows',
    'Тату-эскиз': 'Tattoo sketch',
    'Треугольники': 'Triangles',
    'Тропики': 'Tropics',
    'Травы': 'Herbs',
    'Цветы': 'Flowers',
    'Череп': 'Skull',
    'Шипы': 'Thorns',
    'Эзотерика': 'Esoterica',
    'Ювелирное': 'Jewelry',
}


def _style_name(name: str, lang: str) -> str:
    normalized = name.strip()
    if lang == 'en':
        return _STYLE_EN.get(normalized, normalized)
    return normalized


def _tag_name(name: str, lang: str) -> str:
    normalized = name.strip()
    if lang == 'en':
        return _TAG_EN.get(normalized, normalized)
    return normalized


@router.get('/styles', response_model=list[StyleOut])
def list_styles(lang: str = 'ru', db: Session = Depends(get_db), _current_user=Depends(get_current_user)):
    rows = (
        db.execute(
            select(
                Style,
                func.count(distinct(SketchStyle.sketch_id)).label('post_count'),
            )
            .outerjoin(SketchStyle, SketchStyle.style_id == Style.id)
            .group_by(Style.id)
            .order_by(func.count(distinct(SketchStyle.sketch_id)).desc(), Style.name.asc())
        )
        .all()
    )
    return [
        {
            'id': str(style.id),
            'name': _style_name(style.name, lang),
            'description': style.description,
            'post_count': int(post_count or 0),
        }
        for style, post_count in rows
    ]


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
    rows = (
        db.execute(
            select(
                Tag,
                func.count(distinct(SketchTag.sketch_id)).label('post_count'),
            )
            .outerjoin(SketchTag, SketchTag.tag_id == Tag.id)
            .group_by(Tag.id)
            .order_by(func.count(distinct(SketchTag.sketch_id)).desc(), Tag.name.asc())
        )
        .all()
    )
    return [
        {
            'id': str(tag.id),
            'name': _tag_name(tag.name, lang),
            'post_count': int(post_count or 0),
        }
        for tag, post_count in rows
    ]


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
