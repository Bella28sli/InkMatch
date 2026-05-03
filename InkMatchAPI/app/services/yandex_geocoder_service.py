from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.core.config import settings


class YandexGeocoderError(Exception):
    pass


def _component_name(components: list[dict[str, Any]], *kinds: str) -> str | None:
    for kind in kinds:
        for component in components:
            if component.get('kind') == kind:
                name = (component.get('name') or '').strip()
                if name:
                    return name
    return None


def _precision_level(meta: dict[str, Any]) -> str:
    kind = meta.get('kind')
    precision = meta.get('precision')
    if kind in {'house', 'street'} or precision == 'exact':
        return 'exact'
    if kind == 'locality':
        return 'locality'
    if kind in {'province', 'area', 'district'}:
        return 'region'
    return 'exact'


def _parse_feature(feature: dict[str, Any]) -> dict[str, Any] | None:
    geo_object = feature.get('GeoObject') or {}
    point = geo_object.get('Point') or {}
    pos = (point.get('pos') or '').split()
    if len(pos) != 2:
        return None

    try:
        lon = float(pos[0])
        lat = float(pos[1])
    except ValueError:
        return None

    meta = (
        geo_object.get('metaDataProperty', {})
        .get('GeocoderMetaData', {})
    )
    address = meta.get('Address') or {}
    components = address.get('Components') or []
    country = _component_name(components, 'country')
    region = _component_name(components, 'province', 'area', 'district')
    locality = _component_name(components, 'locality')
    street = _component_name(components, 'street')
    house = _component_name(components, 'house')

    address_line_parts = [street, house]
    address_line = ', '.join([part for part in address_line_parts if part]) or None
    display_label = (
        (meta.get('text') or '').strip()
        or (geo_object.get('name') or '').strip()
        or ', '.join([part for part in [address_line, locality, region, country] if part])
    )
    short_label = ', '.join([part for part in [locality, region] if part]) or None

    return {
        'country': country,
        'region': region,
        'locality': locality,
        'address_line': address_line,
        'postal_code': address.get('postal_code'),
        'lat': lat,
        'lon': lon,
        'precision_level': _precision_level(meta),
        'provider': 'yandex',
        'provider_place_id': geo_object.get('uri'),
        'display_label': display_label,
        'short_label': short_label,
    }


def geocode(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    if not settings.yandex_geocoder_api_key:
        raise YandexGeocoderError('Yandex Geocoder is not configured: YANDEX_GEOCODER_API_KEY is missing')

    normalized_query = query.strip()
    if not normalized_query:
        return []

    params = urllib.parse.urlencode({
        'apikey': settings.yandex_geocoder_api_key,
        'geocode': normalized_query,
        'format': 'json',
        'lang': 'ru_RU',
        'results': limit,
    })
    url = f'https://geocode-maps.yandex.ru/1.x/?{params}'

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            raw = response.read().decode('utf-8')
            payload = json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='ignore')
        raise YandexGeocoderError(f'Yandex Geocoder request failed: {detail or exc.code}') from exc
    except urllib.error.URLError as exc:
        raise YandexGeocoderError('Yandex Geocoder is unreachable') from exc
    except json.JSONDecodeError as exc:
        raise YandexGeocoderError('Yandex Geocoder returned invalid JSON') from exc

    if payload.get('error'):
        detail = payload.get('error', {}).get('message') or payload.get('error')
        raise YandexGeocoderError(f'Yandex Geocoder request failed: {detail}')

    members = (
        payload.get('response', {})
        .get('GeoObjectCollection', {})
        .get('featureMember', [])
    )
    candidates = [_parse_feature(member) for member in members]
    return [candidate for candidate in candidates if candidate is not None]
