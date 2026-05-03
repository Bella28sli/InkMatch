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
    VerifyRequestIn,
    ResetConfirmIn,
    ResetRequestIn,
    TokenOut,
)
from app.schemas.user import UserOut
from app.models.user import User
from app.models.profiles import Profile
from app.services.auth_service import (
    confirm_verification_code,
    create_verification_code,
    get_user_by_login,
    issue_tokens,
    login_user,
    refresh_access_token,
    register_user,
    revoke_refresh_token,
)
from app.core.security import hash_password, verify_password
from app.services.notification_service import create_notification
from app.services.email_service import EmailServiceError, send_verification_email
from app.services.firebase_auth_service import (
    FirebaseAuthError,
    confirm_password_reset,
    ensure_user_exists,
    send_password_reset_email,
)

router = APIRouter()


@router.get('/nickname-available', response_model=NicknameCheckOut)
def nickname_available(nickname: str = Query(min_length=2, max_length=64), db: Session = Depends(get_db)):
    exists = db.execute(
        select(Profile.user_id).where(func.lower(Profile.nickname) == nickname.strip().lower())
    ).scalar_one_or_none()
    return {'available': exists is None}


@router.post('/register', response_model=RegisterOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    if payload.role not in {r.value for r in UserRole}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid role',
        )
    if not payload.email and not payload.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Email or phone required',
        )
    user, error = register_user(
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
    if not user:
        if error == 'conflict':
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Email or phone already registered',
            )
        if error == 'nickname_conflict':
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Nickname already registered',
            )
        if error in {'invalid_preferences', 'missing_master_profile', 'invalid_role'}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invalid registration data',
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Registration failed',
        )
    create_notification(
        db,
        user_id=str(user.id),
        type_=NotificationType.system,
        title='Добро пожаловать в InkMatch',
        body='Регистрация завершена. Теперь вы можете войти в аккаунт.',
        deep_link='/login',
    )
    if user.email:
        try:
            code = create_verification_code(db, user, 'email')
            send_verification_email(user.email, code)
        except EmailServiceError:
            # Keep registration successful, but the user will need a resend once SMTP is configured.
            pass
    db.commit()
    if user.email and not user.is_verified:
        return {'message': 'Registration completed. Check your email for the verification code.'}
    return {'message': 'Registration completed. Please sign in.'}


@router.post('/login', response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = login_user(db, payload.login, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid credentials',
        )
    if user.email and not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Email is not verified',
        )
    return issue_tokens(db, user)


@router.post('/refresh', response_model=TokenOut)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)):
    result = refresh_access_token(db, payload.refresh_token)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid refresh token')
    return {**result, 'refresh_token': None}


@router.post('/logout', status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshIn, db: Session = Depends(get_db)):
    if not revoke_refresh_token(db, payload.refresh_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid refresh token')
    return None


@router.get('/me', response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user


@router.post('/verify/request', status_code=status.HTTP_204_NO_CONTENT)
def verify_request(payload: VerifyRequestIn, db: Session = Depends(get_db)):
    login = payload.login.strip()
    if not login:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Login required')

    user = get_user_by_login(db, login)
    if not user:
        return None

    if user.email:
        try:
            code = create_verification_code(db, user, 'email')
            send_verification_email(user.email, code)
        except EmailServiceError:
            return None
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Login and code required')

    user = get_user_by_login(db, login)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    channel = 'email' if user.email else 'phone' if user.phone else 'email'
    if not confirm_verification_code(db, user, channel, code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid code')
    return None


@router.post('/change-password', status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid old password')
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()

    create_notification(
        db,
        user_id=str(current_user.id),
        type_=NotificationType.system,
        title='Пароль изменен',
        body='Пароль вашего аккаунта был изменен.',
        deep_link='/settings/account',
    )
    db.commit()
    return None


@router.post('/password/reset-request', status_code=status.HTTP_204_NO_CONTENT)
def reset_request(payload: ResetRequestIn, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    try:
        send_password_reset_email(email)
        return None
    except FirebaseAuthError as exc:
        error_text = str(exc)

    # do not leak whether email exists
    local_user = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
    if not local_user:
        return None

    # For EMAIL_NOT_FOUND we create Firebase user once and retry.
    if 'EMAIL_NOT_FOUND' in error_text:
        try:
            ensure_user_exists(email)
            send_password_reset_email(email)
        except FirebaseAuthError:
            return None
        return None

    # Firebase can return CONNECTION_NOT_FOUND / OPERATION_NOT_ALLOWED when provider is misconfigured.
    # Keep endpoint idempotent for client and avoid 400 on UI.
    return None


@router.post('/password/reset-confirm', status_code=status.HTTP_204_NO_CONTENT)
def reset_confirm(payload: ResetConfirmIn, db: Session = Depends(get_db)):
    try:
        email = confirm_password_reset(payload.oob_code, payload.new_password)
    except FirebaseAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    user = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found for this email')

    user.password_hash = hash_password(payload.new_password)
    db.commit()

    create_notification(
        db,
        user_id=str(user.id),
        type_=NotificationType.system,
        title='Пароль изменен',
        body='Вы успешно изменили пароль.',
        deep_link='/login',
    )
    db.commit()
    return None
