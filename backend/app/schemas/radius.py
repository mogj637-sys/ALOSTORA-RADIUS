from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RadiusAuthorizeRequest(BaseModel):
    nas_identifier: str = Field(min_length=1, max_length=150)
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(default="", max_length=500)
    chap_password_hex: str | None = Field(default=None, max_length=64, pattern=r"^[0-9A-Fa-f]*$")
    chap_challenge_hex: str | None = Field(default=None, max_length=64, pattern=r"^[0-9A-Fa-f]*$")
    framed_ip_address: str | None = Field(default=None, max_length=45)
    calling_station_id: str | None = Field(default=None, max_length=100)


class RadiusAccountingRequest(BaseModel):
    nas_identifier: str = Field(min_length=1, max_length=150)
    username: str = Field(min_length=1, max_length=120)
    acct_session_id: str = Field(min_length=1, max_length=150)
    status_type: Literal["Start", "Interim-Update", "Stop"]
    event_timestamp: datetime | None = None
    framed_ip_address: str | None = Field(default=None, max_length=45)
    calling_station_id: str | None = Field(default=None, max_length=100)
    session_time_seconds: int = Field(default=0, ge=0)
    input_octets: int = Field(default=0, ge=0)
    output_octets: int = Field(default=0, ge=0)
    input_gigawords: int = Field(default=0, ge=0)
    output_gigawords: int = Field(default=0, ge=0)


class RadiusAccountingResponse(BaseModel):
    processed: bool
    duplicate: bool = False
    disconnect_required: bool = False
    disconnect_sent: bool = False
    reason: str
