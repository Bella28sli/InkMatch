from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.enums import NotificationType, UserRole
from app.schemas.auth import (
    ChangePasswordIn,
    NicknameCheckOut,
    LoginIn,
    RefreshIn,
    RegisterIn,
    RegisterOut,
    VerifyConfirmIn,
    VerifyBypassIn,
    VerifyCancelIn,
    VerifyRequestIn,
    ResetConfirmIn,
    ResetRequestIn,
    ResetVerifyIn,
    TokenOut,
)
from app.schemas.user import UserOut
from app.models.user import User
from app.models.profiles import Profile
from app.services.notification_service import create_notification
from app.services.email_service import (
    EmailServiceError,
    send_password_reset_email,
    send_verification_email,
)
from app.services.auth_service import (
    confirm_verification_code,
    consume_verification_code,
    create_verification_code,
    _cleanup_pending_registration,
    _finalize_pending_registration,
    _issue_pending_code,
    inspect_preference_resolution,
    get_user_by_login,
    get_pending_registration_by_token,
    issue_tokens,
    login_user,
    refresh_access_token,
    register_user,
    revoke_refresh_token,
    verify_verification_code,
)
from app.core.security import hash_password, verify_password

router = APIRouter()


def _registration_error_detail(db: Session, error: str, payload: RegisterIn) -> dict:
    preference_debug = inspect_preference_resolution(
        db,
        payload.preferred_style_ids,
        payload.preferred_tag_ids,
    )
    base = {
        'error': error,
        'role': payload.role,
        'email_present': bool(payload.email),
        'phone_present': bool(payload.phone),
        'nickname': payload.profile.nickname,
        'styles_count': len(payload.preferred_style_ids),
        'tags_count': len(payload.preferred_tag_ids),
        'styles': payload.preferred_style_ids,
        'tags': payload.preferred_tag_ids,
        'has_preferences': payload.preferences is not None,
        'has_master_profile': payload.master_profile is not None,
        'has_workplace': payload.workplace is not None,
        'preference_debug': preference_debug,
    }
    if payload.preferences:
        base['preferences'] = payload.preferences.model_dump()
    if payload.master_profile:
        base['master_profile'] = payload.master_profile.model_dump()
    if payload.workplace:
        base['workplace'] = payload.workplace.model_dump()
    return base


@router.get('/nickname-available', response_model=NicknameCheckOut)
def nickname_available(nickname: str = Query(min_length=2, max_length=64), db: Session = Depends(get_db)):
    exists = db.execute(
        select(Profile.user_id).where(func.lower(Profile.nickname) == nickname.strip().lower())
    ).scalar_one_or_none()
    return {'available': exists is None}


@router.get('/contact-available')
def contact_available(
    type: str = Query(pattern='^(email|phone)$'),
    value: str = Query(min_length=3, max_length=255),
    db: Session = Depends(get_db),
):
    normalized = value.strip().lower()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Value required')

    if type == 'email':
        exists = db.execute(select(User.id).where(func.lower(User.email) == normalized)).scalar_one_or_none()
    else:
        digits = ''.join(ch for ch in normalized if ch.isdigit() or ch == '+')
        exists = db.execute(select(User.id).where(User.phone == digits)).scalar_one_or_none()
    return {'available': exists is None}


@router.post('/register', response_model=RegisterOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    try:
        if payload.role not in {r.value for r in UserRole}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Некорректная роль',
            )
        if not payload.email and not payload.phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Требуется email или телефон',
            )

        user, error, registration_token = register_user(
            db,
            payload.email,
            payload.phone,
            payload.password,
            payload.role,
            payload.profile.model_dump(),
            payload.preferred_style_ids,
            payload.preferred_tag_ids,
            payload.preferences.model_dump() if payload.preferences else None,
            payload.master_profile.model_dump() if payload.master_profile else None,
            payload.workplace.model_dump() if payload.workplace else None,
        )

        if registration_token:
            pending = get_pending_registration_by_token(db, registration_token)
            if not pending or not (pending.email or payload.email):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail='Не удалось создать черновик регистрации',
                )
            try:
                code = _issue_pending_code(pending)
                db.flush()
                send_verification_email((pending.email or payload.email).strip(), code)
                db.commit()
            except EmailServiceError as exc:
                db.rollback()
                try:
                    _cleanup_pending_registration(db, pending)
                except Exception:
                    db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=str(exc),
                ) from exc
            return {
                'message': 'Не удалось создать черновик регистрации. Пожалуйста, попробуйте позже.',
                'registration_token': registration_token,
            }

        if not user:
            if error == 'conflict':
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail='Email или телефон уже зарегистрированы',
                )
            if error == 'nickname_conflict':
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail='Никнейм уже зарегистрирован',
                )
            if error in {'invalid_preferences', 'missing_master_profile', 'invalid_role'}:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        'message': 'Некорректные данные регистрации',
                        **_registration_error_detail(db, error, payload),
                    },
                )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Не удалось завершить регистрацию')

        create_notification(
            db,
            user_id=str(user.id),
            type_=NotificationType.system,
            title='Новая регистрация в InkMatch',
            body='Регистрация завершена. Проверьте почту и код в приложении.',
            deep_link='/login',
            send_push_too=False,
        )
        if user.phone and not user.email:
            create_notification(
                db,
                user_id=str(user.id),
                type_=NotificationType.system,
                title='Подтвердите email',
                body='Пожалуйста, подтвердите email, чтобы завершить регистрацию.',
                deep_link='/demo-settings',
                send_push_too=False,
            )
        db.commit()
        return {'message': 'Регистрация завершена. Войдите в аккаунт.'}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        try:
            debug_detail = _registration_error_detail(db, 'unexpected_exception', payload)
        except Exception as debug_exc:
            debug_detail = {
                'error': 'unexpected_exception',
                'debug_error': str(debug_exc),
                'role': payload.role,
                'nickname': payload.profile.nickname,
                'styles': payload.preferred_style_ids,
                'tags': payload.preferred_tag_ids,
            }
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                'message': 'Регистрация завершилась с ошибкой сервера',
                'exception': str(exc),
                **debug_detail,
            },
        ) from exc
@router.post('/login', response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = login_user(db, payload.login, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Неверные учетные данные',
        )
    if user.email and not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Email не подтвержден',
        )
    return issue_tokens(db, user)


@router.post('/refresh', response_model=TokenOut)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)):
    result = refresh_access_token(db, payload.refresh_token)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Неверный refresh-токен')
    return {**result, 'refresh_token': None}


@router.post('/logout', status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshIn, db: Session = Depends(get_db)):
    if not revoke_refresh_token(db, payload.refresh_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Неверный refresh-токен')
    return None


@router.get('/me', response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user


@router.post('/verify/request', status_code=status.HTTP_204_NO_CONTENT)
def verify_request(payload: VerifyRequestIn, db: Session = Depends(get_db)):
    login = payload.login.strip()
    if not login:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Требуется логин')

    if payload.registration_token:
        pending = get_pending_registration_by_token(db, payload.registration_token)
        if not pending or not pending.email:
            return None
        try:
            code = _issue_pending_code(pending)
            db.flush()
            send_verification_email(pending.email, code)
            db.commit()
        except EmailServiceError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
        return None

    user = get_user_by_login(db, login)
    if not user:
        return None

    if user.email:
        try:
            code = create_verification_code(db, user, 'email')
            send_verification_email(user.email, code)
        except EmailServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
        return None

    if user.phone:
        create_verification_code(db, user, 'phone')
        return None

    return None


@router.post('/verify/confirm', status_code=status.HTTP_204_NO_CONTENT)
def verify_confirm(payload: VerifyConfirmIn, db: Session = Depends(get_db)):
    login = payload.login.strip()
    code = payload.code.strip()
    if not login or not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Требуются логин и код')

    if payload.registration_token:
        pending = get_pending_registration_by_token(db, payload.registration_token)
        if not pending or not pending.email:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Черновик регистрации не найден')
        if pending.code != code or pending.code_expires_at is None or pending.code_expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Неверный код')
        user = _finalize_pending_registration(db, pending)
        if not user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Не удалось завершить регистрацию')
        create_notification(
            db,
            user_id=str(user.id),
            type_=NotificationType.system,
            title='Добро пожаловать в InkMatch',
            body='Регистрация завершена. Мы рады видеть вас в InkMatch.',
            deep_link='/feed',
            send_push_too=False,
        )
        db.commit()
        return None

    user = get_user_by_login(db, login)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Пользователь не найден')

    channel = 'email' if user.email else 'phone' if user.phone else 'email'
    if not confirm_verification_code(db, user, channel, code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Неверный код')
    return None


@router.post('/verify/bypass', status_code=status.HTTP_204_NO_CONTENT)
def verify_bypass(payload: VerifyBypassIn, db: Session = Depends(get_db)):
    login = payload.login.strip()
    if not login:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Требуется логин')

    if payload.registration_token:
        pending = get_pending_registration_by_token(db, payload.registration_token)
        if not pending or not pending.email:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Черновик регистрации не найден')
        user = _finalize_pending_registration(db, pending)
        if not user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Не удалось завершить регистрацию')
        create_notification(
            db,
            user_id=str(user.id),
            type_=NotificationType.system,
            title='Добро пожаловать в InkMatch',
            body='Регистрация завершена. Мы рады видеть вас в InkMatch.',
            deep_link='/feed',
            send_push_too=False,
        )
        db.commit()
        return None

    user = get_user_by_login(db, login)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Пользователь не найден')

    if user.email:
        user.is_verified = True
        db.commit()
    return None


@router.post('/verify/cancel', status_code=status.HTTP_204_NO_CONTENT)
def verify_cancel(payload: VerifyCancelIn, db: Session = Depends(get_db)):
    if payload.registration_token:
        pending = get_pending_registration_by_token(db, payload.registration_token)
        if pending:
            db.delete(pending)
            db.commit()
        return None
    login = (payload.login or '').strip()
    if not login:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Требуется логин')
    purge_unverified_email_registration(db, login)
    return None


@router.post('/change-password', status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Неверный старый пароль')
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()

    create_notification(
        db,
        user_id=str(current_user.id),
        type_=NotificationType.system,
            title='Пароль изменён',
            body='Пароль вашего аккаунта был изменён.',
        deep_link='/settings/account',
        send_push_too=False,
    )
    db.commit()
    return None


@router.post('/password/reset-request', status_code=status.HTTP_204_NO_CONTENT)
def reset_request(payload: ResetRequestIn, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    local_user = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
    if not local_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Пользователь с таким email не найден')
    try:
        code = create_verification_code(db, local_user, 'email')
        send_password_reset_email(local_user.email or email, code)
        return None
    except EmailServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post('/password/reset-verify', status_code=status.HTTP_204_NO_CONTENT)
def reset_verify(payload: ResetVerifyIn, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Пользователь с таким email не найден')
    if not verify_verification_code(db, user, 'email', payload.oob_code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Неверный код')
    return None


@router.post('/password/reset-confirm', status_code=status.HTTP_204_NO_CONTENT)
def reset_confirm(payload: ResetConfirmIn, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Пользователь с таким email не найден')
    if not consume_verification_code(db, user, 'email', payload.oob_code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Неверный код')

    user.password_hash = hash_password(payload.new_password)
    db.commit()

    create_notification(
        db,
        user_id=str(user.id),
        type_=NotificationType.system,
            title='Пароль изменён',
            body='Вы успешно изменили пароль.',
        deep_link='/login',
        send_push_too=False,
    )
    db.commit()
    return None
