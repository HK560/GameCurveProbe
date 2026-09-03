from __future__ import annotations

from urllib.parse import urlparse
from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)


def require_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> str:
    expected_token = getattr(request.app.state.context, "token", None)
    if not credentials or credentials.credentials != expected_token:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Invalid or missing bearer token."},
        )
    return credentials.credentials


def verify_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        return

    allowed = getattr(request.app.state.context, "allowed_origins", frozenset())
    parsed = urlparse(origin)
    normalized = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    if normalized not in allowed and origin.rstrip("/") not in allowed:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN_ORIGIN", "message": f"Origin {origin} not allowed."},
        )
