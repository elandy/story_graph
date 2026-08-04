import secrets

from starlette.requests import Request
from starlette.responses import Response

COOKIE_NAME = "session_id"


def get_or_create_session_id(
    request: Request,
    response: Response | None = None,
) -> str:
    session_id = request.cookies.get(COOKIE_NAME)

    if session_id:
        return session_id

    session_id = secrets.token_urlsafe(32)

    if response is not None:
        response.set_cookie(
            COOKIE_NAME,
            session_id,
            httponly=True,
            samesite="lax",
        )

    return session_id