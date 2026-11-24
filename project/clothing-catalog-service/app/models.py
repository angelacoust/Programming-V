from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ItemStatus = Literal["Available", "Sold"]


class ClothingItemCreate(BaseModel):
    """Body of POST /clothes."""

    name: str = Field(min_length=1)
    price: float = Field(gt=0)
    description: str | None = None
    seller: str | None = None
    category: str | None = None
    size: str | None = None
    condition: str | None = None

    model_config = ConfigDict(extra="allow")


class ClothingItem(ClothingItemCreate):
    """A clothing item as returned by the API."""

    id: str
    status: ItemStatus = "Available"


class FavoriteCreate(BaseModel):
    """Body of POST /favorites (flexible field names)."""

    user: str | None = None
    username: str | None = None
    buyer: str | None = None
    buyerName: str | None = None
    buyer_name: str | None = None
    item_id: str | None = None
    itemId: str | None = None
    clothing_id: str | None = None
    clothes_id: str | None = None
    id: str | None = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class StatusUpdate(BaseModel):
    """Body for status updates."""

    status: ItemStatus


class PurchaseUpdate(BaseModel):
    """Body for marking an item purchased."""

    status: str | None = None
