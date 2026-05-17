from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.sketches import Style, Tag


STYLES = [
    "Абстракция",
    "Азия",
    "Акварель",
    "Биомеханика",
    "Блэкаут",
    "Блэк-н-грэй",
    "Блэкворк",
    "Ботаника",
    "Браш",
    "Восточный",
    "Геометрия",
    "Гравюра",
    "Готика",
    "Дотворк",
    "Иллюстративный",
    "Каллиграфия",
    "Киберсигил",
    "Коллаж",
    "Комикс",
    "Космический",
    "Лайнворк",
    "Минимализм",
    "Микрореализм",
    "Мозаика",
    "Набросок",
    "Нео-традишнл",
    "Нео-японский",
    "Новый скул",
    "Олдскул",
    "Орнаментал",
    "Пейзаж",
    "Пинап",
    "Портрет",
    "Реализм",
    "Скетч",
    "Стимпанк",
    "Стрэйт-лайн",
    "Сюрреализм",
    "Трайбл",
    "Треш-полька",
    "Традишнл",
    "Флора",
    "Хэндпоук",
    "Хоррор",
    "Хэви чёрный",
    "Чернила и тень",
    "Чикано",
    "Штриховка",
    "Японский",
]

TAGS = [
    "Абстрактные формы",
    "Аниме",
    "Архитектура",
    "Астрология",
    "Бабочки",
    "Берёзы",
    "Библия",
    "Бисер",
    "Волки",
    "Вороны",
    "Глаз",
    "Город",
    "Готика",
    "Демон",
    "Деревья",
    "Драконы",
    "Египет",
    "Животные",
    "Жемчуг",
    "Звёзды",
    "Зодиак",
    "Змея",
    "Игральные карты",
    "Кинжал",
    "Космос",
    "Кошки",
    "Крест",
    "Крылья",
    "Луна",
    "Листья",
    "Лотос",
    "Магия",
    "Маска",
    "Месяц",
    "Мини",
    "Мистика",
    "Море",
    "Нежность",
    "Нож",
    "Огонь",
    "Орнамент",
    "Паутина",
    "Пейзаж",
    "Птицы",
    "Планеты",
    "Пчёлы",
    "Растения",
    "Розы",
    "Романтика",
    "Руна",
    "Свечи",
    "Сердца",
    "Скелет",
    "Сны",
    "Солнце",
    "Стилизация",
    "Тёмная фантазия",
    "Тени",
    "Тату-эскиз",
    "Треугольники",
    "Тропики",
    "Травы",
    "Цветы",
    "Череп",
    "Шипы",
    "Эзотерика",
    "Ювелирное",
]


def seed_styles(session):
    existing = {name.strip().lower() for name in session.execute(select(Style.name)).scalars().all()}
    for name in STYLES:
        normalized = name.strip().lower()
        if normalized not in existing:
            session.add(Style(name=normalized))
            existing.add(normalized)


def seed_tags(session):
    existing = {name.strip().lower() for name in session.execute(select(Tag.name)).scalars().all()}
    for name in TAGS:
        normalized = name.strip().lower()
        if normalized not in existing:
            session.add(Tag(name=normalized))
            existing.add(normalized)


def main():
    session = SessionLocal()
    try:
        seed_styles(session)
        seed_tags(session)
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    main()
