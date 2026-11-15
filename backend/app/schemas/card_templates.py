from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

class CardTemplateBase(BaseModel):
    code: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    width_mm: Decimal = Field(default=Decimal("90"), gt=0, le=300)
    height_mm: Decimal = Field(default=Decimal("50"), gt=0, le=300)
    background_color: str = Field(default="#ffffff", pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str = Field(default="#173b2d", pattern=r"^#[0-9A-Fa-f]{6}$")
    layout: dict = Field(default_factory=dict)

class CardTemplateCreate(CardTemplateBase):
    pass

class CardTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    width_mm: Decimal | None = Field(default=None, gt=0, le=300)
    height_mm: Decimal | None = Field(default=None, gt=0, le=300)
    background_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    layout: dict | None = None
    is_default: bool | None = None

class CardTemplateResponse(CardTemplateBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_default: bool
