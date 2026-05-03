from __future__ import annotations

import json
import os
import re
import tarfile
import tempfile
import urllib.request

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.locations import Location, MetroStation
from app.models.sketches import Style, Tag
from app.models.enums import LocationPrecisionLevel, LocationProvider
from app.services.yandex_geocoder_service import YandexGeocoderError, geocode


STYLES = [
    "abstract",
    "blackgray",
    "blackwork",
    "fineline",
    "nature",
    "neotrad",
    "oldschool",
    "realism",
    "trashpolka",
]

TAGS = [
    "animals",
    "anime",
    "cyberpunk",
    "flowers",
    "gothic",
    "lettering",
    "mini",
    "ornamental",
    "zodiac",
]

LOCATIONS = [
    {
        "country": "Россия",
        "region": "Москва",
        "locality": "Москва",
        "address_line": None,
        "postal_code": None,
        "lat": 55.7558,
        "lon": 37.6173,
        "precision_level": LocationPrecisionLevel.locality,
        "provider": LocationProvider.manual,
        "provider_place_id": "moscow",
    },
    {
        "country": "Россия",
        "region": "Санкт-Петербург",
        "locality": "Санкт-Петербург",
        "address_line": None,
        "postal_code": None,
        "lat": 59.9343,
        "lon": 30.3351,
        "precision_level": LocationPrecisionLevel.locality,
        "provider": LocationProvider.manual,
        "provider_place_id": "spb",
    },
    {
        "country": "Россия",
        "region": "Республика Татарстан",
        "locality": "Казань",
        "address_line": None,
        "postal_code": None,
        "lat": 55.7961,
        "lon": 49.1064,
        "precision_level": LocationPrecisionLevel.locality,
        "provider": LocationProvider.manual,
        "provider_place_id": "kazan",
    },
    {
        "country": "Россия",
        "region": "Свердловская область",
        "locality": "Екатеринбург",
        "address_line": None,
        "postal_code": None,
        "lat": 56.8389,
        "lon": 60.6057,
        "precision_level": LocationPrecisionLevel.locality,
        "provider": LocationProvider.manual,
        "provider_place_id": "ekaterinburg",
    },
    {
        "country": "Россия",
        "region": "Нижегородская область",
        "locality": "Нижний Новгород",
        "address_line": None,
        "postal_code": None,
        "lat": 56.3269,
        "lon": 44.0059,
        "precision_level": LocationPrecisionLevel.locality,
        "provider": LocationProvider.manual,
        "provider_place_id": "nizhny_novgorod",
    },
    {
        "country": "Россия",
        "region": "Новосибирская область",
        "locality": "Новосибирск",
        "address_line": None,
        "postal_code": None,
        "lat": 55.0084,
        "lon": 82.9357,
        "precision_level": LocationPrecisionLevel.locality,
        "provider": LocationProvider.manual,
        "provider_place_id": "novosibirsk",
    },
    {
        "country": "Россия",
        "region": "Самарская область",
        "locality": "Самара",
        "address_line": None,
        "postal_code": None,
        "lat": 53.1959,
        "lon": 50.1008,
        "precision_level": LocationPrecisionLevel.locality,
        "provider": LocationProvider.manual,
        "provider_place_id": "samara",
    },
]

RIOASKOV_METRO_URL = 'https://registry.npmjs.org/@riaskov/metro-ru/-/metro-ru-1.0.21.tgz'
RIOASKOV_CITY_VARS = {
    'moscow': 'e',
    'spb': 'u',
    'kazan': 'g',
    'ekaterinburg': 'A',
}

MANUAL_METRO_LINES = {
    'nizhny_novgorod': [
        ('Автозаводская', '#D42B2B', [
            'Парк культуры', 'Кировская', 'Комсомольская', 'Автозаводская',
            'Пролетарская', 'Двигатель Революции', 'Заречная', 'Ленинская',
            'Чкаловская', 'Московская', 'Горьковская',
        ]),
        ('Сормовско-Мещерская', '#1E88E5', [
            'Буревестник', 'Бурнаковская', 'Канавинская', 'Московская', 'Стрелка',
        ]),
    ],
    'novosibirsk': [
        ('Ленинская', '#D42B2B', [
            'Заельцовская', 'Гагаринская', 'Красный проспект', 'Площадь Ленина',
            'Октябрьская', 'Речной вокзал', 'Студенческая', 'Площадь Маркса',
        ]),
        ('Дзержинская', '#2E9D47', [
            'Площадь Гарина-Михайловского', 'Сибирская', 'Маршала Покрышкина',
            'Берёзовая роща', 'Золотая Нива',
        ]),
    ],
    'samara': [
        ('Первая', '#D42B2B', [
            'Юнгородок', 'Кировская', 'Безымянка', 'Победа', 'Советская',
            'Спортивная', 'Гагаринская', 'Московская', 'Российская', 'Алабинская',
        ]),
    ],
}


def seed_styles(session):
    existing = set(session.execute(select(Style.name)).scalars().all())
    for name in STYLES:
        if name not in existing:
            session.add(Style(name=name))


def seed_tags(session):
    existing = set(session.execute(select(Tag.name)).scalars().all())
    for name in TAGS:
        if name not in existing:
            session.add(Tag(name=name))


def seed_locations(session):
    existing = {
        (l.country, l.region, l.locality)
        for l in session.execute(select(Location)).scalars().all()
    }
    created = {}
    for item in LOCATIONS:
        key = (item["country"], item["region"], item["locality"])
        if key in existing:
            # fetch existing for metro mapping
            loc = (
                session.execute(
                    select(Location).where(
                        Location.country == item["country"],
                        Location.region == item["region"],
                        Location.locality == item["locality"],
                    )
                )
                .scalars()
                .first()
            )
            if loc:
                created[item["provider_place_id"]] = loc.id
            continue
        loc = Location(**item)
        session.add(loc)
        session.flush()
        created[item["provider_place_id"]] = loc.id
    return created


def _download_riaskov_bundle() -> str | None:
    try:
        fd, archive_path = tempfile.mkstemp(suffix='.tgz')
        os.close(fd)
        urllib.request.urlretrieve(RIOASKOV_METRO_URL, archive_path)
        with tarfile.open(archive_path, 'r:gz') as archive:
            member = archive.extractfile('package/dist/esm/metro-ru.min.mjs')
            if member is None:
                return None
            return member.read().decode('utf-8')
    except Exception:
        return None


def _extract_js_array(bundle: str, variable: str) -> str | None:
    match = re.search(r'(?:var [^;=]*|,)' + variable + r'=\[', bundle)
    if not match:
        return None

    start = bundle.find('[', match.start())
    depth = 0
    for index in range(start, len(bundle)):
        if bundle[index] == '[':
            depth += 1
        elif bundle[index] == ']':
            depth -= 1
            if depth == 0:
                return bundle[start + 1:index]
    return None


def _parse_js_station_array(raw: str, city_key: str) -> list[dict]:
    rows = []
    for match in re.finditer(r'\{([^{}]+)\}', raw):
        text = match.group(1)

        def value(key: str):
            value_match = re.search(key + r':(?:(\"[^\"]*\")|([^,}]+))', text)
            if not value_match:
                return None
            raw_value = (value_match.group(1) or value_match.group(2)).strip()
            if raw_value.startswith('"'):
                return json.loads(raw_value)
            if re.match(r'^-?\d+(\.\d+)?$', raw_value):
                return float(raw_value)
            return raw_value

        color = value('LineColor') or '#777777'
        if isinstance(color, str) and not color.startswith('#'):
            color = f'#{color}'
        rows.append({
            'city_key': city_key,
            'name': value('Name'),
            'line_name': value('Line'),
            'lat': value('Lat'),
            'lon': value('Lon'),
            'color_hex': color,
        })
    return rows


def _load_riaskov_metro() -> list[dict]:
    bundle = _download_riaskov_bundle()
    if not bundle:
        return []

    rows: list[dict] = []
    for city_key, variable in RIOASKOV_CITY_VARS.items():
        raw = _extract_js_array(bundle, variable)
        if raw:
            rows.extend(_parse_js_station_array(raw, city_key))
    return rows


def _manual_metro_rows() -> list[dict]:
    rows = []
    for city_key, lines in MANUAL_METRO_LINES.items():
        for line_name, color_hex, stations in lines:
            for station in stations:
                rows.append({
                    'city_key': city_key,
                    'name': station,
                    'line_name': line_name,
                    'lat': None,
                    'lon': None,
                    'color_hex': color_hex,
                })
    return rows


def _city_by_id(session, city_id):
    return session.execute(select(Location).where(Location.id == city_id)).scalar_one_or_none()


def _resolve_station_coordinates(session, city_id, item: dict) -> tuple[float, float]:
    if item.get('lat') is not None and item.get('lon') is not None:
        return float(item['lat']), float(item['lon'])

    city = _city_by_id(session, city_id)
    if city:
        try:
            candidates = geocode(f'Россия, {city.locality}, метро {item["name"]}', limit=1)
            if candidates:
                return float(candidates[0]['lat']), float(candidates[0]['lon'])
        except (YandexGeocoderError, KeyError, TypeError, ValueError):
            pass
        return float(city.lat), float(city.lon)
    return 0.0, 0.0


def seed_metro(session, city_map):
    existing = {
        (str(row.city_location_id), row.name, row.line_name)
        for row in session.execute(select(MetroStation)).scalars().all()
    }
    for item in [*_load_riaskov_metro(), *_manual_metro_rows()]:
        city_id = city_map.get(item['city_key'])
        if not city_id:
            continue
        key = (str(city_id), item['name'], item['line_name'])
        if key in existing:
            continue
        lat, lon = _resolve_station_coordinates(session, city_id, item)
        session.add(
            MetroStation(
                city_location_id=city_id,
                name=item['name'],
                line_name=item['line_name'],
                lat=lat,
                lon=lon,
                color_hex=item['color_hex'],
            )
        )


def main():
    session = SessionLocal()
    try:
        seed_styles(session)
        seed_tags(session)
        city_map = seed_locations(session)
        seed_metro(session, city_map)
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    main()
