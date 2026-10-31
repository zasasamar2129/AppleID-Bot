import secrets
from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from bridge_app.config import settings

security = HTTPBearer()

async def verify_authentication(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    # 1. Verify IP Restriction if enabled
    if settings.allowed_client_ip:
        client_ip = request.client.host if request.client else None
        if client_ip != settings.allowed_client_ip:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied for this client IP"
            )

    # 2. Constant-time comparison for API Key
    token = credentials.credentials
    if not secrets.compare_digest(token, settings.bridge_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token
