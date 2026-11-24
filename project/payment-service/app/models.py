from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    """Body of POST /payments (flexible field names)."""

    orderId: str | None = None
    order_id: str | None = None
    id: str | None = None
    order: str | None = None
    amount: float | None = None
    total: float | None = None
    price: float | None = None
    card_number: str | None = None
    cardNumber: str | None = None
    card: str | None = None
    cvv: str | None = None
    expiry: str | None = None
    exp: str | None = None

    model_config = ConfigDict(extra="allow")


class Payment(BaseModel):
    """A payment as returned by the API."""

    id: str
    paymentId: str | None = None
    orderId: str | None = None
    order_id: str | None = None
    amount: float
    total: float | None = None
    status: str
    paid: bool
    card_last4: str | None = None
    created_at: datetime

    model_config = ConfigDict(extra="allow")


class PaymentReceipt(Payment):
    pass
