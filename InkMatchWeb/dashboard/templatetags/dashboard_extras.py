from django import template
from datetime import date, datetime

register = template.Library()


@register.filter
def get_item(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return None


@register.filter
def date_input(value):
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d')
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10]).isoformat()
        except Exception:
            return ''
    return ''


@register.filter
def datetime_input(value):
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%dT%H:%M')
    if isinstance(value, str):
        raw = value.replace('Z', '+00:00')
        try:
            return datetime.fromisoformat(raw).strftime('%Y-%m-%dT%H:%M')
        except Exception:
            return ''
    return ''


@register.filter
def time_input(value):
    if isinstance(value, datetime):
        return value.strftime('%H:%M')
    if isinstance(value, str):
        try:
            return value[:5]
        except Exception:
            return ''
    return ''


@register.filter
def truncate_cell(value, length=28):
    if value is None:
        return ''
    text = str(value)
    if len(text) <= length:
        return text
    return text[: length - 1] + '...'


