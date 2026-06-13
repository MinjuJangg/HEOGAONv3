from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IntakeResult(BaseModel):
    intent: Literal["food", "signage", "outdoor", "general", "unsupported"] = "food"
    business_type: str | None = None
    region: str | None = None
    address: str | None = None
    building_use: str | None = None
    sales_modes: list[str] = Field(default_factory=list)
    signage_wanted: bool = False
    outdoor_wanted: bool = False
    liquor_sales: bool | None = None
    on_site_consumption: bool | None = None
    manufacturing_mode: str | None = None
    unknowns: list[str] = Field(default_factory=list)
    confidence: float = 0.0


