from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    roles: list[str]
    permissions: list[str]
    point_of_sale_ids: list[int] = []
    card_visibility: str = "search_any"
    permission_overrides: list[dict] = []
