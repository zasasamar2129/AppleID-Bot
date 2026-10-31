from pydantic import BaseModel

class TokenRequest(BaseModel):
    order_id: str
    amount: int  # Amount in Rial
    redirect_url: str

class TokenResponse(BaseModel):
    token: str
    url: str

class VerifyRequest(BaseModel):
    ref_num: str
    terminal_id: str

class VerifyResponse(BaseModel):
    paid: bool
    external_id: str | None
    amount: int | None
