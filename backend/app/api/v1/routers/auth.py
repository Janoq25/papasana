from fastapi import APIRouter, Body, Cookie, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user
from app.api.v1.serializers import me_out
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.auth import (
    ChangePasswordIn,
    ForgotPasswordIn,
    LoginIn,
    LogoutIn,
    ResetPasswordIn,
    TokenOut,
)
from app.schemas.common import Message
from app.schemas.user import MeOut
from app.services.auth_service import AuthService, IssuedTokens

router = APIRouter(prefix="/auth", tags=["Autenticación"])
_s = get_settings()


def _set_refresh_cookie(response: Response, raw: str) -> None:
    response.set_cookie(
        key=_s.refresh_cookie_name,
        value=raw,
        max_age=_s.refresh_token_days * 24 * 3600,
        httponly=True,
        secure=_s.cookie_secure,
        samesite="strict",
        path=_s.refresh_cookie_path,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(_s.refresh_cookie_name, path=_s.refresh_cookie_path, httponly=True,
                           secure=_s.cookie_secure, samesite="strict")


def _token_out(db: Session, t: IssuedTokens) -> TokenOut:
    return TokenOut(access_token=t.access_token, expires_in=t.expires_in, user=me_out(db, t.user))


@router.post("/login", response_model=TokenOut, summary="Iniciar sesión")
@limiter.limit("10/minute")
def login(request: Request, response: Response, body: LoginIn, db: Session = Depends(get_db)):
    tokens = AuthService(db).login(body.email, body.password)
    _set_refresh_cookie(response, tokens.refresh_token)
    return _token_out(db, tokens)


@router.post("/refresh", response_model=TokenOut, summary="Renovar el token de acceso (cookie de refresh)")
@limiter.limit("30/minute")
def refresh(request: Request, response: Response, db: Session = Depends(get_db),
            ps_refresh: str | None = Cookie(default=None)):
    tokens = AuthService(db).refresh(ps_refresh)
    _set_refresh_cookie(response, tokens.refresh_token)
    return _token_out(db, tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Cerrar sesión")
def logout(response: Response, body: LogoutIn = Body(default_factory=LogoutIn), db: Session = Depends(get_db),
           ps_refresh: str | None = Cookie(default=None)):
    svc = AuthService(db)
    session = svc.session_from_refresh_cookie(ps_refresh)
    if session is not None:
        svc.logout(session, body.reason)
    _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=MeOut, summary="Usuario actual, permisos y parámetros de sesión")
def me(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return me_out(db, current.user)


@router.post("/forgot-password", response_model=Message, status_code=202, summary="Solicitar recuperación")
@limiter.limit("5/minute")
def forgot_password(request: Request, body: ForgotPasswordIn, db: Session = Depends(get_db)):
    AuthService(db).forgot_password(body.email)
    return Message(message="Si el correo está registrado, recibirá un enlace para restablecer la contraseña.")


@router.post("/reset-password", response_model=Message, summary="Restablecer contraseña con el enlace recibido")
@limiter.limit("10/minute")
def reset_password(request: Request, body: ResetPasswordIn, db: Session = Depends(get_db)):
    AuthService(db).reset_password(body.token, body.new_password)
    return Message(message="Contraseña actualizada. Ya puede iniciar sesión.")


@router.post("/change-password", response_model=Message, summary="Cambiar la contraseña propia")
def change_password(body: ChangePasswordIn, current: CurrentUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    AuthService(db).change_password(current.user, current.session, body.current_password, body.new_password)
    return Message(message="Contraseña actualizada. Se cerraron sus otras sesiones.")
