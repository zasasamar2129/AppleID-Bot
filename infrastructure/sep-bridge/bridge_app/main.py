import logging
from fastapi import Depends, FastAPI, HTTPException, status
from bridge_app.auth import verify_authentication
from bridge_app.config import settings
from bridge_app.schemas import TokenRequest, TokenResponse, VerifyRequest, VerifyResponse
from bridge_app.sep_client import SepClient

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("sep-bridge")

app = FastAPI(title="Iran SEP Bridge", version="1.0.0")
sep_client = SepClient()

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/v1/sep/token", response_model=TokenResponse, dependencies=[Depends(verify_authentication)])
async def create_token(payload: TokenRequest):
    try:
        result = await sep_client.request_token(
            order_id=payload.order_id,
            amount_rial=payload.amount,
            redirect_url=payload.redirect_url
        )
        return TokenResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

@app.post("/api/v1/sep/verify", response_model=VerifyResponse, dependencies=[Depends(verify_authentication)])
async def verify_payment(payload: VerifyRequest):
    try:
        result = await sep_client.verify_transaction(
            ref_num=payload.ref_num,
            terminal_id=payload.terminal_id
        )
        return VerifyResponse(**result)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
