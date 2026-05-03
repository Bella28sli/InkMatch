import json
from urllib import error, request

from app.core.config import settings


class FirebaseAuthError(Exception):
    pass


def _firebase_api_url(method: str) -> str:
    if not settings.firebase_web_api_key:
        raise FirebaseAuthError('Firebase is not configured: FIREBASE_WEB_API_KEY is missing')
    return f'https://identitytoolkit.googleapis.com/v1/accounts:{method}?key={settings.firebase_web_api_key}'


def _post(method: str, payload: dict) -> dict:
    url = _firebase_api_url(method)
    body = json.dumps(payload).encode('utf-8')
    req = request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    try:
        with request.urlopen(req, timeout=15) as response:
            raw = response.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='ignore')
        detail = raw
        try:
            parsed = json.loads(raw)
            detail = parsed.get('error', {}).get('message', raw)
        except Exception:
            pass
        raise FirebaseAuthError(f'Firebase request failed: {detail}') from exc
    except error.URLError as exc:
        raise FirebaseAuthError('Firebase is unreachable') from exc


def send_password_reset_email(email: str) -> None:
    _post('sendOobCode', {'requestType': 'PASSWORD_RESET', 'email': email})


def confirm_password_reset(oob_code: str, new_password: str) -> str:
    data = _post('resetPassword', {'oobCode': oob_code, 'newPassword': new_password})
    email = (data.get('email') or '').strip().lower()
    if not email:
        raise FirebaseAuthError('Firebase did not return email for reset operation')
    return email


def ensure_user_exists(email: str) -> None:
    # Firebase user is required to send reset email via Firebase Auth.
    try:
        _post('signUp', {
            'email': email,
            'password': 'Temp#123456',
            'returnSecureToken': False,
        })
    except FirebaseAuthError as exc:
        if 'EMAIL_EXISTS' in str(exc):
            return
        raise
